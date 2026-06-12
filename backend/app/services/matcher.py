import logging
import re
import time
from datetime import date, datetime

from qdrant_client.models import FieldCondition, Filter, MatchAny

from app.models import AnalyzeRequest, AnalyzeResponse, ConsultantMatch, ScoreDetail
from app.services.claude_service import generate_explanations, rewrite_offer
from app.services.config_service import get_app_config
from app.services.embeddings import embedding_service

logger = logging.getLogger(__name__)

# Plage réelle de similarité cosinus pour paraphrase-multilingual-MiniLM-L12-v2
# Sur des textes longs (CVs), le modèle ne dépasse jamais ~0.85 même pour un match parfait
# et reste au-dessus de ~0.25 même pour des textes peu liés.
_COSINE_FLOOR = 0.25
_COSINE_CEIL  = 0.85


def _calibrate_cosine(raw: float) -> float:
    """Ramène la similarité cosinus brute dans la plage utile [0.0, 1.0]."""
    return max(0.0, min(1.0, (raw - _COSINE_FLOOR) / (_COSINE_CEIL - _COSINE_FLOOR)))


def _keyword_ratio(offer_skills: list[str], cv_text: str) -> float:
    """Proportion des compétences de l'offre littéralement présentes dans le CV (0.0–1.0)."""
    if not offer_skills:
        return 0.0
    cv_lower = cv_text.lower()
    hits = sum(1 for s in offer_skills if s.lower() in cv_lower)
    return hits / len(offer_skills)


def _skill_match(offer_skills: list[str], cv_text: str) -> tuple[list[str], list[str]]:
    cv_lower = cv_text.lower()
    matched = [s for s in offer_skills if s.lower() in cv_lower]
    missing = [s for s in offer_skills if s.lower() not in cv_lower]
    return matched[:8], missing[:4]


def _infer_title(cv_meta_title: str, cv_text: str) -> str:
    if cv_meta_title:
        return cv_meta_title
    lines = [ln.strip() for ln in cv_text.split("\n") if ln.strip()]
    return lines[1][:60] if len(lines) > 1 else (lines[0][:60] if lines else "Consultant")


def _score_domain(consultant_domains: list[str], target_domain: str | None) -> int:
    """0–25 pts. Priorité absolue si le consultant a déjà travaillé dans ce domaine."""
    if not target_domain or not consultant_domains:
        return 0
    cfg = get_app_config()
    if target_domain in consultant_domains:
        return 25
    if any(d in consultant_domains for d in cfg.domain_similar.get(target_domain, [])):
        return 12
    return 0


def _score_availability(status: str | None, availability_date: str | None) -> int:
    """0–15 pts. Favorise les ressources en intercontrat disponibles rapidement."""
    if status == "intercontrat":
        if not availability_date:
            return 15
        try:
            avail = datetime.strptime(availability_date, "%Y-%m-%d").date()
            delta = (avail - date.today()).days
            if delta <= 0:  return 15
            if delta <= 14: return 12
            if delta <= 30: return 8
            return 3
        except Exception:
            return 10
    if status == "preavailable":
        return 7
    if availability_date:
        try:
            avail = datetime.strptime(availability_date, "%Y-%m-%d").date()
            delta = (avail - date.today()).days
            if delta <= 30: return 5
            if delta <= 90: return 2
        except Exception:
            pass
    # en_mission sans date connue : ressource pool, score neutre minimum
    return 3


def _score_location(
    consultant_location: str | None,
    consultant_remote: str | None,
    target_location: str | None,
    target_remote: str | None,
) -> int:
    """0–5 pts."""
    score = 0
    if target_remote and consultant_remote:
        if target_remote == "full" and consultant_remote == "full":
            score += 3
        elif target_remote in ("partial", "none") and consultant_remote in ("partial", "none"):
            score += 1
    if target_location and consultant_location:
        tl, cl = target_location.lower(), consultant_location.lower()
        if tl in cl or cl in tl:
            score += 5
    return min(score, 5)


def _max_possible_score(
    eff_domain: str | None,
    eff_location: str | None,
    eff_remote: str | None,
    request_seniority: str | None = None,
) -> int:
    """Calcule le score maximum atteignable selon les critères actifs de la requête."""
    max_score = 55  # compétences toujours présentes
    if eff_domain:
        max_score += 25
    if eff_location or eff_remote:
        max_score += 5
    max_score += 15  # disponibilité : toujours dans le dénominateur (critère métier)
    if request_seniority:
        max_score += 5
    return max_score


def _passes_hard_filters(
    r: dict,
    filter_intercontrat_only: bool,
    filter_languages: list[str],
) -> bool:
    # Garde Python en filet de sécurité — Qdrant a déjà appliqué ces filtres en amont
    if filter_intercontrat_only:
        if r.get("status", "intercontrat") == "en_mission":
            return False
    if filter_languages:
        if not any(lang in r.get("languages", ["fr"]) for lang in filter_languages):
            return False
    return True


def _build_qdrant_filter(
    filter_intercontrat_only: bool,
    filter_languages: list[str],
) -> Filter | None:
    """Construit un filtre Qdrant natif (pre-filtering côté base vectorielle)."""
    conditions = []
    if filter_intercontrat_only:
        conditions.append(
            FieldCondition(key="status", match=MatchAny(any=["intercontrat", "preavailable"]))
        )
    if filter_languages:
        conditions.append(
            FieldCondition(key="languages", match=MatchAny(any=filter_languages))
        )
    return Filter(must=conditions) if conditions else None


# ── Séniorité ─────────────────────────────────────────────────────────────────

_SENIORITY_EXPERT = {"expert", "lead", "principal", "architecte senior", "directeur technique"}
_SENIORITY_SENIOR = {"sénior", "senior", "confirmé", "expérimenté", "chevronné"}
_SENIORITY_JUNIOR = {"junior", "débutant", "entry level", "jeune diplômé"}


def _detect_request_seniority(mission_text: str, offer_title: str) -> str | None:
    """Détecte le niveau de séniorité demandé dans la requête. Retourne 'expert'|'senior'|'junior'|None."""
    combined = f"{offer_title} {mission_text}".lower()
    if any(kw in combined for kw in _SENIORITY_EXPERT):
        return "expert"
    if any(kw in combined for kw in _SENIORITY_SENIOR):
        return "senior"
    if any(kw in combined for kw in _SENIORITY_JUNIOR):
        return "junior"
    return None


def _years_to_seniority(years: int) -> str:
    if years >= 12: return "expert"
    if years >= 6:  return "senior"
    if years >= 3:  return "confirme"
    return "junior"


def _score_seniority(cv_title: str, cv_years: int | None, request_seniority: str | None) -> int:
    """0–5 pts. Bonus si la séniorité du consultant correspond à celle demandée dans la requête."""
    if not request_seniority:
        return 0
    years = cv_years
    if years is None:
        m = re.search(r"(\d+)\s*ans?", cv_title, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 50:
                years = val
    if years is None:
        return 0
    cv_level = _years_to_seniority(years)
    table = {
        ("expert", "expert"):   5,
        ("expert", "senior"):   2,
        ("expert", "confirme"): 0,
        ("expert", "junior"):   0,
        ("senior", "expert"):   3,
        ("senior", "senior"):   5,
        ("senior", "confirme"): 1,
        ("senior", "junior"):   0,
        ("junior", "junior"):   5,
        ("junior", "confirme"): 1,
        ("junior", "senior"):   0,
        ("junior", "expert"):   0,
    }
    return table.get((request_seniority, cv_level), 0)


async def analyze_and_match(request: AnalyzeRequest) -> AnalyzeResponse:
    t0 = time.monotonic()
    offer = await rewrite_offer(request.mission_text)
    logger.info(
        "[matcher] Offre réécrite — title='%s' domain='%s' skills=%s soft=%s",
        offer.title, offer.domain, offer.technical_skills, offer.soft_skills,
    )

    eff_domain    = request.filter_domain    or offer.domain
    eff_location  = request.filter_location  or offer.location
    eff_remote    = request.filter_remote    or offer.remote
    eff_languages = request.filter_languages or offer.languages

    all_skills = offer.technical_skills + offer.soft_skills
    if request.priority_skills:
        all_skills = request.priority_skills + [s for s in all_skills if s not in request.priority_skills]

    # [7.2] Requête Qdrant sur le texte brut de l'utilisateur, pas sur l'offre enrichie par le LLM.
    # L'offre LLM reste utilisée pour le keyword matching et le scoring, pas pour l'embedding de requête.
    query_text = request.mission_text

    logger.info("[matcher] Requête Qdrant (%d chars) : %s", len(query_text), query_text[:200])

    # [7.3] Séniorité demandée dans la requête
    request_seniority = _detect_request_seniority(request.mission_text, offer.title)
    logger.info("[matcher] Séniorité détectée : %s", request_seniority or "aucune")

    # [7.5] Filtre Qdrant natif : pré-filtrage côté base vectorielle avant le scoring Python
    qdrant_filter = _build_qdrant_filter(request.filter_intercontrat_only, eff_languages)

    ranked = embedding_service.rank_by_similarity(query_text, qdrant_filter=qdrant_filter)
    if ranked:
        logger.info(
            "[matcher] Qdrant — %d résultats | cosinus min=%.3f max=%.3f",
            len(ranked), min(r["score"] for r in ranked), max(r["score"] for r in ranked),
        )
    else:
        logger.warning("[matcher] Qdrant n'a retourné aucun résultat")

    max_possible = _max_possible_score(eff_domain, eff_location, eff_remote, request_seniority)
    logger.info(
        "[matcher] Score max atteignable = %d (domain=%s, loc=%s, remote=%s, seniorite=%s)",
        max_possible, eff_domain, eff_location, eff_remote, request_seniority,
    )

    scored = []
    for r in ranked:
        # Filet de sécurité Python — Qdrant a déjà filtré mais on vérifie par précaution
        if not _passes_hard_filters(r, request.filter_intercontrat_only, eff_languages):
            logger.debug("[matcher] Filtré (filet Python) : %s", r.get("name"))
            continue

        # Score compétences : hybride 70% embedding sémantique + 30% matching direct
        calibrated = _calibrate_cosine(r["score"])
        kw_ratio   = _keyword_ratio(offer.technical_skills, r["text"])
        hybrid     = calibrated * 0.70 + kw_ratio * 0.30
        skills_score = max(0, min(55, round(hybrid * 55)))

        domain_score    = _score_domain(r.get("domains", []), eff_domain)
        avail_score     = _score_availability(r.get("status"), r.get("availability_date"))
        loc_score       = _score_location(r.get("location"), r.get("remote"), eff_location, eff_remote)
        seniority_score = _score_seniority(r.get("title", ""), r.get("years_experience"), request_seniority)

        raw_total = skills_score + domain_score + avail_score + loc_score + seniority_score
        display_score = min(100, round(raw_total * 100 / max_possible))

        logger.debug(
            "[matcher] %s — cosinus=%.3f calib=%.3f kw=%.2f | skills=%d domain=%d avail=%d loc=%d senior=%d → %d%%",
            r.get("name", "?"), r["score"], calibrated, kw_ratio,
            skills_score, domain_score, avail_score, loc_score, seniority_score, display_score,
        )

        scored.append({
            **r,
            "_total":    display_score,
            "_raw":      raw_total,
            "_skills":   skills_score,
            "_domain":   domain_score,
            "_avail":    avail_score,
            "_loc":      loc_score,
            "_seniority": seniority_score,
        })

    scored.sort(key=lambda x: x["_total"], reverse=True)
    top = scored[: request.max_results]

    if top:
        logger.info(
            "[matcher] Top 3 résultats : %s",
            [(r.get("name"), r["_total"]) for r in top[:3]],
        )

    offer_summary = f"Poste: {offer.title}. Compétences: {', '.join(offer.technical_skills[:6])}."
    if eff_domain:
        offer_summary += f" Domaine: {eff_domain}."
    explanations = await generate_explanations(offer_summary, [r["text"] for r in top])

    consultants = [
        ConsultantMatch(
            id=r["cv_id"],
            name=r["name"],
            title=_infer_title(r.get("title", ""), r["text"]),
            score=r["_total"],
            matched_skills=_skill_match(all_skills, r["text"])[0],
            missing_skills=_skill_match(all_skills, r["text"])[1],
            explanation=explanations[i],
            available=r.get("available", True),
            cv_filename=r["filename"],
            availability_date=r.get("availability_date"),
            location=r.get("location"),
            remote=r.get("remote"),
            languages=r.get("languages", []),
            domains=r.get("domains", []),
            status=r.get("status"),
            email=r.get("email"),
            score_detail=ScoreDetail(
                skills=r["_skills"],
                domain=r["_domain"],
                availability=r["_avail"],
                location=r["_loc"],
            ),
        )
        for i, r in enumerate(top)
    ]

    logger.info(
        "[matcher] Pipeline terminé en %.2fs — %d consultants retournés sur %d CVs",
        time.monotonic() - t0, len(consultants), embedding_service.cv_count,
    )

    return AnalyzeResponse(
        rewritten_offer=offer,
        consultants=consultants,
        total_cvs=embedding_service.cv_count,
    )
