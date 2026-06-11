# Anomalie — Incohérence du score de matching RAG

**Fichier impacté :** `backend/app/services/matcher.py`
**Date détection :** 2026-06-11
**Signalement :** Manager (test manuel — "dev java sénior" → Laurent Sainton à 36%)
**Statut :** Corrigé (commit à pousser sur le serveur)

---

## Symptôme observé

Lors d'une recherche simple **"dev java sénior"**, le consultant **Laurent Sainton** (20 ans d'expérience Java) ressortait avec un score de **36% de correspondance**, ce qui est manifestement incohérent avec son profil.

D'autres incohérences similaires pouvaient apparaître selon le type de requête :
- Requête sans domaine → tous les scores plafonnaient artificiellement bas
- Consultant en_mission → score de 0 pour disponibilité même si la question n'était pas prioritaire
- Consultant avec toutes les compétences explicitement dans le CV → pas avantagé face à un profil sémantiquement proche mais sans les mots-clés exacts

---

## Analyse des causes racines

### Cause 1 — Mauvaise calibration de la similarité cosinus

**Localisation :** `matcher.py`, ligne `skills_score = max(0, min(55, round(r["score"] * 55)))`

**Problème :**
Le modèle d'embeddings utilisé (`paraphrase-multilingual-MiniLM-L12-v2`) retourne des similarités cosinus qui, pour des textes réels (CVs complets), se situent dans la plage **0,35 → 0,85**. Le modèle n'atteint jamais 1,0 sur des documents longs car l'embedding capture la sémantique globale d'un texte, pas une correspondance mot à mot.

La formule `score × 55` traitait la plage `0,0 → 1,0` comme si elle était atteignable, ce qui signifiait :
- Un cosinus de **0,65** (bonne correspondance) donnait `round(0.65 × 55) = 36/55`
- Le **maximum jamais atteignable** pour un consultant parfaitement correspondant était `round(0.85 × 55) = 46/55`
- Un consultant non pertinent (cosinus 0,35) obtenait `round(0.35 × 55) = 19/55` au lieu de 0

**Illustration :**

| Cosinus brut | Signification réelle | Score avant correction | Score après correction |
|---|---|---|---|
| 0,85 | Correspondance quasi parfaite | 46/55 (84%) | 55/55 (100%) |
| 0,65 | Bonne correspondance | 36/55 (65%) | 42/55 (76%) |
| 0,45 | Correspondance moyenne | 25/55 (45%) | 14/55 (25%) |
| 0,30 | Non pertinent | 16/55 (29%) | 0/55 (0%) |

**Correction appliquée :**
```python
_COSINE_FLOOR = 0.25
_COSINE_CEIL  = 0.85

def _calibrate_cosine(raw: float) -> float:
    return max(0.0, min(1.0, (raw - _COSINE_FLOOR) / (_COSINE_CEIL - _COSINE_FLOOR)))
```
La plage utile réelle est ramenée à `0,0 → 1,0` avant multiplication par 55.

---

### Cause 2 — Le matching direct de mots-clés n'influençait pas le score

**Localisation :** `matcher.py`, fonction `_skill_match()`

**Problème :**
La fonction `_skill_match` détectait correctement si des compétences comme "Java" étaient présentes littéralement dans le CV, mais son résultat était utilisé **uniquement pour l'affichage** (listes `matched_skills` / `missing_skills` dans l'UI). Il n'avait **aucun impact sur le score numérique**.

Conséquence : un consultant qui a "Java" 15 fois dans son CV et un consultant qui ne l'a jamais pouvaient obtenir le même `skills_score` si leurs embeddings globaux étaient proches sémantiquement.

L'embedding d'un CV complet capture la sémantique de l'ensemble de la carrière (domaines, contexte client, méthodes de travail…), pas uniquement les technologies maîtrisées. Cela provoque une **dilution du signal technique** pour les profils expérimentés ayant des CVs riches et variés.

**Correction appliquée :**
Scoring hybride : **70% embedding sémantique + 30% matching direct des mots-clés**.
```python
def _keyword_ratio(offer_skills: list[str], cv_text: str) -> float:
    if not offer_skills:
        return 0.0
    cv_lower = cv_text.lower()
    hits = sum(1 for s in offer_skills if s.lower() in cv_lower)
    return hits / len(offer_skills)

# Dans analyze_and_match :
calibrated   = _calibrate_cosine(r["score"])
kw_ratio     = _keyword_ratio(offer.technical_skills, r["text"])
hybrid       = calibrated * 0.70 + kw_ratio * 0.30
skills_score = max(0, min(55, round(hybrid * 55)))
```

Pour Laurent Sainton avec "Java" présent dans le CV :
- `calibrated = 0.67` (cosinus 0,65 recalibré)
- `kw_ratio = 1.0` (Java trouvé)
- `hybrid = 0.67 × 0.70 + 1.0 × 0.30 = 0.769`
- `skills_score = round(0.769 × 55) = 42/55`

---

### Cause 3 — Dénominateur fixe à 100 même quand des composantes sont inapplicables

**Localisation :** `matcher.py`, calcul du `total` et affichage du score

**Problème :**
Le score total était calculé sur 100 points, décomposés en :
- Compétences : 55 pts
- Domaine : 25 pts
- Disponibilité : 15 pts
- Localisation : 5 pts

Quand une recherche ne précisait ni domaine, ni localisation, les composantes correspondantes retournaient **0**. Mais le score restait affiché sur 100.

Pour la requête "dev java sénior" (sans domaine, sans localisation) :
- Score max atteignable = 55 (skills) + 15 (dispo) = **70/100**
- Laurent Sainton, `en_mission` sans date de fin : score max = **55/100**
- Son score réel de 36/100 représentait donc **65% de ce qui était mesurable**, mais était affiché comme 36%

C'était une distorsion de représentation : le score apparent ne reflétait pas la pertinence réelle du consultant par rapport aux critères actifs.

**Correction appliquée :**
Le score affiché est normalisé sur le **maximum atteignable** selon les critères effectivement présents dans la requête.
```python
def _max_possible_score(eff_domain, eff_location, eff_remote) -> int:
    max_score = 55  # compétences : toujours présentes
    if eff_domain:
        max_score += 25
    if eff_location or eff_remote:
        max_score += 5
    max_score += 15  # disponibilité : toujours dans le dénominateur (critère métier)
    return max_score

display_score = min(100, round(raw_total * 100 / max_possible))
```

---

### Cause 4 — Pénalité excessive pour les consultants `en_mission` sans date de fin

**Localisation :** `matcher.py`, fonction `_score_availability()`

**Problème :**
Un consultant `en_mission` sans date de disponibilité connue retournait un score de **0 pts** sur 15. Cette logique est pertinente quand la disponibilité est un critère prioritaire (ex : "besoin urgent dans 2 semaines"), mais elle était appliquée systématiquement.

Pour une requête comme "dev java sénior" où l'urgence n'est pas exprimée, pénaliser à 0 un expert disponible dans 3 mois introduit un biais en faveur de consultants moins qualifiés mais immédiatement libres.

**Correction appliquée :**
Les consultants `en_mission` sans date connue reçoivent désormais **3 pts** (valeur neutre minimale) au lieu de 0. Ils restent défavorisés par rapport aux ressources intercontrat, mais ne sont plus totalement exclus du scoring.
```python
# Avant (ligne finale de _score_availability) :
return 0

# Après :
return 3  # en_mission sans date : ressource pool, score neutre minimum
```

---

## Impact chiffré sur le cas Laurent Sainton

| Composante | Avant corrections | Après corrections |
|---|---|---|
| Skills (cosinus 0,65, Java présent) | 36/55 | 42/55 |
| Domaine (non spécifié) | 0/25 | 0/25 |
| Disponibilité (`en_mission`, sans date) | 0/15 | 3/15 |
| Localisation (non spécifiée) | 0/5 | 0/5 |
| **Total brut** | **36/100** | **45/85** |
| **Score affiché** | **36%** | **53%** |

Le score affiché passe de **36% → 53%** pour un profil Java senior, ce qui est plus cohérent. Un consultant Java intercontrat immédiatement disponible avec toutes les compétences atteindrait ~85-90%.

---

## Limites architecturales restantes (non corrigées dans cette itération)

Ces problèmes nécessitent un refactoring plus profond et ne sont pas bloquants pour la V2 :

### 1. Embedding de l'ensemble du CV en un seul vecteur (vector dilution)

Un CV de 20 ans de carrière contient beaucoup d'informations variées. L'embedding unique capture la "sémantique moyenne" de l'ensemble, pas les pics d'expertise. Un consultant expert Java avec des expériences variées peut avoir un embedding légèrement éloigné d'une requête purement Java.

**Solution future :** Découper le CV en chunks (512 tokens) et indexer plusieurs vecteurs par CV avec max-pooling lors de la recherche (Qdrant le supporte nativement).

### 2. Requête construite par le LLM trop enrichie pour les recherches simples

Pour "dev java sénior", le LLM expand la requête en `["Java", "Spring Boot", "Maven", "JEE", "microservices"…]`. Le vecteur de requête résultant est l'embedding de "l'environnement Java en général", ce qui peut correspondre autant à un chef de projet technique qu'à un développeur Java pur.

**Solution future :** Conserver la requête utilisateur brute pour la recherche Qdrant et utiliser la version enrichie uniquement pour la présentation.

### 3. Détection de séniorité non implémentée

Le niveau de séniorité ("junior", "confirmé", "senior", "expert") n'est pas extrait des CVs et ne contribue pas au scoring. Une requête "senior" ne favorise pas un consultant avec 15 ans d'expérience face à un junior.

**Solution future :** Parser les indicateurs de séniorité dans les CVs (années d'expérience, termes "senior"/"lead"/"expert") et les stocker dans `consultants_meta.json`, puis les inclure dans le score.

---

## Commandes de déploiement

```bash
# Sur le poste local
git add backend/app/services/matcher.py
git commit -m "fix: calibration cosinus + scoring hybride + dénominateur adaptatif"
git push origin ovh-rag-managers

# Sur le serveur OVH (51.83.44.48)
cd /opt/rag-managers
git pull
docker compose restart backend

# Vérification
curl http://localhost:8000/health
docker compose logs backend --tail=30
```
