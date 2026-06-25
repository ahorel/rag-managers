# Corrections RAG — V2.6

**Problème observé :** requête "ingénieur IA senior / Reinforcement learning / LLM / secteur bancaire"
retournait un **Product Owner** en position #1 (52%) et un **Consultant AMOA** en #2 (49%).

**Cause racine :** un profil sans compétences techniques mais en intercontrat + dans le bon domaine
accumulait assez de points (domaine 25 + dispo 15 + localisation 5 = 45) pour écraser un ingénieur IA
hors-domaine avec un bon score compétences.

---

## 1. Chunking sémantique par paragraphes — `embeddings.py`

### Avant
- Chaque CV → **1 seul vecteur** calculé sur les 6 000 premiers caractères
- Un CV long ou polyvalent produisait un vecteur "moyen" qui diluait les compétences de pointe
- Un expert RL dont les missions datent de 2020 mais sont en milieu de CV = mal retrouvé

### Après
- Chaque CV → **N vecteurs** (1 par section/paragraphe naturel)
- Fonction `_make_semantic_chunks()` : split sur `\n{2,}`, regroupement jusqu'à 2 000 chars,
  fusion des blocs trop courts (< 300 chars), découpe fixe avec overlap 200 chars si un bloc
  dépasse 2 000 chars
- `rank_by_similarity()` : recherche sur **200 hits** (au lieu de 50) puis **max-pool par cv_id**
  → on garde le chunk le plus pertinent par CV
- Le champ `text` du payload reste le **texte complet** pour le keyword matching

```python
# Exemple : CV de 8 000 chars → 5 chunks sémantiques
Chunk 1 → "Expérience CGI : Manager IA, 80 ingénieurs, blueprints RAG..."
Chunk 2 → "Expérience K-Lagan : RL hiérarchique, GANs, LLM assurance..."
Chunk 3 → "Expérience Avisto : vision 3D, MMDetection3D, Kalman..."
Chunk 4 → "Compétences : LangGraph, CrewAI, PyTorch, FAISS..."
Chunk 5 → "Formation : PhD IP Paris, certifications DeepLearning.AI..."
```

---

## 2. Rééquilibrage des poids — `matcher.py`

### Avant

| Composante  | Max | Ratio sur 100 |
|-------------|-----|---------------|
| Compétences | 55  | 58%           |
| Domaine     | 25  | 26%           |
| Disponibil. | 15  | 16%           |
| Localisation| 5   | 5%            |

→ Un PO finance intercontrat Paris : 7 + 25 + 15 + 5 = **52%**

### Après

| Composante  | Max | Ratio sur 100 |
|-------------|-----|---------------|
| Compétences | 65  | 66%           |
| Domaine     | 15  | 15%           |
| Disponibil. | 15  | 15%           |
| Localisation| 5   | 5%            |

→ Le même PO finance intercontrat Paris : 7 + 15 + 15 + 5 = **42%**
→ Un ingénieur IA hors-domaine : 45 + 0 + 15 + 5 = **65%** → correctement devant

**Calibration cosinus ajustée** : `_COSINE_CEIL` 0.85 → 0.90
(les chunks sémantiques étant plus focalisés, les scores cosinus sont naturellement plus élevés)

---

## 3. Seuil minimum de compétences — `matcher.py`

```python
_MIN_SKILLS_SCORE = 15  # sur 65
```

Tout profil dont le score compétences est inférieur à 15/65 (~23%) est **exclu des résultats**,
quelle que soit sa disponibilité ou son domaine.

- Product Owner avec skills = 7 → exclu ✓
- Consultant AMOA avec skills = 10 → exclu ✓
- Ingénieur IA avec skills = 40 → retenu ✓

---

## 4. Keyword matching amélioré — synonymes + frontières de mots — `matcher.py`

### Problème
- `"rl" in cv_lower` matchait "url", "parallel", "rl" → faux positifs ou faux négatifs
- "Reinforcement learning" dans l'offre ne matchait pas "RL" dans le CV

### Après

**`_keyword_in_text()`** : utilise `\b` (word boundary) pour éviter les faux positifs :
```python
re.search(r"\b" + re.escape(keyword.lower()) + r"\b", cv_lower)
```

**`_SKILL_SYNONYMS`** : dictionnaire de correspondances bidirectionnelles :
```python
"reinforcement learning" → ["rl", "apprentissage par renforcement"]
"llm"                   → ["large language model", "modèle de langage", "gpt"]
"machine learning"      → ["ml", "apprentissage automatique"]
"nlp"                   → ["natural language processing", "traitement du langage naturel"]
"rag"                   → ["retrieval augmented generation"]
"mlops"                 → ["ml ops", "machine learning operations"]
...
```

Une compétence est considérée **matchée** si elle-même OU un de ses synonymes est trouvé dans le CV.

---

## Fichiers modifiés

| Fichier | Changements |
|---------|-------------|
| `backend/app/services/embeddings.py` | `_make_semantic_chunks()`, chunking dans `load_cvs()`, max-pool dans `rank_by_similarity()`, compteur CVs uniques |
| `backend/app/services/matcher.py` | `_SKILL_SYNONYMS`, `_expand_skills()`, `_keyword_in_text()`, `_score_domain()` 25→15, `_max_possible_score()` 55→65 / 25→15, seuil `_MIN_SKILLS_SCORE`, `_COSINE_CEIL` 0.85→0.90 |

---

## Déploiement sur VPS OVH

```bash
# 1. Sur la machine locale — pousser la branche
git add backend/app/services/embeddings.py backend/app/services/matcher.py
git commit -m "feat: RAG V2.6 — chunking sémantique + rééquilibrage scoring + synonymes"
git push origin ovh-rag-managers

# 2. Sur le VPS (51.83.44.48)
ssh ubuntu@51.83.44.48
cd /opt/rag-managers           # ou le chemin du repo sur le VPS
git pull origin ovh-rag-managers

# 3. Redémarrer uniquement le backend (réindexation automatique au démarrage)
docker compose restart backend

# 4. Surveiller les logs — vérifier le chunking et l'indexation
docker compose logs -f backend | grep -E "(chunk|Indexed|matcher)"

# Attendre le message :
# "Indexed N CVs → M chunks into Qdrant (matchconsult_cvs)."
# puis tester une requête "ingénieur IA senior RL LLM banque"
```

> **Note :** Le backend est indisponible ~60–90s pendant la réindexation (comportement normal,
> inchangé). Le healthcheck Docker attend `start_period: 120s`.

---

*Corrections appliquées le 2026-06-25 — branche `ovh-rag-managers`*
