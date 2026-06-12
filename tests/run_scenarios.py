"""
MatchConsult — Scénarios de test d'intégration
===============================================
Lance tous les scénarios contre l'API et affiche les résultats détaillés
pour valider la cohérence du matching.

Usage (sur le serveur) :
    python3 tests/run_scenarios.py                          # port 8000 local
    python3 tests/run_scenarios.py http://51.83.44.48:8000  # URL explicite

Aucune dépendance externe — uniquement la stdlib Python 3.
"""

import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
TIMEOUT  = 90   # secondes — appels LLM peuvent être lents

# Credentials email — injectés via variables d'environnement (fichier .env serveur)
SMTP_HOST       = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER       = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD   = os.environ.get("SMTP_PASSWORD", "")
SMTP_RECIPIENTS = [r.strip() for r in os.environ.get("SMTP_RECIPIENTS", "").split(",") if r.strip()]

# ── Couleurs terminal ─────────────────────────────────────────────────────────

G  = "\033[92m"   # vert
R  = "\033[91m"   # rouge
Y  = "\033[93m"   # jaune
B  = "\033[94m"   # bleu
C  = "\033[96m"   # cyan
W  = "\033[97m"   # blanc
DIM = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"

def ok(s):   return f"{G}✓{RST} {s}"
def err(s):  return f"{R}✗{RST} {s}"
def warn(s): return f"{Y}⚠{RST} {s}"
def hdr(s):  return f"\n{BOLD}{C}{s}{RST}"
def dim(s):  return f"{DIM}{s}{RST}"


# ── HTTP ──────────────────────────────────────────────────────────────────────

def http_get(path: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE_URL}{path}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}

def http_post(path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{BASE_URL}{path}", data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read())
        except Exception:
            pass
        return e.code, body


# ── Affichage ─────────────────────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    name:         str
    passed:       bool
    duration:     float
    checks:       list[str]  = field(default_factory=list)
    issues:       list[str]  = field(default_factory=list)
    http_status:  int        = 0
    payload:      dict       = field(default_factory=dict)
    offer:        dict       = field(default_factory=dict)
    consultants:  list[dict] = field(default_factory=list)


all_results: list[ScenarioResult] = []


def print_offer(offer: dict):
    print(f"   {B}Fiche générée{RST}")
    print(f"   ├─ Intitulé    : {W}{offer.get('title','—')}{RST}")
    print(f"   ├─ Type        : {offer.get('mission_type','—')}")
    print(f"   ├─ Durée       : {offer.get('duration','—')}")
    print(f"   ├─ Domaine     : {offer.get('domain','—')}")
    skills = offer.get("technical_skills", [])
    soft   = offer.get("soft_skills", [])
    print(f"   ├─ Skills tech : {', '.join(skills[:5]) or '—'}")
    print(f"   └─ Soft skills : {', '.join(soft[:3]) or '—'}")


def print_consultants(consultants: list[dict], max_show: int = 5):
    print(f"   {B}Consultants matchés{RST} ({len(consultants)} résultats)")
    for i, c in enumerate(consultants[:max_show]):
        d      = c.get("score_detail", {})
        status = c.get("status", "?")
        scolor = G if status == "intercontrat" else (Y if status == "preavailable" else R)
        bar_n  = round(c["score"] / 5)
        bar    = f"{G}{'█' * bar_n}{DIM}{'░' * (20 - bar_n)}{RST}"
        print(
            f"   {'└' if i == min(max_show, len(consultants)) - 1 else '├'}─ "
            f"{BOLD}{c['name'][:28]:<28}{RST}  "
            f"{bar} {BOLD}{c['score']:>3}%{RST}  "
            f"{scolor}{status:<12}{RST}  "
            f"{dim(f'skills={d.get(\"skills\",0):>2} dom={d.get(\"domain\",0):>2} dispo={d.get(\"availability\",0):>2} loc={d.get(\"location\",0):>1}')}"
        )
        matched = c.get("matched_skills", [])
        if matched:
            print(f"   {'   '} {dim('compétences trouvées : ' + ', '.join(matched[:4]))}")


def run_scenario(name: str, payload: dict,
                 checks: list[tuple[str, Any]],
                 expect_http: int = 200) -> ScenarioResult:
    """Exécute un scénario, affiche les résultats, retourne le résultat."""
    print(hdr(f"  {name}"))
    print(f"   {dim('Requête : ' + payload.get('mission_text','')[:100] + '...')}")

    t0 = time.monotonic()
    status, data = http_post("/api/analyze", payload)
    dur = time.monotonic() - t0

    offer       = data.get("rewritten_offer", {})
    consultants = data.get("consultants", [])

    result = ScenarioResult(
        name=name, passed=True, duration=dur,
        http_status=status, payload=payload,
        offer=offer, consultants=consultants,
    )

    if status != expect_http:
        result.passed = False
        result.issues.append(f"HTTP {status} attendu {expect_http}")
        print(f"   {err(f'HTTP {status} (attendu {expect_http})')}")
        all_results.append(result)
        return result

    print(f"   {ok(f'HTTP {status}  ({dur:.1f}s)')}")

    print_offer(offer)
    print()
    print_consultants(consultants)
    print()

    # ── Vérifications de cohérence ─────────────────────────────────────────
    for label, check_fn in checks:
        try:
            ok_flag, detail = check_fn(offer, consultants, data)
            if ok_flag:
                result.checks.append(ok(f"{label} — {detail}"))
                print(f"   {ok(label)}: {dim(detail)}")
            else:
                result.passed = False
                result.issues.append(f"{label} — {detail}")
                print(f"   {err(label)}: {Y}{detail}{RST}")
        except Exception as exc:
            result.passed = False
            result.issues.append(f"{label} — exception : {exc}")
            print(f"   {err(label)}: {R}{exc}{RST}")

    all_results.append(result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DÉFINITION DES SCÉNARIOS
# ══════════════════════════════════════════════════════════════════════════════

def c_has_results(n: int):
    return lambda o, c, d: (
        len(c) >= n,
        f"{len(c)} consultant(s) retourné(s) (min attendu : {n})"
    )

def c_top_score_above(threshold: int):
    return lambda o, c, d: (
        (c[0]["score"] >= threshold if c else False),
        f"score top = {c[0]['score']}% (seuil : {threshold}%)" if c else "aucun consultant"
    )

def c_skills_contain(keyword: str):
    def check(o, c, d):
        skills = [s.lower() for s in o.get("technical_skills", [])]
        found  = any(keyword.lower() in s for s in skills)
        return found, f"'{keyword}' {'trouvé' if found else 'ABSENT'} dans {o.get('technical_skills', [])}"
    return check

def c_scores_in_range():
    def check(o, c, d):
        for x in c:
            sd = x.get("score_detail", {})
            if not (0 <= sd.get("skills", 0)       <= 55): return False, f"{x['name']} skills={sd['skills']} hors [0,55]"
            if not (0 <= sd.get("domain", 0)       <= 25): return False, f"{x['name']} domain={sd['domain']} hors [0,25]"
            if not (0 <= sd.get("availability", 0) <= 15): return False, f"{x['name']} avail={sd['availability']} hors [0,15]"
            if not (0 <= sd.get("location", 0)     <= 5):  return False, f"{x['name']} loc={sd['location']} hors [0,5]"
        return True, f"composantes vérifiées sur {len(c)} consultant(s)"
    return check

def c_domain_score_active():
    def check(o, c, d):
        best = max((x["score_detail"].get("domain", 0) for x in c), default=0)
        return best > 0, f"meilleur score domaine = {best}/25"
    return check

def c_intercontrat_only():
    def check(o, c, d):
        bad = [x["name"] for x in c if x.get("status") == "en_mission"]
        return len(bad) == 0, (
            f"tous intercontrat/preavailable ✓" if not bad
            else f"consultants en_mission dans les résultats : {bad}"
        )
    return check

def c_ordered_desc():
    def check(o, c, d):
        for i in range(len(c) - 1):
            if c[i]["score"] < c[i + 1]["score"]:
                return False, f"désordre : pos {i}={c[i]['score']}% < pos {i+1}={c[i+1]['score']}%"
        return True, f"classement décroissant vérifié ({len(c)} résultats)"
    return check

def c_no_null_fields():
    def check(o, c, d):
        nulls = [k for k, v in o.items() if v is None and k in
                 ("title", "mission_type", "duration", "technical_skills",
                  "soft_skills", "client_context")]
        return len(nulls) == 0, (
            f"aucun champ null ✓" if not nulls
            else f"champs null dans l'offre : {nulls}"
        )
    return check


SCENARIOS = [

    # ── S01a : Dev Java sénior — requête courte directe ───────────────────────
    # Cas signalé par le manager : "développeur java sénior" → Laurent Sainton 36%
    # On vérifie que les résultats sont des profils Java et que le score est cohérent
    ("S01a — Requête directe : 'développeur java sénior'", {
        "mission_text": "Nous recherchons un développeur java sénior expérimenté."
    }, [
        ("Résultats présents",        c_has_results(3)),
        ("Java extrait dans les skills", c_skills_contain("java")),
        ("Score top > 40%",            c_top_score_above(40)),
        ("Scores dans les plages",     c_scores_in_range()),
        ("Classement décroissant",     c_ordered_desc()),
        ("Pas de champs null",         c_no_null_fields()),
        # Vérification clé : les CVs des tops consultants contiennent bien 'java'
        ("Top 3 ont Java dans leur CV",
            lambda o, c, d: (
                sum(1 for x in c[:3] if "java" in x.get("matched_skills", []) or
                    any("java" in s.lower() for s in x.get("matched_skills", []))) >= 1,
                f"consultants top 3 avec Java en matched_skills : "
                f"{[x['name'] + ' ' + str(x['score']) + '%' for x in c[:3]]}"
            )
        ),
    ]),

    # ── S01b : Dev Java sénior — expression de besoin complète ───────────────
    ("S01b — Expression complète : développeur Java sénior Spring Boot", {
        "mission_text": (
            "Nous recherchons un développeur Java sénior avec minimum 8 ans d'expérience "
            "sur des projets de développement backend en Java. Maîtrise de Spring Boot, "
            "Maven, JUnit indispensable. Bonne connaissance des architectures microservices. "
            "Mission en régie, durée 6 mois renouvelable."
        )
    }, [
        ("Résultats présents",        c_has_results(3)),
        ("Java dans les skills",       c_skills_contain("java")),
        ("Score top > 45%",            c_top_score_above(45)),
        ("Scores dans les plages",     c_scores_in_range()),
        ("Classement décroissant",     c_ordered_desc()),
        ("Pas de champs null",         c_no_null_fields()),
        # S01b doit donner un meilleur top score que S01a (plus d'infos = meilleur matching)
        ("Score top S01b >= score top S01a",
            lambda o, c, d: (True, f"top score = {c[0]['score']}%  (à comparer avec S01a)")
        ),
    ]),

    # ── S02 : Chef de projet MOA ──────────────────────────────────────────────
    ("S02 — Chef de projet MOA — domaine finance", {
        "mission_text": (
            "Dans le cadre d'un projet de transformation digitale bancaire, nous cherchons "
            "un chef de projet MOA expérimenté pour piloter la refonte de notre système "
            "de gestion des crédits. Expérience en conduite du changement et rédaction de "
            "cahiers des charges fonctionnels requise. Connaissance du secteur banque ou "
            "assurance indispensable. Mission de 12 mois."
        ),
        "filter_domain": "finance"
    }, [
        ("Résultats présents",        c_has_results(1)),
        ("Score domaine activé",       c_domain_score_active()),
        ("Scores dans les plages",     c_scores_in_range()),
        ("Classement décroissant",     c_ordered_desc()),
        ("Pas de champs null",         c_no_null_fields()),
    ]),

    # ── S03 : Product Owner Agile ─────────────────────────────────────────────
    ("S03 — Product Owner Agile", {
        "mission_text": (
            "Poste de Product Owner en régie, mission 6 mois renouvelable. Le profil "
            "doit maîtriser la gestion de backlog, la rédaction de user stories et la "
            "tenue des cérémonies Scrum. Expérience dans un contexte Agile à l'échelle "
            "(SAFe) souhaitée. Environnement grands comptes."
        )
    }, [
        ("Résultats présents",        c_has_results(2)),
        ("Scores dans les plages",     c_scores_in_range()),
        ("Type de mission extrait",
            lambda o, c, d: (bool(o.get("mission_type")),
                             f"mission_type='{o.get('mission_type','')}'")
        ),
        ("Classement décroissant",     c_ordered_desc()),
        ("Pas de champs null",         c_no_null_fields()),
    ]),

    # ── S04 : Filtre intercontrat uniquement ──────────────────────────────────
    ("S04 — Filtre intercontrat : ressources disponibles uniquement", {
        "mission_text": (
            "Besoin urgent d'un consultant AMOA disponible immédiatement pour une mission "
            "d'assistance à maîtrise d'ouvrage sur un projet ERP. Démarrage dès que "
            "possible. Durée 3 mois. Connaissance SAP appréciée."
        ),
        "filter_intercontrat_only": True
    }, [
        ("Que des intercontrat/preavailable", c_intercontrat_only()),
        ("Scores dans les plages",            c_scores_in_range()),
        ("Pas de champs null",                c_no_null_fields()),
    ]),

    # ── S05 : Domaine télécom ─────────────────────────────────────────────────
    ("S05 — Architecte réseau — domaine télécom", {
        "mission_text": (
            "Dans le cadre du déploiement de notre infrastructure 5G, nous recherchons "
            "un architecte réseau ou consultant technique spécialisé dans les réseaux "
            "télécoms. Connaissance des protocoles IP, BGP, MPLS requise. Expérience "
            "chez un opérateur ou une ESN télécoms souhaitée."
        ),
        "filter_domain": "telecom"
    }, [
        ("Résultats présents",        c_has_results(1)),
        ("Score domaine activé",       c_domain_score_active()),
        ("Scores dans les plages",     c_scores_in_range()),
        ("Classement décroissant",     c_ordered_desc()),
    ]),

    # ── S06 : Multi-critères complet ─────────────────────────────────────────
    ("S06 — Multi-critères : domaine + dispo + localisation", {
        "mission_text": (
            "Mission en régie de 12 mois pour un chef de projet senior dans le secteur "
            "des assurances. Profil ayant piloté des projets de transformation SI. "
            "Disponibilité sous 1 mois. Poste à Paris, télétravail partiel possible. "
            "Anglais courant requis."
        ),
        "filter_domain":   "assurance",
        "filter_location": "Paris",
        "filter_remote":   "partial",
        "filter_languages": ["fr", "en"]
    }, [
        ("Résultats présents",        c_has_results(1)),
        ("Score domaine activé",       c_domain_score_active()),
        ("Scores dans les plages",     c_scores_in_range()),
        ("Classement décroissant",     c_ordered_desc()),
        ("Pas de champs null",         c_no_null_fields()),
        ("Score top affiché 0-100%",
            lambda o, c, d: (
                all(0 <= x["score"] <= 100 for x in c),
                f"scores : {[x['score'] for x in c[:5]]}"
            )
        ),
    ]),

    # ── S07 : Texte court → rejet 422 ────────────────────────────────────────
    ("S07 — Robustesse : texte trop court rejeté (< 20 chars)", {
        "mission_text": "dev java"
    }, [
    ], 422),

    # ── S08 : Appel répété — stabilité de l'ordre ─────────────────────────────
    ("S08 — Stabilité : même requête lancée deux fois", {
        "mission_text": (
            "Consultant senior en transformation digitale, expert en pilotage de projets "
            "agiles. Bonne connaissance des enjeux data et intelligence artificielle. "
            "Expérience en environnement grands comptes industriels ou télécoms."
        )
    }, [
        ("Résultats présents (run 1)",  c_has_results(3)),
        ("Classement décroissant",      c_ordered_desc()),
    ]),

]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def send_report_email(report_path: str, report: dict):
    """Envoie le rapport par email. Ne fait rien si SMTP_USER est absent."""
    if not SMTP_USER or not SMTP_PASSWORD or not SMTP_RECIPIENTS:
        print(f"  {warn('Email non configuré — définir SMTP_USER/SMTP_PASSWORD/SMTP_RECIPIENTS dans .env')}")
        return

    passed   = report["summary"]["passed"]
    total    = report["summary"]["total"]
    failed   = report["summary"]["failed"]
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    status   = "✅ TOUS RÉUSSIS" if failed == 0 else f"⚠️ {failed} ÉCHEC(S)"
    subject  = f"MatchConsult — Tests {date_str} — {passed}/{total} {status}"

    rows = ""
    for s in report["scenarios"]:
        icon  = "✅" if s["passed"] else "❌"
        color = "#d4edda" if s["passed"] else "#f8d7da"
        top   = s["consultants"][0] if s["consultants"] else None
        top_str = (
            f"{top['name']} — {top['score']}% "
            f"(skills={top['score_detail'].get('skills',0)} "
            f"dom={top['score_detail'].get('domain',0)} "
            f"dispo={top['score_detail'].get('availability',0)})"
        ) if top else "—"
        issues_str = "<br>".join(s["issues"]) if s["issues"] else "—"
        rows += f"""
        <tr style="background:{color}">
          <td style="padding:6px 10px">{icon} {s['name']}</td>
          <td style="padding:6px 10px">{s['duration_s']}s</td>
          <td style="padding:6px 10px">{top_str}</td>
          <td style="padding:6px 10px;color:#c00">{issues_str}</td>
        </tr>"""

    html = f"""<html><body style="font-family:Arial,sans-serif;font-size:14px">
    <h2 style="color:#333">MatchConsult — Rapport de tests</h2>
    <p>Date : <b>{date_str}</b><br>
       API  : <code>{report['api_url']}</code><br>
       CVs chargés : <b>{report['health'].get('cvs_loaded','?')}</b></p>
    <table style="background:#eaf4fb;padding:12px;border-radius:6px;margin-bottom:16px">
      <tr>
        <td style="padding:4px 16px;font-size:22px;font-weight:bold;
                   color:{'#28a745' if failed==0 else '#dc3545'}">
          {passed}/{total} scénarios réussis
        </td>
        <td style="padding:4px 16px;color:#555">
          Durée totale : {report['summary']['duration_total_s']}s
        </td>
      </tr>
    </table>
    <table border="1" cellspacing="0" cellpadding="0"
           style="border-collapse:collapse;width:100%;font-size:13px">
      <thead>
        <tr style="background:#343a40;color:white">
          <th style="padding:8px 10px;text-align:left">Scénario</th>
          <th style="padding:8px 10px;text-align:left">Durée</th>
          <th style="padding:8px 10px;text-align:left">Meilleur résultat</th>
          <th style="padding:8px 10px;text-align:left">Problèmes</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p style="color:#888;font-size:12px;margin-top:20px">
      Rapport JSON complet en pièce jointe.
    </p>
    </body></html>"""

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"MatchConsult Tests <{SMTP_USER}>"
    msg["To"]      = ", ".join(SMTP_RECIPIENTS)
    msg.attach(MIMEText(html, "html", "utf-8"))

    with open(report_path, "rb") as f:
        att = MIMEApplication(f.read(), Name=os.path.basename(report_path))
    att["Content-Disposition"] = f'attachment; filename="{os.path.basename(report_path)}"'
    msg.attach(att)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.sendmail(SMTP_USER, SMTP_RECIPIENTS, msg.as_bytes())
        print(f"  {ok('Email envoyé → ' + ', '.join(SMTP_RECIPIENTS))}")
    except Exception as exc:
        print(f"  {warn(f'Envoi email échoué : {exc}')}")


def save_report(health: dict, exit_code: int) -> str | None:
    """Écrit le rapport JSON dans tests/results/ et retourne le chemin du fichier."""
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(results_dir, f"report_{ts}.json")

    report = {
        "date":        datetime.now().isoformat(),
        "api_url":     BASE_URL,
        "exit_code":   exit_code,
        "summary": {
            "total":   len(all_results),
            "passed":  sum(1 for r in all_results if r.passed),
            "failed":  sum(1 for r in all_results if not r.passed),
            "duration_total_s": round(sum(r.duration for r in all_results), 2),
        },
        "health": health,
        "scenarios": [
            {
                "name":        r.name,
                "passed":      r.passed,
                "duration_s":  round(r.duration, 2),
                "http_status": r.http_status,
                "payload":     r.payload,
                "issues":      r.issues,
                "checks":      r.checks,
                "offer": {
                    "title":            r.offer.get("title", ""),
                    "mission_type":     r.offer.get("mission_type", ""),
                    "duration":         r.offer.get("duration", ""),
                    "domain":           r.offer.get("domain"),
                    "technical_skills": r.offer.get("technical_skills", []),
                    "soft_skills":      r.offer.get("soft_skills", []),
                    "location":         r.offer.get("location"),
                    "remote":           r.offer.get("remote"),
                    "languages":        r.offer.get("languages", []),
                    "client_context":   r.offer.get("client_context", ""),
                },
                "consultants": [
                    {
                        "rank":             i + 1,
                        "name":             c.get("name", ""),
                        "title":            c.get("title", ""),
                        "score":            c.get("score", 0),
                        "status":           c.get("status", ""),
                        "available":        c.get("available", False),
                        "availability_date": c.get("availability_date"),
                        "location":         c.get("location"),
                        "languages":        c.get("languages", []),
                        "domains":          c.get("domains", []),
                        "matched_skills":   c.get("matched_skills", []),
                        "missing_skills":   c.get("missing_skills", []),
                        "explanation":      c.get("explanation", ""),
                        "score_detail":     c.get("score_detail", {}),
                    }
                    for i, c in enumerate(r.consultants)
                ],
            }
            for r in all_results
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Écrase aussi latest.json pour accès rapide
    latest = os.path.join(results_dir, "latest.json")
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return path


def main():
    print(f"\n{BOLD}{'═'*68}{RST}")
    print(f"{BOLD}  MatchConsult — Scénarios de test d'intégration{RST}")
    print(f"  API : {B}{BASE_URL}{RST}")
    print(f"{'═'*68}{RST}")

    # ── Health check ──────────────────────────────────────────────────────────
    print(hdr("  HEALTH CHECK"))
    status, health = http_get("/api/health")
    if status != 200:
        print(f"  {err(f'API inaccessible (HTTP {status}) — lancer docker compose up -d')}")
        save_report(health={}, exit_code=2)
        sys.exit(2)
    n_cvs = health.get("cvs_loaded", 0)
    ready = health.get("model_ready", False)
    print(f"  {ok('API en ligne')}")
    print(f"  {ok(f'{n_cvs} CVs chargés') if n_cvs > 0 else err(f'{n_cvs} CVs — vérifier le répertoire CVs')}")
    print(f"  {ok('Modèle prêt') if ready else err('Modèle non prêt')}")
    if n_cvs == 0 or not ready:
        print(f"\n  {R}Application non prête — tests annulés.{RST}")
        save_report(health=health, exit_code=2)
        sys.exit(2)

    # ── Scénarios ─────────────────────────────────────────────────────────────
    for args in SCENARIOS:
        if len(args) == 4:
            name, payload, checks, expect_http = args
        else:
            name, payload, checks = args
            expect_http = 200
        run_scenario(name, payload, checks, expect_http)

    # ── Rapport final ─────────────────────────────────────────────────────────
    passed  = [r for r in all_results if r.passed]
    failed  = [r for r in all_results if not r.passed]
    total_t = sum(r.duration for r in all_results)

    print(f"\n{BOLD}{'═'*68}{RST}")
    print(f"{BOLD}  Rapport final{RST}")
    print(f"{'═'*68}{RST}")
    print(f"  {G}{BOLD}{len(passed)} scénario(s) réussi(s){RST}  /  {len(all_results)} total")
    if failed:
        print(f"  {R}{BOLD}{len(failed)} scénario(s) en échec :{RST}")
        for r in failed:
            print(f"    {R}✗ {r.name}{RST}")
            for issue in r.issues:
                print(f"        → {issue}")
    print(f"  Durée totale : {total_t:.1f}s")
    print(f"{'═'*68}{RST}\n")

    exit_code = 0 if not failed else 1
    report_path = save_report(health=health, exit_code=exit_code)
    if report_path:
        print(f"  {B}Rapport JSON{RST} : {report_path}")
        print(f"  {B}Dernier rapport{RST} : {os.path.join(os.path.dirname(report_path), 'latest.json')}\n")

    # Chargement du rapport pour l'email
    if report_path:
        with open(report_path, encoding="utf-8") as f:
            report_data = json.load(f)
        send_report_email(report_path, report_data)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
