import asyncio
import json
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.models import ConsultantMatch, EmailConfig, RewrittenOffer

logger = logging.getLogger(__name__)

_CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "email_config.json"

_REMOTE_LABELS = {"full": "Full remote", "partial": "Remote partiel", "none": "Présentiel"}
_STATUS_LABELS = {"intercontrat": "Intercontrat", "en_mission": "En mission", "preavailable": "Préavailable"}


def load_email_config() -> EmailConfig:
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return EmailConfig(**json.load(f))
    return EmailConfig()


def save_email_config(config: EmailConfig) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)


def _build_html(offer: RewrittenOffer, consultants: list[ConsultantMatch]) -> str:
    skills_str = ", ".join(offer.technical_skills[:6])

    details = []
    if offer.start_date:
        details.append(f"<strong>Démarrage :</strong> {offer.start_date}")
    if offer.location:
        details.append(f"<strong>Localisation :</strong> {offer.location}")
    if offer.remote:
        details.append(f"<strong>Remote :</strong> {_REMOTE_LABELS.get(offer.remote, offer.remote)}")
    if offer.languages:
        details.append(f"<strong>Langues :</strong> {', '.join(l.upper() for l in offer.languages)}")
    if offer.domain:
        details.append(f"<strong>Domaine :</strong> {offer.domain.capitalize()}")
    detail_html = " &nbsp;·&nbsp; ".join(details)

    rows = []
    for c in consultants:
        status_label = _STATUS_LABELS.get(c.status or "", c.status or "")
        dispo_color = "#28a745" if c.available else ("#f59e0b" if c.status == "preavailable" else "#999")
        dispo_text = c.availability_date if c.availability_date else ("Disponible" if c.available else status_label)
        domains_str = ", ".join(c.domains) if c.domains else "—"
        langs_str   = ", ".join(l.upper() for l in c.languages) if c.languages else "FR"
        email_cell  = f'<a href="mailto:{c.email}" style="color:#FF7900">{c.email}</a>' if c.email else "—"
        rows.append(f"""<tr>
          <td style="padding:10px 12px;border-bottom:1px solid #eee"><strong>{c.name}</strong><br>
            <span style="font-size:12px;color:#666">{c.title}</span></td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:center">
            <span style="background:#FF7900;color:#fff;padding:3px 9px;border-radius:12px;font-weight:700;font-size:13px">{c.score}%</span></td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;color:{dispo_color};font-weight:500;font-size:13px">{dispo_text}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;font-size:12px;color:#0055aa">{domains_str}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;font-size:13px">{c.location or "—"}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;font-size:13px">{langs_str}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;font-size:12px">{email_cell}</td>
        </tr>""")

    n = len(consultants)
    s = "s" if n > 1 else ""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Shortlist MatchConsult — {offer.title}</title></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;color:#333;background:#f5f5f5">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:24px 0">
    <tr><td align="center">
      <table width="700" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:6px;overflow:hidden">

        <!-- Header -->
        <tr><td style="background:#000;padding:18px 24px">
          <table cellpadding="0" cellspacing="0"><tr>
            <td style="background:#FF7900;width:32px;height:32px;border-radius:2px;text-align:center;vertical-align:middle">
              <span style="color:#fff;font-weight:700;font-size:18px">m</span></td>
            <td style="padding-left:12px;color:#fff;font-size:16px;font-weight:500">MatchConsult</td>
            <td style="padding-left:12px;color:#888;font-size:13px">— Orange Business · Sourcing ESN</td>
          </tr></table>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:28px 24px">
          <h2 style="margin:0 0 20px;color:#000;font-size:20px">Shortlist — {offer.title}</h2>

          <!-- Offer summary -->
          <div style="background:#f8f8f8;padding:16px 20px;border-left:4px solid #FF7900;margin-bottom:24px;font-size:14px;line-height:1.7">
            <strong>Mission :</strong> {offer.title} &nbsp;·&nbsp;
            <strong>Type :</strong> {offer.mission_type} — {offer.duration}<br>
            <strong>Compétences :</strong> {skills_str}<br>
            {detail_html}
          </div>

          <!-- Consultants table -->
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
            <thead>
              <tr style="background:#FF7900;color:#fff">
                <th style="padding:10px 12px;text-align:left;font-weight:600">Consultant</th>
                <th style="padding:10px 12px;text-align:center;font-weight:600">Score</th>
                <th style="padding:10px 12px;text-align:left;font-weight:600">Disponibilité</th>
                <th style="padding:10px 12px;text-align:left;font-weight:600">Domaines</th>
                <th style="padding:10px 12px;text-align:left;font-weight:600">Localisation</th>
                <th style="padding:10px 12px;text-align:left;font-weight:600">Langues</th>
                <th style="padding:10px 12px;text-align:left;font-weight:600">Email</th>
              </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
          </table>

          <p style="color:#888;font-size:13px;margin-top:20px">
            <em>{n} consultant{s} sélectionné{s} · Généré automatiquement par MatchConsult</em>
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#f0f0f0;padding:12px 24px;text-align:center;font-size:12px;color:#999">
          MatchConsult · Orange Business · Cet email a été généré automatiquement — ne pas répondre
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _send_sync(config: EmailConfig, subject: str, html_body: str, recipients: list[str]) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{config.sender_name} <{config.sender_email}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as srv:
        srv.ehlo()
        srv.starttls(context=ctx)
        if config.smtp_user and config.smtp_password:
            srv.login(config.smtp_user, config.smtp_password)
        srv.sendmail(config.sender_email, recipients, msg.as_string())


async def send_results_email(
    offer: RewrittenOffer,
    consultants: list[ConsultantMatch],
    extra_recipients: list[str] = [],
) -> tuple[bool, str, list[str]]:
    config = load_email_config()
    all_recipients = list(dict.fromkeys(config.recipients + extra_recipients))

    if not all_recipients:
        return False, "Aucun destinataire configuré. Rendez-vous sur la page Administration.", []
    if not config.smtp_host:
        return False, "Serveur SMTP non configuré. Rendez-vous sur la page Administration.", []

    html    = _build_html(offer, consultants)
    n       = len(consultants)
    subject = f"[MatchConsult] Shortlist — {offer.title} ({n} candidat{'s' if n > 1 else ''})"

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_sync, config, subject, html, all_recipients)
        return True, f"Email envoyé à {len(all_recipients)} destinataire(s).", all_recipients
    except Exception as e:
        logger.error("Email send error: %s", e)
        return False, f"Erreur d'envoi : {e}", []
