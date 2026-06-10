from datetime import date, datetime

from app.models import AnalyzeRequest, AnalyzeResponse, ConsultantMatch, ScoreDetail
from app.services.claude_service import generate_explanations, rewrite_offer
from app.services.config_service import get_app_config
from app.services.embeddings import embedding_service


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
    return 0


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


def _passes_hard_filters(
    r: dict,
    filter_intercontrat_only: bool,
    filter_languages: list[str],
) -> bool:
    if filter_intercontrat_only:
        if r.get("status", "intercontrat") == "en_mission" and not r.get("availability_date"):
            return False
    if filter_languages:
        if not any(lang in r.get("languages", ["fr"]) for lang in filter_languages):
            return False
    return True


async def analyze_and_match(request: AnalyzeRequest) -> AnalyzeResponse:
    offer = await rewrite_offer(request.mission_text)

    eff_domain    = request.filter_domain    or offer.domain
    eff_location  = request.filter_location  or offer.location
    eff_remote    = request.filter_remote    or offer.remote
    eff_languages = request.filter_languages or offer.languages

    all_skills = offer.technical_skills + offer.soft_skills
    if request.priority_skills:
        all_skills = request.priority_skills + [s for s in all_skills if s not in request.priority_skills]

    query_text = (
        f"{offer.title} "
        + " ".join(offer.technical_skills)
        + " "
        + " ".join(offer.soft_skills)
        + " "
        + offer.client_context
    )
    if eff_domain:
        query_text += f" {eff_domain}"

    ranked = embedding_service.rank_by_similarity(query_text)

    scored = []
    for r in ranked:
        if not _passes_hard_filters(r, request.filter_intercontrat_only, eff_languages):
            continue
        skills_score = max(0, min(55, round(r["score"] * 55)))
        domain_score = _score_domain(r.get("domains", []), eff_domain)
        avail_score  = _score_availability(r.get("status"), r.get("availability_date"))
        loc_score    = _score_location(r.get("location"), r.get("remote"), eff_location, eff_remote)
        total = skills_score + domain_score + avail_score + loc_score
        scored.append({**r, "_total": total, "_skills": skills_score, "_domain": domain_score,
                       "_avail": avail_score, "_loc": loc_score})

    scored.sort(key=lambda x: x["_total"], reverse=True)
    top = scored[: request.max_results]

    offer_summary = f"Poste: {offer.title}. Compétences: {', '.join(offer.technical_skills[:6])}."
    if eff_domain:
        offer_summary += f" Domaine: {eff_domain}."
    explanations = await generate_explanations(offer_summary, [r["text"] for r in top])

    consultants = [
        ConsultantMatch(
            id=r["cv_id"],
            name=r["name"],
            title=_infer_title(r.get("title", ""), r["text"]),
            score=min(100, r["_total"]),
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

    return AnalyzeResponse(
        rewritten_offer=offer,
        consultants=consultants,
        total_cvs=embedding_service.cv_count,
    )
