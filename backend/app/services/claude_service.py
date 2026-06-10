import asyncio
import json
import logging

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


# ── Anthropic ─────────────────────────────────────────────────────────────────

def _anthropic_client():
    import anthropic
    return anthropic.AsyncAnthropic(api_key=_effective_anthropic_key())


async def _anthropic_rewrite(mission_text: str) -> RewrittenOffer:
    client = _anthropic_client()
    msg = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=_REWRITE_SYSTEM,
        messages=[{"role": "user", "content": _REWRITE_TEMPLATE.format(mission_text=mission_text[:4000])}],
    )
    raw = _strip_markdown(msg.content[0].text)
    return RewrittenOffer(**json.loads(raw))


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
        logger.error("Anthropic explanation failed: %s", e)
        return "Profil correspondant aux exigences de la mission."


# ── Groq ──────────────────────────────────────────────────────────────────────

def _groq_client():
    from groq import AsyncGroq
    return AsyncGroq(api_key=_effective_groq_key())


async def _groq_rewrite(mission_text: str) -> RewrittenOffer:
    client = _groq_client()
    resp = await client.chat.completions.create(
        model=_effective_groq_model(),
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _REWRITE_SYSTEM},
            {"role": "user", "content": _REWRITE_TEMPLATE.format(mission_text=mission_text[:4000])},
        ],
    )
    raw = _strip_markdown(resp.choices[0].message.content)
    return RewrittenOffer(**json.loads(raw))


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
        logger.error("Groq explanation failed: %s", e)
        return "Profil correspondant aux exigences de la mission."


# ── Public API ────────────────────────────────────────────────────────────────

async def rewrite_offer(mission_text: str) -> RewrittenOffer:
    backend = _effective_backend()
    logger.info("LLM backend: %s", backend)
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
