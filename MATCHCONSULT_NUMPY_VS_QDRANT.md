# NumPy vs Qdrant — Choix pour le matching de CVs

## Contexte

MatchConsult utilise des vecteurs (embeddings) pour comparer une offre de mission
aux CVs disponibles. La question est : où stocker ces vecteurs et comment effectuer la recherche ?

---

## Comparatif technique

| Critère | NumPy (solution initiale) | Qdrant (solution retenue) |
|---------|--------------------------|--------------------------|
| **Stockage** | RAM uniquement | Disque persistant (volume Docker) |
| **Survie au redémarrage** | Non — re-vectorise tous les CVs à chaque démarrage | Oui — les vecteurs sont sur disque |
| **Temps de démarrage** | Long si beaucoup de CVs (lecture + vectorisation) | Quasi-instantané (déjà indexé) |
| **Dashboard de supervision** | Aucun | Interface web intégrée (port 6333) |
| **100 CVs — temps de recherche** | ~1 ms | ~1 ms |
| **1 000 CVs — temps de recherche** | ~10 ms | ~2 ms |
| **10 000 CVs — temps de recherche** | ~100 ms | ~5 ms |
| **Filtrage par métadonnée** | Non | Oui (disponibilité, compétence, titre...) |
| **Dépendance externe** | Aucune (NumPy inclus) | Service Qdrant (Docker, ~100 MB) |
| **Complexité** | Minimale | Légère (un container supplémentaire) |

---

## Performance à l'échelle ESN

Pour une ESN avec 50 à 500 consultants :

```
50 CVs  → NumPy : <1 ms  | Qdrant : <1 ms   → équivalents
200 CVs → NumPy : ~2 ms  | Qdrant : ~1 ms   → équivalents
500 CVs → NumPy : ~5 ms  | Qdrant : ~1 ms   → Qdrant légèrement meilleur
```

La performance de recherche n'est pas l'argument décisif à cette échelle.
**L'argument décisif est la persistance.**

---

## Pourquoi Qdrant est retenu

### 1. Persistance — le gain principal

Avec NumPy, chaque redémarrage du serveur déclenche :
- Lecture de tous les fichiers PDF/DOCX
- Vectorisation de chaque CV (CPU, plusieurs secondes par CV)
- Pour 100 CVs : ~2-3 minutes avant que le service soit opérationnel

Avec Qdrant :
- Les vecteurs sont déjà sur disque (volume Docker)
- Démarrage en quelques secondes

### 2. Cohérence d'architecture

Le projet RAG (atelier ML) utilise déjà Qdrant.
Les deux projets partagent la même brique technique sur le même serveur Hetzner.
Un seul container Qdrant peut servir les deux collections simultanément.

### 3. Dashboard de supervision

Accessible à `http://IP_SERVEUR:6333/dashboard` :
- Voir combien de CVs sont indexés
- Vérifier qu'un CV est bien présent après ajout
- Inspecter le contenu d'un vecteur sans écrire de code

### 4. Évolutivité future

Si l'ESN grandit (>500 consultants), Qdrant gère sans changement de code.
NumPy deviendrait un goulot d'étranglement au-delà de 1 000 CVs.

---

## Ce qui a changé dans le code

Un seul fichier modifié : `backend/app/services/embeddings.py`

| Avant (NumPy) | Après (Qdrant) |
|---------------|----------------|
| `cv_store: dict` en RAM | Collection Qdrant sur disque |
| `np.dot()` pour la similarité | `qdrant.search()` avec distance cosinus |
| Re-vectorise à chaque démarrage | Vectorise une fois, persiste |
| Aucune supervision possible | Dashboard web intégré |

L'interface publique (`rank_by_similarity`) reste identique.
`matcher.py` n'a pas été modifié.

---

## Verdict

**Qdrant est retenu.** La persistance et la cohérence d'architecture justifient
le léger surcoût d'un container supplémentaire (~100 MB RAM, inclus dans le CX22).

Le serveur CX22 (4 GB RAM) reste la bonne configuration :
Qdrant + Backend + Frontend + Nginx ≈ 1,5 GB RAM utilisés, soit 2,5 GB de marge.
