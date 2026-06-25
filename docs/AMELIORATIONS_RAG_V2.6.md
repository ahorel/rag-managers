# Améliorations RAG — V2.6

**Date :** 2026-06-25
**Branche :** `ovh-rag-managers`
**Commits :** `8d1f530`, `5ac6e6c`

---

## Problème observé

Requête : *"ingénieur IA senior / Reinforcement Learning / LLM / secteur bancaire"*

| Position | Profil | Score | Cause |
|----------|--------|-------|-------|
| #1 | **Product Owner** finance | 52% | Domaine finance (25 pts) + intercontrat (15 pts) écrasaient les compétences (7 pts) |
| #2 | **Consultant AMOA** | 49% | Même phénomène |

Un profil sans compétences techniques classait premier uniquement grâce à sa disponibilité et son domaine.

---

## 1. Chunking sémantique par paragraphes

**Fichier :** `backend/app/services/embeddings.py`

### Avant
- 1 seul vecteur par CV, calculé sur les **6 000 premiers caractères**
- Un CV de senior polyvalent (10+ ans, plusieurs domaines) produisait un vecteur "moyen" qui diluait ses compétences de pointe
- Les compétences situées après le premier tiers du CV étaient invisibles pour Qdrant

### Après
- Chaque CV est découpé en **N chunks sémantiques** par la fonction `_make_semantic_chunks()`
- Découpage sur les **sauts de paragraphe naturels** (`\n\n`) — chaque section reste cohérente
- Taille cible : 2 000 caractères (~512 tokens) avec overlap de 200 caractères sur les blocs géants
- Les chunks trop courts (< 300 chars) sont fusionnés avec le suivant
- **Résultat sur 25 CVs : 125 chunks indexés** (moyenne 5 chunks/CV)

```
Exemple CV senior (8 000 chars) → 5 chunks
  Chunk 1 → En-tête + résumé profil
  Chunk 2 → Expérience CGI (management IA, 80 ingénieurs)
  Chunk 3 → Expérience K-Lagan (RL hiérarchique, LLM assurance)
  Chunk 4 → Expérience Avisto (vision 3D, MMDetection3D)
  Chunk 5 → Compétences + Formation + Certifications
```

### Max-pool au retrieval
- Qdrant est interrogé sur **200 hits** (au lieu de 50)
- Déduplication par `cv_id` : on garde le **meilleur chunk** par CV
- Un ingénieur senior dont les compétences RL datent de 2020 mais sont en page 3 n'est plus pénalisé

---

## 2. Rééquilibrage des poids de scoring

**Fichier :** `backend/app/services/matcher.py`

### Avant

| Composante | Max | Part du score |
|------------|-----|---------------|
| Compétences | 55 pts | 58% |
| Domaine | **25 pts** | **26%** |
| Disponibilité | 15 pts | 16% |
| Localisation | 5 pts | 5% |

→ Product Owner finance intercontrat Paris : `7 + 25 + 15 + 5 = 52%`

### Après

| Composante | Max | Part du score |
|------------|-----|---------------|
| Compétences | **65 pts** | **66%** |
| Domaine | **15 pts** | **15%** |
| Disponibilité | 15 pts | 15% |
| Localisation | 5 pts | 5% |

→ Product Owner finance intercontrat Paris : `15 + 15 + 15 + 5 = 50%` → **exclu** (sous le seuil)
→ Ingénieur IA hors-domaine : `45 + 0 + 15 + 5 = 65%` → correctement en tête

---

## 3. Seuil minimum de compétences

**Fichier :** `backend/app/services/matcher.py`

```python
_MIN_SKILLS_SCORE = 22  # sur 65 (~34%)
```

Tout profil dont le **score compétences est inférieur à 22/65** est exclu des résultats, quelle que soit sa disponibilité ou son domaine sectoriel.

| Profil | Skills | Résultat |
|--------|--------|----------|
| Product Owner finance | 15/65 | **Exclu** ✓ |
| Consultant AMOA | 23/65 | Retenu (à surveiller) |
| Ingénieur IA senior | 40+/65 | Retenu ✓ |

> Le seuil a été ajusté de 15 → 22 après le premier test : le PO atteignait exactement 15
> grâce aux termes génériques "IA" et "ML" présents dans son CV de contexte.

---

## 4. Keyword matching — synonymes + frontières de mots

**Fichier :** `backend/app/services/matcher.py`

### Problèmes résolus

| Avant | Après |
|-------|-------|
| `"rl" in cv_text` matchait "url", "parallel" | `\b rl \b` — frontière de mot stricte |
| "Reinforcement Learning" dans l'offre ne matchait pas "RL" dans le CV | Synonymes bidirectionnels |
| "LLM" ne matchait pas "large language model" | Couvert par `_SKILL_SYNONYMS` |

### Dictionnaire de synonymes

```python
"reinforcement learning" ↔ ["rl", "apprentissage par renforcement"]
"llm"                   ↔ ["large language model", "modèle de langage", "gpt"]
"machine learning"      ↔ ["ml", "apprentissage automatique"]
"nlp"                   ↔ ["natural language processing", "traitement du langage naturel"]
"rag"                   ↔ ["retrieval augmented generation"]
"mlops"                 ↔ ["ml ops", "machine learning operations"]
"generative ai"         ↔ ["ia générative", "gen ai", "genai"]
"deep learning"         ↔ ["dl", "apprentissage profond", "réseau de neurones"]
"computer vision"       ↔ ["vision par ordinateur", "vision artificielle"]
```

---

## Résultats avant / après

### Requête : "ingénieur IA senior / Reinforcement Learning / LLM / secteur bancaire"

| Position | Avant | Score | Après | Score |
|----------|-------|-------|-------|-------|
| #1 | Product Owner ❌ | 52% | **Profil technique IA** ✓ | ~42% |
| #2 | Consultant AMOA ❌ | 49% | **Profil technique IA** ✓ | ~41% |
| #3+ | Profils techniques | 38–37% | Profils techniques | 40–38% |

Le Product Owner est **exclu** du top 10. Les scores globaux sont plus bas mais plus honnêtes — ils reflètent la difficulté réelle à trouver un profil RL/LLM en finance disponible immédiatement.

---

## Fichiers modifiés

| Fichier | Changements |
|---------|-------------|
| `backend/app/services/embeddings.py` | `_make_semantic_chunks()`, N chunks/CV dans `load_cvs()`, max-pool dans `rank_by_similarity()` (limit 200), compteur CVs uniques |
| `backend/app/services/matcher.py` | `_SKILL_SYNONYMS`, `_keyword_in_text()` (word boundary), `_score_domain()` 25→15, `_max_possible_score()` 55→65 / 25→15, `_MIN_SKILLS_SCORE = 22`, `_COSINE_CEIL` 0.85→0.90 |

---

## Déploiement

```bash
# Sur le VPS (51.83.44.48)
git pull origin ovh-rag-managers

# V2.6 initial (chunking + scoring) — rebuild obligatoire
docker compose build --no-cache backend
docker compose up -d

# Ajustement seuil 15→22 — restart suffit (pas de rebuild)
docker compose restart backend
```

**Signal de confirmation :**
```
Indexed 25 CVs → 125 chunks into Qdrant (matchconsult_cvs).
```
