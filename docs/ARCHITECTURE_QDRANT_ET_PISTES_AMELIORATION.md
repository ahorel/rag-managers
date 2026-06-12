# Architecture Qdrant — Fonctionnement actuel et pistes d'amélioration

**Contexte :** MatchConsult utilise Qdrant comme base vectorielle pour indexer les CVs et retrouver
les consultants les plus pertinents par similarité sémantique.
Ce document décrit le fonctionnement actuel tel qu'il est implémenté, les choix techniques retenus
et les améliorations identifiées mais non encore réalisées.

---

## 1. Vue d'ensemble de la pipeline RAG

```
CV (PDF/DOCX)
     │
     ▼
[cv_parser.py]  ←── extraction texte brut (pdfplumber / python-docx)
     │
     ▼
Texte brut du CV (tronqué à 6 000 caractères)
     │
     ▼
[sentence-transformers]  ←── modèle paraphrase-multilingual-MiniLM-L12-v2
     │
     ▼
Vecteur 384 dimensions (float32)
     │
     ▼
[Qdrant]  ←── stockage + recherche par similarité cosinus
     │
     ▼
Requête utilisateur → embeddings → top-50 cosinus → scoring hybride → top-10 affichés
```

---

## 2. Extraction de texte des CVs

**Fichier :** `backend/app/services/cv_parser.py`

### Ce qui est fait

Deux parseurs sont implémentés :
- **PDF** → `pdfplumber` : extrait le texte page par page, concatène les pages avec `\n`
- **DOCX/DOC** → `python-docx` : extrait les paragraphes non vides, concatène avec `\n`

```python
def extract_text_from_pdf(path: str) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)
```

### Limite : pas de chunking

Le texte extrait est ensuite **tronqué à 6 000 caractères** dans `embeddings.py` avant d'être envoyé
au modèle d'embeddings. Il n'y a **pas de découpage en chunks** : le CV entier est traité comme
un seul document et produit **un seul vecteur** dans Qdrant.

```python
_MAX_CHARS = 6000  # dans embeddings.py
embedding = self.model.encode(text[:_MAX_CHARS])
```

---

## 3. Modèle d'embeddings

**Modèle :** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers)

| Caractéristique | Valeur |
|---|---|
| Dimensions | 384 |
| Langues | 50+ dont français |
| Taille du modèle | ~120 Mo |
| Longueur max (tokens) | 512 tokens ≈ 350-400 mots |
| Distance utilisée | Cosinus |

### Comportement observé sur des CVs réels

La similarité cosinus retournée par Qdrant **ne couvre pas la plage théorique 0–1**.
Sur des textes longs (CVs complets), les valeurs observées sont :

| Situation | Cosinus brut |
|---|---|
| Meilleure correspondance observée | ~0,85 |
| Correspondance moyenne | ~0,55–0,65 |
| Consultants non pertinents | ~0,30–0,40 |
| Minimum absolu observé | ~0,25 |

Raison : le modèle encode la **sémantique globale** d'un texte, pas des mots-clés individuels.
Deux documents longs et variés produisent des vecteurs structurellement proches même s'ils ne
partagent pas le même domaine technique — l'embedding "lisse" la diversité du contenu.

---

## 4. Index Qdrant

**Fichier :** `backend/app/services/embeddings.py`

### Structure de la collection

```
Collection : matchconsult_cvs
Distance   : COSINE
Vecteurs   : 384 dimensions
```

**Un point Qdrant par CV.** Chaque point contient :

```json
{
  "id": 0,
  "vector": [0.12, -0.34, ...],   ← 384 floats
  "payload": {
    "cv_id":             "nom_fichier_sans_extension",
    "name":              "Prénom NOM",
    "title":             "Senior Java Developer",
    "available":         true,
    "status":            "intercontrat | preavailable | en_mission",
    "availability_date": "2026-09-01",
    "location":          "Paris",
    "remote":            "full | partial | none",
    "languages":         ["fr", "en"],
    "domains":           ["finance", "assurance"],
    "email":             "consultant@email.com",
    "text":              "texte brut du CV (non tronqué, pour le keyword matching)",
    "filename":          "cv.pdf"
  }
}
```

> **Note importante :** Le champ `text` dans le payload contient le **texte complet** du CV
> (non tronqué), contrairement au vecteur qui est calculé sur les 6 000 premiers caractères.
> Ce champ est utilisé en post-traitement pour le keyword matching (`_keyword_ratio()` dans
> `matcher.py`) et pour la génération des explications par le LLM.

### Réindexation au démarrage

À chaque démarrage du backend (`lifespan` dans `main.py`), la collection est **supprimée et recréée**
entièrement :

```python
# embeddings.py — load_cvs()
self.qdrant.delete_collection(_COLLECTION)   # supprime l'ancienne
self.qdrant.create_collection(...)           # recrée à vide
# … encode tous les CVs …
self.qdrant.upsert(collection_name=_COLLECTION, points=points)
```

Cela garantit que l'index est toujours cohérent avec les fichiers CVs présents sur disque.
La contrepartie est que le backend est **indisponible pendant le chargement** (environ 30–90 secondes
selon le nombre de CVs), d'où le healthcheck avec `start_period: 120s`.

### Gestion des race conditions

Avec 2 workers uvicorn, les deux peuvent essayer de recréer la collection simultanément.
Le code est protégé par un try/except :

```python
try:
    self.qdrant.delete_collection(_COLLECTION)
except Exception:
    pass
try:
    self.qdrant.create_collection(...)
except Exception:
    logger.warning("Collection déjà créée par un autre worker, on continue.")
```

---

## 5. Recherche et scoring

**Fichier :** `backend/app/services/matcher.py`

### Construction de la requête Qdrant

Le texte de requête envoyé à Qdrant est construit depuis l'offre réécrite par le LLM :

```python
query_text = (
    f"{offer.title} "
    + " ".join(offer.technical_skills)
    + " "
    + " ".join(offer.soft_skills)
    + " "
    + offer.client_context
)
if eff_domain:
    query_text += f" {eff_domain}"
```

Ce texte est embedé avec le même modèle que les CVs, puis Qdrant retourne les **50 CVs** ayant
les vecteurs les plus proches (cosinus le plus élevé).

### Scoring hybride (post-Qdrant)

Le score final n'est **pas** le cosinus brut de Qdrant. Il est recalculé en 4 composantes :

```
Score total (0–100%) = skills + domain + availability + location
                       ─────────────────────────────────────────
                             max_possible(critères actifs)
```

| Composante | Points max | Calcul |
|---|---|---|
| **Skills** | 55 | 70% cosinus calibré + 30% keyword ratio |
| **Domaine** | 25 | Correspondance exacte=25, similaire=12, aucune=0 |
| **Disponibilité** | 15 | intercontrat=15, preavailable=7, en_mission+date=2–5, en_mission sans date=3 |
| **Localisation** | 5 | Ville + remote match |

Le dénominateur est **adaptatif** : si la requête ne précise ni domaine ni localisation,
le max est 70 (55+15) et non 100, pour que les scores restent lisibles.

---

## 6. Métadonnées consultants

**Fichier :** `backend/data/consultants_meta.json`

Les informations non présentes dans le CV (disponibilité, domaines métier, localisation) sont
stockées dans un fichier JSON externe maintenu manuellement :

```json
{
  "nom_cv_sans_extension": {
    "name":              "Prénom NOM",
    "title":             "Intitulé de poste",
    "available":         true,
    "status":            "intercontrat",
    "availability_date": null,
    "location":          "Paris",
    "remote":            "partial",
    "languages":         ["fr", "en"],
    "domains":           ["finance", "telecom"],
    "email":             "consultant@email.com"
  }
}
```

Ces données sont chargées une fois au démarrage et injectées dans le payload Qdrant de chaque point.
Si un CV n'a pas d'entrée dans ce fichier, les valeurs par défaut sont : `available=true`,
`status="intercontrat"`, autres champs vides.

---

## 7. Pistes d'amélioration identifiées (non réalisées)

### 7.1 — Chunking du CV en plusieurs vecteurs ★★★ Impact fort

**Problème actuel :** Un CV de 20 ans de carrière est réduit à un seul vecteur de 384 dimensions,
calculé sur les 6 000 premiers caractères. Cela produit une "sémantique moyenne" qui dilue les
compétences de pointe. Un expert Java avec des expériences variées (management, architecture,
DevOps) peut avoir un vecteur plus éloigné d'une requête "développeur Java" que quelqu'un avec
un CV court et uniforme.

**Solution envisagée :** Découper chaque CV en chunks de 512 tokens avec un chevauchement de 50 tokens
(sliding window), puis indexer **N vecteurs par CV** dans Qdrant. Lors de la recherche,
sélectionner le **meilleur chunk** par CV (max-pooling) pour représenter la similarité du consultant.

```
CV complet (3 000 tokens)
    ├── Chunk 1 : tokens 0–511
    ├── Chunk 2 : tokens 461–972   (overlap 50)
    ├── Chunk 3 : tokens 922–1433
    └── …
```

Qdrant le supporte via les `named vectors` ou simplement via plusieurs points avec le même
`cv_id` dans le payload.

**Bénéfice attendu :** Meilleure détection des compétences enfouies dans un CV long.
Un profil senior dont les missions Java datent de 5 ans mais restent présentes en milieu de CV
ne serait plus pénalisé par le "bruit" de ses missions récentes.

**Coût :** Réindexation plus longue (N× plus de calculs d'embeddings), requêtes Qdrant plus
volumineuses, logique de déduplication par `cv_id` à implémenter dans `matcher.py`.

---

### 7.2 — Requête Qdrant sur le texte brut, pas sur l'offre enrichie ★★ Impact moyen

**Problème actuel :** La requête envoyée à Qdrant est l'embedding de l'offre réécrite par le LLM
(`offer.title + skills + context`). Pour une requête simple "développeur Java sénior", le LLM
enrichit en `["Java", "Spring Boot", "Maven", "JEE", "microservices", "backend"]`. L'embedding de
cette liste est un vecteur "environnement Java en général" qui peut correspondre autant à un
chef de projet technique qu'à un développeur Java pur.

**Solution envisagée :** Utiliser le **texte brut de la requête utilisateur** comme première
recherche Qdrant, et n'utiliser l'offre enrichie du LLM que pour le scoring post-Qdrant
(keyword matching). Ou construire la requête Qdrant uniquement depuis le `title` + la liste
courte de `technical_skills` extraite par le LLM.

**Bénéfice attendu :** Meilleure précision sur les requêtes courtes et directes. Moins de
bruit sémantique sur les recherches simples type "dev Java sénior".

**Coût :** Risque de moins bonne couverture sur les requêtes longues et complexes où l'enrichissement
du LLM apporte réellement de la valeur.

---

### 7.3 — Détection de séniorité ★★ Impact moyen

**Problème actuel :** Le niveau de séniorité ("junior", "confirmé", "senior", "expert") n'est
extrait ni des CVs ni des requêtes. Une requête "développeur Java **sénior**" ne favorise pas un
consultant avec 15 ans d'expérience par rapport à un consultant avec 2 ans. La séniorité est
présente dans `consultants_meta.json` uniquement si elle a été saisie manuellement dans le champ
`title`.

**Solution envisagée :** Lors du parsing des CVs, détecter les indicateurs de séniorité :
- Nombre total d'années d'expérience (regex sur "X ans d'expérience", dates de missions)
- Termes explicites : "Senior", "Lead", "Expert", "Principal", "Directeur technique"
- Nombre de missions / employeurs mentionnés

Stocker ce `seniority_level` dans le payload Qdrant et ajouter une composante score (+5 pts si
le niveau correspond, –5 si mismatch fort senior/junior).

**Coût :** Implémentation du parser de séniorité (fragile sur des CVs mal formatés), nécessite
de revoir le calcul du score total et le max_possible.

---

### 7.4 — Persistence de l'index Qdrant entre redémarrages ★ Impact faible

**Problème actuel :** La collection est détruite et reconstruite à chaque démarrage du backend.
Avec 25 CVs, cela prend ~60 secondes. Avec 200+ CVs, cela pourrait prendre 5–10 minutes pendant
lesquelles le backend est en état `starting` et refuse les requêtes.

**Solution envisagée :** Ne reconstruire l'index que si les CVs ont changé (comparaison de hash
MD5 des fichiers avec les hash stockés dans un manifest JSON). Si aucun CV n'a changé depuis le
dernier démarrage, réutiliser l'index Qdrant existant (qui est persisté sur volume Docker).

```
Au démarrage :
  1. Calculer les hash MD5 de tous les CVs dans data/cvs/
  2. Comparer avec le manifest data/embeddings_manifest.json
  3. Si identique → skip la réindexation, juste vérifier que la collection existe
  4. Si différent → réindexer les CVs modifiés/ajoutés, supprimer les CVs retirés
```

**Coût :** Logique de diff incrementale à écrire, gestion des cas de corruption d'index.

---

### 7.5 — Filtres Qdrant natifs (pre-filtering) ★ Impact faible

**Problème actuel :** Les filtres (domaine, localisation, langue, statut) sont appliqués
**après** la recherche Qdrant, en Python, sur les 50 résultats retournés. Si les 50 premiers
résultats Qdrant sont tous `en_mission`, le filtre `intercontrat_only` peut retourner 0 résultats
même si des profils pertinents existent.

**Solution envisagée :** Passer les filtres directement à Qdrant via son API de filtrage :

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

hits = self.qdrant.search(
    collection_name=_COLLECTION,
    query_vector=query_emb,
    limit=50,
    query_filter=Filter(
        must=[FieldCondition(key="status", match=MatchValue(value="intercontrat"))]
    ),
    with_payload=True,
)
```

Cela garantit que les 50 résultats retournés respectent déjà les filtres, même dans des corpus
de grande taille.

**Coût :** Refactoring de la logique de filtrage de `matcher.py` vers `embeddings.py`,
passage des filtres en paramètres du `rank_by_similarity()`.

---

## 8. Résumé des priorités

| # | Amélioration | Impact | Complexité | Priorité |
|---|---|---|---|---|
| 7.1 | Chunking CVs (multi-vecteurs) | ★★★ Fort | Haute | V3 |
| 7.2 | Requête Qdrant = texte brut | ★★ Moyen | Faible | V2.5 |
| 7.3 | Détection séniorité | ★★ Moyen | Moyenne | V2.5 |
| 7.4 | Index persistant (diff incrémental) | ★ Faible | Moyenne | V3 |
| 7.5 | Filtres Qdrant natifs | ★ Faible | Faible | V2.5 |

L'amélioration 7.2 (requête sur texte brut) est la plus simple à implémenter et donnerait
une amélioration visible immédiatement sur les requêtes courtes. Les améliorations 7.1 (chunking)
et 7.3 (séniorité) ont le plus d'impact sur la qualité des résultats mais nécessitent un chantier
plus important.

---

*Document créé le 2026-06-12 — basé sur le code de la branche `ovh-rag-managers`*
