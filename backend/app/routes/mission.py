from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.models import (
    AdminConfig, AnalyzeRequest, AnalyzeResponse,
    AppConfig, EmailConfig, HealthResponse,
    SendResultsRequest, SendResultsResponse,
)
from app.services.config_service import get_app_config, save_app_config
from app.services.email_service import load_email_config, save_email_config, send_results_email
from app.services.embeddings import embedding_service
from app.services.matcher import analyze_and_match

router = APIRouter()


# ── Santé ─────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        cvs_loaded=embedding_service.cv_count,
        model_ready=embedding_service.is_ready,
    )


# ── Matching ──────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    if embedding_service.cv_count == 0:
        raise HTTPException(503, "Aucun CV disponible. Vérifiez le répertoire CV_DIRECTORY.")
    try:
        return await analyze_and_match(request)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Envoi email ───────────────────────────────────────────────────────────────

@router.post("/send-results", response_model=SendResultsResponse)
async def send_results(request: SendResultsRequest):
    success, message, recipients = await send_results_email(
        offer=request.offer,
        consultants=request.consultants,
        extra_recipients=request.extra_recipients,
    )
    return SendResultsResponse(success=success, message=message, recipients=recipients)


# ── Configuration admin ───────────────────────────────────────────────────────

def _mask_app(cfg: AppConfig) -> AppConfig:
    return AppConfig(**{
        **cfg.model_dump(),
        "groq_api_key":      "***" if cfg.groq_api_key      else "",
        "anthropic_api_key": "***" if cfg.anthropic_api_key else "",
    })


def _mask_email(cfg: EmailConfig) -> EmailConfig:
    return EmailConfig(**{**cfg.model_dump(), "smtp_password": "***" if cfg.smtp_password else ""})


@router.get("/config/admin", response_model=AdminConfig)
async def get_admin_config():
    return AdminConfig(app=_mask_app(get_app_config()), email=_mask_email(load_email_config()))


@router.put("/config/admin", response_model=AdminConfig)
async def update_admin_config(config: AdminConfig):
    existing_app   = get_app_config()
    existing_email = load_email_config()

    app = config.app
    if app.groq_api_key      == "***": app.groq_api_key      = existing_app.groq_api_key
    if app.anthropic_api_key == "***": app.anthropic_api_key = existing_app.anthropic_api_key

    email = config.email
    if email.smtp_password == "***": email.smtp_password = existing_email.smtp_password

    save_app_config(app)
    save_email_config(email)
    return AdminConfig(app=_mask_app(app), email=_mask_email(email))


# ── Domaines publics (pour les dropdowns UI) ──────────────────────────────────

@router.get("/domains")
async def get_domains():
    return {"domains": get_app_config().domain_list}


# ── Accès CVs ─────────────────────────────────────────────────────────────────

@router.get("/cvs/{filename}")
async def get_cv(filename: str):
    if any(c in filename for c in ("/", "\\", "..")):
        raise HTTPException(400, "Nom de fichier invalide.")
    cv_path = Path(settings.cv_directory) / filename
    if not cv_path.exists():
        raise HTTPException(404, "CV introuvable.")
    return FileResponse(cv_path)
