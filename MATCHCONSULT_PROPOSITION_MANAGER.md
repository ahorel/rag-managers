# Proposition — MatchConsult : outil de matching consultant-mission

## Contexte

MatchConsult est un outil à destination des **équipes commerciales ESN**.
Un commercial colle une fiche de poste → l'IA reformule l'offre et classe automatiquement
les consultants disponibles par pertinence, avec une explication pour chacun.

Objectif : réduire le temps de sélection des profils et améliorer la qualité des propositions.

---

## Ce que fait l'outil

```
Commercial (navigateur)
         ↓  colle une fiche de poste
 ┌───────────────────────────────────────┐
 │  Interface web React                  │
 │  → reformulation de l'offre par l'IA  │
 │  → liste des consultants classés      │
 │     avec score et explication         │
 └──────────────┬────────────────────────┘
                ↓  appel sécurisé HTTPS
           Groq API (cloud)
           Llama 3.1 8B — open-source
           gratuit jusqu'à 130 analyses/jour
```

En pratique, pour chaque analyse :
1. L'IA restructure la fiche de poste en JSON (titre, compétences, contexte client)
2. Le système compare l'offre à tous les CVs disponibles par similarité sémantique
3. L'IA génère une phrase d'explication par consultant (ex : *"Profil senior React, idéal pour ce contexte bancaire"*)

---

## Choix technologiques

| Composant | Technologie | Pourquoi ce choix |
|-----------|-------------|-------------------|
| Interface | React 18 + TypeScript | Standard industriel, performant, responsive |
| Backend | FastAPI (Python) | Rapide, idéal pour les APIs IA |
| Modèle IA | Llama 3.1 8B via Groq | Open-source, multilingue FR/EN, gratuit, < 1 s |
| Matching | Similarité cosinus (NumPy) | 100 % local, aucune donnée CV envoyée en cloud |
| Parsing CV | pdfplumber + python-docx | Lit PDF et Word sans conversion |
| Serveur | Hetzner (Allemagne) | RGPD, fiable, moins cher qu'AWS/Azure |

> Les CVs et données consultants **ne quittent jamais le serveur**.
> Seule la fiche de poste est envoyée à Groq pour reformulation.

---

## Gestion des données

| Rôle | Qui | Action |
|------|-----|--------|
| Administrateur | 1 dev désigné | Dépose les CVs sur le serveur, redémarre si besoin |
| Commercial | Toute l'équipe | Utilise l'interface web — ne touche pas au serveur |

Les CVs (PDF ou DOCX) sont déposés dans un dossier sur le serveur.
Ils sont vectorisés automatiquement au démarrage. Aucune base de données externe.

---

## Coût mensuel estimé — 10 commerciaux, 50 analyses/jour

| Poste | Coût |
|-------|------|
| Serveur Hetzner CX22 (2 vCPU, 4 Go RAM, Allemagne) | **3,79 €/mois** |
| API Groq — Llama 3.1 8B (50 analyses/jour) | **0 € (free tier)** |
| **Total** | **< 4 €/mois** |

Le free tier Groq couvre jusqu'à **130 analyses/jour** sans aucun frais.
Au-delà, le coût LLM reste marginal : ~0,70 € pour 1 500 analyses/mois.

---

## Ce que l'équipe peut faire avec cet outil

- Coller n'importe quelle fiche de poste → résultat en moins de 5 secondes
- Voir les consultants classés par score de pertinence (0-100)
- Lire les compétences matchées, manquantes et l'explication IA
- Accéder depuis n'importe quel navigateur, sans installation

---

*Mise en place estimée : 1 journée développeur. Aucune maintenance particulière ensuite.*
*Ajouter un consultant : déposer son CV dans le dossier dédié + redémarrer le service.*
