"""
Mode démo — retourne des données fictives sans aucun appel LLM.
Activé par DEMO_MODE=true dans .env (ou absence de toute clé API).
"""
import re

from app.models import RewrittenOffer


def _extract_keywords(text: str) -> list[str]:
    patterns = [
        r"\bJava\b", r"\bPython\b", r"\bSpring\b", r"\bDjango\b", r"\bFastAPI\b",
        r"\bReact\b", r"\bVue\b", r"\bAngular\b", r"\bTypeScript\b", r"\bJavaScript\b",
        r"\bKubernetes\b", r"\bDocker\b", r"\bAWS\b", r"\bAzure\b", r"\bGCP\b",
        r"\bPostgreSQL\b", r"\bMySQL\b", r"\bMongoDB\b", r"\bKafka\b", r"\bRabbitMQ\b",
        r"\bMicroservices?\b", r"\bREST\b", r"\bGraphQL\b", r"\bCI/CD\b",
        r"\bDevOps\b", r"\bAgile\b", r"\bScrum\b",
    ]
    found = []
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            found.append(m.group(0))
    return found[:6] if found else ["Développement logiciel", "Architecture", "API"]


def _guess_title(text: str) -> str:
    t = text.lower()
    if "architecte" in t:           return "Architecte Logiciel / Cloud"
    if "chef de projet" in t or "moa" in t: return "Chef de Projet MOA"
    if "devops" in t:               return "Ingénieur DevOps"
    if "data" in t and "scientist" in t: return "Data Scientist"
    if "java" in t or "spring" in t: return "Lead Developer Java / Spring"
    if "python" in t:               return "Développeur Python Senior"
    if "react" in t or "frontend" in t: return "Développeur Frontend React"
    return "Consultant Technique Senior"


def _guess_type(text: str) -> str:
    t = text.lower()
    if "forfait" in t: return "Forfait"
    if "cdi" in t:     return "CDI"
    return "Régie — temps plein"


def _guess_domain(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["banque", "bancaire", "finance", "financ"]):
        return "finance"
    if any(w in t for w in ["assurance", "mutuelle"]):
        return "assurance"
    if any(w in t for w in ["telecom", "télécoms", "orange", "sfr"]):
        return "telecom"
    if any(w in t for w in ["innovation", "startup", "digital"]):
        return "innovation"
    if any(w in t for w in ["industrie", "industriel", "manufacturing"]):
        return "industrie"
    if any(w in t for w in ["mobilité", "mobilite", "transport", "automobile"]):
        return "mobilite"
    return "telecom"


async def demo_rewrite_offer(mission_text: str) -> RewrittenOffer:
    keywords = _extract_keywords(mission_text)
    return RewrittenOffer(
        title=_guess_title(mission_text),
        mission_type=_guess_type(mission_text),
        duration="6 mois (renouvelable)",
        technical_skills=keywords,
        soft_skills=["Autonomie", "Communication", "Esprit d'équipe"],
        client_context=(
            "Mission dans un contexte client grand compte — environnement agile, "
            "équipe pluridisciplinaire, démarrage rapide souhaité."
        ),
        start_date="dès que possible",
        location="Paris",
        remote="partial",
        languages=["fr"],
        domain=_guess_domain(mission_text),
    )


_DEMO_EXPLANATIONS = [
    "Profil senior très aligné avec la mission, disponible immédiatement.",
    "Solide expérience technique, contexte métier à confirmer en entretien.",
    "Bon généraliste avec les compétences clés ; montée en charge rapide.",
    "Profil orienté architecture, adéquation technique partielle.",
    "Polyvalent, expérience back-end confirmée sur des volumes similaires.",
]


async def demo_explanations(offer_summary: str, cv_texts: list[str]) -> list[str]:
    return [
        _DEMO_EXPLANATIONS[i % len(_DEMO_EXPLANATIONS)]
        for i in range(len(cv_texts))
    ]
