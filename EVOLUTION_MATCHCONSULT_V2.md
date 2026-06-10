# MatchConsult V2 — Document d'évolution
**Date :** 10 juin 2026  
**Origine :** Échange Antoine Jover / Arthur Horel

---

## Contexte et besoin

La V1 fait du matching CV ↔ fiche de poste par similarité vectorielle.  
L'évolution porte sur **trois axes** :

1. **Expression de besoin → fiche de poste automatique** (LLM)
2. **Enrichissement des critères de sélection** (disponibilité, localisation, langue, domaine)
3. **Envoi automatisé au pôle staffing**

---

## Ce que la V1 fait déjà (ne pas retoucher)

| Fonctionnalité | Statut |
|----------------|--------|
| Indexation CVs PDF/DOCX dans Qdrant | ✅ Opérationnel |
| Reformulation fiche de poste (LLM) | ✅ Opérationnel |
| Matching vectoriel cosinus | ✅ Opérationnel |
| Explications IA par consultant | ✅ Opérationnel |
| Score 0-100 + skills matchées/manquantes | ✅ Opérationnel |
| Interface web React | ✅ Opérationnel |
| Filtre disponibilité (booléen) | ✅ Partiel — à enrichir |

---

## Évolution 1 — Expression de besoin → Fiche de poste

### Problème
Le commercial reçoit un email client non structuré.  
Aujourd'hui il recopie manuellement les infos dans le formulaire.

### Solution
Un nouvel onglet **"Nouvelle mission"** dans l'interface avec deux étapes :

**Étape A — Coller l'email brut**
```
[ Zone de texte : coller l'email client tel quel ]

Exemple d'email entrant :
"Bonjour, nous cherchons un expert Salesforce CRM
pour une mission de 6 mois à Lyon, démarrage début juillet,
anglais obligatoire, contexte assurance vie..."

→ Bouton "Générer la fiche de poste"
```

**Étape B — Fiche de poste générée (éditable)**
```
Titre             : [Expert Salesforce CRM]       ← modifiable
Type de mission   : [Régie]                       ← modifiable
Durée             : [6 mois]                      ← modifiable
Date de démarrage : [01/07/2026]                  ← modifiable
Localisation      : [Lyon]                        ← modifiable
Remote            : [Partiel]                     ← modifiable
Langue requise    : [Français + Anglais]          ← modifiable
Domaine métier    : [Assurance]                   ← modifiable
Compétences tech  : [Salesforce, CRM, ...]        ← modifiable
Compétences soft  : [Autonomie, Client...]        ← modifiable
Contexte client   : [Assurance vie, PMO...]       ← modifiable

→ Bouton "Lancer le matching"
```

### Prompt LLM à ajouter dans `claude_service.py`
```python
PROMPT_EXPRESSION_TO_OFFER = """
Tu es un expert en recrutement ESN. À partir de cette expression de besoin,
génère une fiche de poste structurée en JSON valide.

Expression de besoin :
{raw_text}

JSON attendu :
{
  "title": "...",
  "mission_type": "Régie|Forfait|CDI|CDD",
  "duration": "...",
  "start_date": "JJ/MM/AAAA ou 'dès que possible'",
  "location": "ville ou 'Remote'",
  "remote": "full|partial|none",
  "languages": ["fr", "en", ...],
  "domain": "bancaire|assurance|telecom|retail|industrie|secteur_public|autre",
  "technical_skills": [...],
  "soft_skills": [...],
  "client_context": "..."
}
"""
```

---

## Évolution 2 — Enrichissement des critères consultant

### Problème
Le fichier `consultants_meta.json` ne contient que `name`, `title`, `available` (booléen).  
Impossible de filtrer par date de disponibilité, localisation, langue ou domaine.

### Nouveau modèle `consultants_meta.json`

```json
{
  "jean_dupont": {
    "name": "Jean Dupont",
    "title": "Architecte Cloud Senior",
    "email": "jean.dupont@orange.com",
    "status": "intercontrat",
    "available": true,
    "availability_date": "2026-06-15",
    "location": "Paris",
    "remote": "partial",
    "languages": ["fr", "en"],
    "domains": ["bancaire", "assurance"],
    "tjm": 650
  },
  "marie_martin": {
    "name": "Marie Martin",
    "title": "Chef de Projet MOA",
    "email": "marie.martin@orange.com",
    "status": "en_mission",
    "available": false,
    "availability_date": "2026-08-01",
    "location": "Lyon",
    "remote": "full",
    "languages": ["fr"],
    "domains": ["telecom", "secteur_public"],
    "tjm": 580
  }
}
```

**Champs ajoutés :**

| Champ | Type | Valeurs possibles |
|-------|------|-------------------|
| `email` | string | email Orange du consultant |
| `status` | string | `intercontrat` / `en_mission` / `preavailable` |
| `availability_date` | string | `"AAAA-MM-JJ"` — date de dispo réelle |
| `location` | string | Ville |
| `remote` | string | `full` / `partial` / `none` |
| `languages` | list | `["fr", "en", "de", "es", ...]` |
| `domains` | list | secteurs métier travaillés |
| `tjm` | int | optionnel — TJM indicatif |

### Extraction automatique depuis le CV (optionnel)

Si les métadonnées ne sont pas renseignées manuellement, le LLM peut les extraire du texte du CV au moment de l'indexation :

```python
# Dans embeddings.py — à ajouter à load_cvs()
async def extract_meta_from_cv(cv_text: str) -> dict:
    prompt = """
    Extrais depuis ce CV :
    - Les langues parlées
    - Les domaines métier (bancaire, assurance, telecom, etc.)
    - La localisation (ville)
    - Le TJM si mentionné
    Réponds en JSON valide uniquement.
    CV : {cv_text}
    """
```

---

## Évolution 3 — Matching multi-critères

### Nouveau scoring

Le score actuel = similarité cosinus * 100 (uniquement sur les compétences textuelles).

**Nouveau score composé :**

```
Score final = 
  0.55 × score_skills (cosinus embedding — déjà en place)
+ 0.20 × score_disponibilité
+ 0.15 × score_domaine
+ 0.10 × score_localisation_langue
```

**Calcul score_disponibilité :**
```python
def score_disponibilite(availability_date: str, mission_start: str) -> float:
    # Disponible avant ou à la date de démarrage = 1.0
    # Disponible dans les 2 semaines après = 0.7
    # Disponible dans le mois = 0.4
    # Disponible après = 0.1
    # En mission sans date = 0.0
```

**Calcul score_domaine :**
```python
def score_domaine(consultant_domains: list, mission_domain: str) -> float:
    # Domaine exact = 1.0
    # Domaine similaire (ex: bancaire/assurance) = 0.6
    # Hors domaine = 0.0
```

### Nouveaux filtres dans l'interface

```
Filtres dans MissionInput.tsx (options avancées) :
☐ Intercontrat uniquement
☐ Disponible avant : [date picker]
☐ Localisation : [Paris / Lyon / Remote / Toutes]
☐ Langue requise : [FR] [EN] [DE] [ES]
☐ Domaine métier : [dropdown]
```

### Nouveau champ `ConsultantMatch` (Pydantic)

```python
class ConsultantMatch(BaseModel):
    # Existant
    id: str
    name: str
    title: str
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: str
    available: bool
    cv_filename: str
    # Nouveau
    availability_date: str | None
    location: str | None
    remote: str | None
    languages: list[str]
    domains: list[str]
    status: str | None  # intercontrat / en_mission / preavailable
    score_detail: ScoreDetail | None

class ScoreDetail(BaseModel):
    skills: int       # contribution skills
    disponibilite: int
    domaine: int
    localisation: int
```

---

## Évolution 4 — Envoi au pôle staffing

### Flux cible

```
ResultsPage → Bouton "Envoyer au staffing"
    ↓
Modal de confirmation :
  - Liste des consultants sélectionnés (checkboxes)
  - Email destinataire : [staffing@orange.com]
  - Message libre optionnel
  - Bouton "Envoyer"
    ↓
Backend POST /api/send-staffing
  - Génère un email HTML avec :
    * Fiche de poste reformulée
    * Tableau des candidats (nom, titre, score, dispo, localisation)
    * Lien vers chaque CV
  - Envoi via SMTP Orange (ou simple export PDF)
```

### Alternative simple (phase 1) — Export sans envoi email

```
Bouton "Exporter la shortlist" → génère un fichier Markdown ou HTML
avec la liste des candidats, leurs scores, et les CVs à télécharger.
```

Cela ne nécessite pas de configuration SMTP et peut être fait immédiatement.

---

## Nouveau flux utilisateur complet (V2)

```
┌─────────────────────────────────────────────────┐
│  ONGLET 1 : Nouvelle mission (nouveau)          │
│                                                 │
│  [Coller email client]                         │
│       ↓                                         │
│  [Fiche de poste générée — éditable]           │
│       ↓                                         │
│  [Lancer le matching]                          │
└─────────────────┬───────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────┐
│  ONGLET 2 : Résultats (enrichi)                │
│                                                 │
│  Filtres : dispo / remote / langue / domaine   │
│                                                 │
│  ┌─────────────┐  ┌────────────────────────┐   │
│  │Offre        │  │Consultants              │   │
│  │reformulée   │  │[✓] Jean Dupont    92%  │   │
│  │             │  │    Paris | EN | Dispo  │   │
│  │             │  │    Bancaire ✓          │   │
│  │             │  │                        │   │
│  │             │  │[✓] Marie Martin   78%  │   │
│  │             │  │    Remote | FR | 01/08 │   │
│  └─────────────┘  └────────────────────────┘   │
│                                                 │
│  [Envoyer au staffing] [Exporter PDF]          │
└─────────────────────────────────────────────────┘
```

---

## Plan d'implémentation — Par priorité

### Phase 1 — Rapide (3-5 jours)
*Sans toucher à l'architecture existante*

| Tâche | Fichier | Effort |
|-------|---------|--------|
| Enrichir `consultants_meta.json` avec les nouveaux champs | `data/consultants_meta.json` | 1h |
| Passer les métadonnées enrichies dans le payload Qdrant | `embeddings.py` | 2h |
| Afficher localisation, langue, statut dans `ConsultantCard` | `ConsultantCard.tsx` | 3h |
| Ajouter filtres dispo/remote/langue dans l'UI | `MissionInput.tsx` | 4h |
| Transmettre les filtres au backend via `AnalyzeRequest` | `models.py` + `matcher.py` | 3h |

**Résultat Phase 1 :** Même matching mais avec filtres et affichage enrichi.

---

### Phase 2 — Moyenne (1 semaine)

| Tâche | Fichier | Effort |
|-------|---------|--------|
| Nouveau prompt LLM expression de besoin → fiche de poste | `claude_service.py` | 3h |
| Nouvelle route `POST /api/generate-offer` | `mission.py` | 2h |
| Nouveau composant `ExpressionBesoin.tsx` (formulaire étape A) | `components/` | 4h |
| Page édition fiche de poste générée (étape B) | `components/` | 5h |
| Score composé multi-critères | `matcher.py` | 4h |

**Résultat Phase 2 :** Flux complet email → fiche de poste → matching.

---

### Phase 3 — Export et envoi (3 jours)

| Tâche | Fichier | Effort |
|-------|---------|--------|
| Export shortlist en HTML/PDF | `routes/mission.py` | 4h |
| Bouton "Envoyer au staffing" + modal sélection | `ResultsPage.tsx` | 3h |
| Route `POST /api/export-shortlist` | `mission.py` | 3h |
| Config SMTP (optionnel — peut rester export) | `config.py` | 2h |

**Résultat Phase 3 :** Shortlist exportable ou envoyée directement.

---

## Ce qu'on n'automatise PAS (pour l'instant)

| Fonctionnalité | Raison |
|----------------|--------|
| Lecture directe des emails entrants | Nécessite accès boite mail Orange — complexité RGPD |
| Mise à jour auto de la disponibilité | Les consultants doivent la déclarer eux-mêmes |
| Envoi automatique sans validation | Risque d'envoyer sans relecture commerciale |
| Notation historique des missions | Nécessite une base de données persistante (hors scope V2) |

---

## Questions ouvertes avant implémentation

1. **Qui renseigne les métadonnées consultant ?** Manager RH ? Commercial ? Auto-déclaration consultant ?
2. **Le pôle staffing** — quel est leur email ? Quel format préfèrent-ils (email HTML / PDF / lien web) ?
3. **Domaines métier** — quelle liste exhaustive pour Orange Business ? (bancaire, assurance, telecom, energie, retail, secteur_public, industrie, santé ?)
4. **TJM** — à inclure dans la sélection ou confidentiel ?
5. **Périmètre géographique** — France uniquement ou international ?

---

## Résumé des fichiers à créer/modifier

### Backend
```
backend/app/models.py              → Enrichir ConsultantMatch, AnalyzeRequest
backend/app/services/embeddings.py → Stocker nouveaux champs dans Qdrant payload
backend/app/services/matcher.py    → Score multi-critères + filtres
backend/app/services/claude_service.py → Nouveau prompt expression de besoin
backend/app/routes/mission.py      → Nouvelles routes generate-offer + export
backend/data/consultants_meta.json → Enrichir avec nouveaux champs
```

### Frontend
```
frontend/src/types/index.ts         → Nouveaux types TypeScript
frontend/src/components/ExpressionBesoin.tsx  → Nouveau composant (étape A)
frontend/src/components/OfferEditor.tsx       → Nouveau composant (étape B)
frontend/src/components/ConsultantCard.tsx    → Afficher localisation/langue/dispo
frontend/src/components/ResultsPage.tsx       → Filtres + bouton export
frontend/src/components/MissionInput.tsx      → Nouveaux filtres avancés
frontend/src/api/client.ts                    → Nouvelles routes API
```
