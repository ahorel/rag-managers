import asyncio
import json
import logging
import time

from app.config import settings
from app.models import RewrittenOffer
from app.services.demo_service import demo_explanations, demo_rewrite_offer

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM = (
    "Tu es un expert en recrutement dans une ESN française. "
    "Tu analyses des expressions de besoin client ou des fiches de poste et les structures. "
    "Tu réponds UNIQUEMENT en JSON valide, sans markdown ni texte supplémentaire."
)

_REWRITE_TEMPLATE = """\
Analyse ce texte (email client, expression de besoin ou fiche de poste) et structure-le en JSON.

Texte :
{mission_text}

Retourne UNIQUEMENT ce JSON (aucun autre texte) :
{{
  "title": "intitulé exact du poste",
  "mission_type": "Régie | Forfait | CDI | CDD",
  "duration": "ex: 6 mois, 12 mois, CDI",
  "start_date": "JJ/MM/AAAA ou 'dès que possible' ou null",
  "location": "ville ou 'Remote' ou null",
  "remote": "full | partial | none | null",
  "languages": ["fr"],
  "domain": "industrie | telecom | innovation | mobilite | finance | assurance | null",
  "technical_skills": ["compétence1", "compétence2"],
  "soft_skills": ["softskill1", "softskill2"],
  "client_context": "contexte client en 1-2 phrases"
}}"""

_EXPLAIN_TEMPLATE = """\
Mission : {offer_summary}

CV (extrait) :
{cv_excerpt}

En une seule phrase française concise (max 20 mots), explique pourquoi ce consultant correspond à cette mission."""


def _strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


def _effective_groq_key() -> str:
    from app.services.config_service import get_app_config
    return get_app_config().groq_api_key or settings.groq_api_key


def _effective_anthropic_key() -> str:
    from app.services.config_service import get_app_config
    return get_app_config().anthropic_api_key or settings.anthropic_api_key


def _effective_groq_model() -> str:
    from app.services.config_service import get_app_config
    cfg = get_app_config()
    return cfg.groq_model or settings.groq_model


def _effective_backend() -> str:
    if settings.demo_mode:
        return "demo"
    if _effective_groq_key():
        return "groq"
    if _effective_anthropic_key():
        return "anthropic"
    return "demo"


def _parse_and_validate(raw: str, backend: str) -> RewrittenOffer:
    """Parse la réponse JSON du LLM et instancie RewrittenOffer avec logs détaillés."""
    cleaned = _strip_markdown(raw)
    logger.debug("[LLM:%s] Réponse brute (300 premiers chars) : %s", backend, cleaned[:300])
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(
            "[LLM:%s] JSON invalide — position %d, msg='%s' | raw=%s",
            backend, exc.pos, exc.msg, cleaned[:500],
        )
        raise
    logger.info(
        "[LLM:%s] JSON parsé — champs présents: %s | nulls: %s",
        backend,
        list(parsed.keys()),
        [k for k, v in parsed.items() if v is None],
    )
    try:
        offer = RewrittenOffer.model_validate(parsed)
    except Exception as exc:
        logger.error(
            "[LLM:%s] Validation Pydantic échouée — dict=%s | erreur=%s",
            backend, parsed, exc,
        )
        raise
    logger.info(
        "[LLM:%s] RewrittenOffer OK — title='%s' mission_type='%s' skills=%s",
        backend, offer.title, offer.mission_type, offer.technical_skills,
    )
    return offer


# ── Anthropic ─────────────────────────────────────────────────────────────────

def _anthropic_client():
    import anthropic
    return anthropic.AsyncAnthropic(api_key=_effective_anthropic_key())


async def _anthropic_rewrite(mission_text: str) -> RewrittenOffer:
    t0 = time.monotonic()
    logger.info("[LLM:anthropic] Appel rewrite — %d chars d'entrée", len(mission_text))
    client = _anthropic_client()
    msg = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=_REWRITE_SYSTEM,
        messages=[{"role": "user", "content": _REWRITE_TEMPLATE.format(mission_text=mission_text[:4000])}],
    )
    logger.info("[LLM:anthropic] Réponse reçue en %.2fs", time.monotonic() - t0)
    return _parse_and_validate(msg.content[0].text, "anthropic")


async def _anthropic_explain_one(offer_summary: str, cv_text: str) -> str:
    try:
        client = _anthropic_client()
        msg = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=80,
            messages=[{"role": "user", "content": _EXPLAIN_TEMPLATE.format(
                offer_summary=offer_summary, cv_excerpt=cv_text[:2000]
            )}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.error("[LLM:anthropic] explain_one échoué : %s", e)
        return "Profil correspondant aux exigences de la mission."


# ── Groq ──────────────────────────────────────────────────────────────────────

def _groq_client():
    from groq import AsyncGroq
    return AsyncGroq(api_key=_effective_groq_key())


async def _groq_rewrite(mission_text: str) -> RewrittenOffer:
    t0 = time.monotonic()
    model = _effective_groq_model()
    logger.info("[LLM:groq] Appel rewrite — modèle=%s, %d chars d'entrée", model, len(mission_text))
    client = _groq_client()
    resp = await client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _REWRITE_SYSTEM},
            {"role": "user", "content": _REWRITE_TEMPLATE.format(mission_text=mission_text[:4000])},
        ],
    )
    logger.info("[LLM:groq] Réponse reçue en %.2fs", time.monotonic() - t0)
    return _parse_and_validate(resp.choices[0].message.content, "groq")


async def _groq_explain_one(offer_summary: str, cv_text: str) -> str:
    try:
        client = _groq_client()
        resp = await client.chat.completions.create(
            model=_effective_groq_model(),
            max_tokens=80,
            messages=[{"role": "user", "content": _EXPLAIN_TEMPLATE.format(
                offer_summary=offer_summary, cv_excerpt=cv_text[:2000]
            )}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("[LLM:groq] explain_one échoué : %s", e)
        return "Profil correspondant aux exigences de la mission."


# ── Public API ────────────────────────────────────────────────────────────────

async def rewrite_offer(mission_text: str) -> RewrittenOffer:
    backend = _effective_backend()
    logger.info("[rewrite_offer] Backend sélectionné : %s", backend)
    if backend == "groq":
        return await _groq_rewrite(mission_text)
    if backend == "anthropic":
        return await _anthropic_rewrite(mission_text)
    return await demo_rewrite_offer(mission_text)


async def generate_explanations(offer_summary: str, cv_texts: list[str]) -> list[str]:
    backend = _effective_backend()
    if backend == "groq":
        return await asyncio.gather(*[_groq_explain_one(offer_summary, t) for t in cv_texts])
    if backend == "anthropic":
        return await asyncio.gather(*[_anthropic_explain_one(offer_summary, t) for t in cv_texts])
    return await demo_explanations(offer_summary, cv_texts)
