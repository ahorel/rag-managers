# RAG Sandbox — Infrastructure serveur partagé (Hetzner + Groq)

---

## Comment fonctionne ce système — et pourquoi le serveur n'a pas besoin d'être puissant

### Le trajet d'une question

```
Dev (navigateur)
      │
      │  "Comment fonctionne le warm start ?"
      ▼
Serveur Hetzner CX22  (3,79 €/mois — votre serveur)
      │
      │  1. Embedding de la question
      │     sentence-transformers → vecteur 384 dimensions
      │     Calcul CPU, ~50 ms, ~90 MB de RAM
      │
      │  2. Recherche dans Qdrant
      │     top-4 chunks les plus proches sémantiquement
      │     Lecture mémoire, ~10 ms
      │
      │  3. Construction du prompt
      │     [contexte : 4 chunks] + [question]
      │     ~800 tokens au total
      │
      │  ─────── appel HTTPS sortant ──────►  Groq (leurs serveurs)
      │                                              │
      │                                   Llama 3.1 8B Instant
      │                                   tourne sur les GPU de Groq
      │                                   ~700 tokens/seconde
      │                                   latence < 1 seconde
      │
      │  ◄──── réponse JSON (~400 tokens) ───────────┘
      │
      │  4. Affichage dans Streamlit
      ▼
Dev reçoit la réponse dans son navigateur
```

### Ce que fait votre serveur — uniquement des tâches légères

| Tâche | Ressource consommée |
|-------|---------------------|
| Embedding de la question (384 dims) | ~50 MB RAM, CPU < 1 s |
| Recherche vectorielle Qdrant | ~200 MB RAM, < 50 ms |
| Interface Streamlit | ~150 MB RAM |
| **Total serveur** | **~500 MB RAM, 0 GPU** |

Le LLM tourne chez Groq sur leurs machines. Votre serveur envoie juste une requête HTTPS.

---

## Coût total réel

### Ce que coûte chaque requête sur Groq

| | Tokens | Tarif | Coût par requête |
|-|--------|-------|-----------------|
| Input (contexte + question) | ~750 tokens | 0,05 $/1M | 0,000 037 $ |
| Output (réponse) | ~350 tokens | 0,08 $/1M | 0,000 028 $ |
| **Total par requête** | | | **~0,006 centime** |

### Simulation selon l'usage

| Scénario | Requêtes/jour | Coût Groq/mois | Total/mois |
|----------|--------------|----------------|------------|
| Démo atelier (5 devs, 2h) | ~50 | 0 € (free tier) | **3,79 €** |
| Tests quotidiens (5 devs × 20 questions) | 100 | 0 € (free tier) | **3,79 €** |
| Usage intensif (10 devs × 50 questions) | 500 | ~1 € | **~5 €** |

> Le free tier Groq couvre ~500 000 tokens/jour et 14 400 requêtes/jour.

---

## Architecture du serveur

```
Devs (navigateur)
       ↓  http://IP_SERVEUR:8501        ↓  http://IP_SERVEUR:6333/dashboard
 ┌──────────────────────────────────────────────────────┐
 │  Hetzner CX22  (3,79 €/mois) — Ubuntu 24.04         │
 │                                                      │
 │  ┌────────────────────┐   ┌────────────────────────┐ │
 │  │   Qdrant (Docker)  │   │  Streamlit (Docker)    │ │
 │  │   Base vectorielle │←──│  Interface web         │ │
 │  │   Volume persistant│   │  + Embeddings CPU      │ │
 │  │   Dashboard :6333  │   │                        │ │
 │  └────────────────────┘   └───────────┬────────────┘ │
 └──────────────────────────────────────│───────────────┘
                                         ↓  HTTPS
                                    Groq API
                               Llama 3.1 8B Instant
```

---

## Gestion de Qdrant — qui fait quoi

Qdrant est la base de données qui stocke les documents indexés sous forme de vecteurs.
Sa gestion est simple et ne demande aucune maintenance régulière.

### Persistance des données

Les données Qdrant sont stockées dans un **volume Docker** sur le serveur.
Elles survivent aux redémarrages du container et du serveur. Aucune action requise.

### Rôles

| Rôle | Qui | Ce qu'il fait |
|------|-----|---------------|
| Administrateur | 1 dev désigné | Lance la ré-indexation quand les docs changent |
| Développeur | Toute l'équipe | Pose des questions via Streamlit, ne touche pas à Qdrant |

### Cycle de vie

```
1. Premier démarrage   → indexation une seule fois (~1 min)
                          docker compose exec app python RAG_ETAPE1_indexation.py

2. Usage quotidien     → rien à faire, Qdrant répond automatiquement à chaque question

3. Nouveau document    → l'admin relance l'indexation (1 commande, ~1 min)

4. Redémarrage serveur → Qdrant redémarre seul, données intactes (volume Docker)
```

### Dashboard Qdrant — visualiser ce qui est indexé

Le dashboard web Qdrant est accessible directement depuis un navigateur :

```
http://IP_SERVEUR:6333/dashboard
```

Il permet de :
- Voir les collections et le nombre de points indexés
- Lancer une recherche manuelle pour vérifier qu'un document est bien indexé
- Inspecter le contenu d'un chunk (texte, métadonnées, score)

> Ajouter le port **6333** dans les règles du firewall Hetzner
> (même procédure que le port 8501 — étape 1 du mode opératoire).

---

## Fichiers créés dans le projet

| Fichier | Rôle |
|---------|------|
| `Dockerfile` | Image Docker de l'application |
| `docker-compose.yml` | Orchestration Qdrant + Streamlit |
| `RAG_POC/.env.server` | Template `.env` pour le serveur |
| `RAG_POC/rag_config.py` | Config Python — 3 modes : local / server / cloud |
| `RAG_POC/RAG_ETAPE1_indexation.py` | Indexation (supporte les 3 modes) |
| `RAG_POC/RAG_ETAPE2_generation.py` | Retrieval + génération Groq |
| `RAG_POC/streamlit_app.py` | Interface web |
| `.gitignore` | Protège `.env` et `qdrant_db/` du git |

---

## Mode opératoire — 6 étapes

### Étape 1 — Créer le serveur Hetzner (10 min)

1. Créer un compte sur **https://hetzner.com/cloud**
2. "Add Server" avec ces paramètres :

   | Paramètre | Valeur |
   |-----------|--------|
   | Location | Nuremberg ou Helsinki |
   | Image | **Ubuntu 24.04** |
   | Type | **CX22** (2 vCPU / 4 GB RAM / 40 GB SSD) |
   | Networking | IPv4 activé |
   | SSH Key | Ajouter votre clé publique (recommandé) |

3. Noter l'IP publique du serveur, par exemple `49.13.xx.xx`

4. Dans l'onglet **Firewalls** de Hetzner, autoriser les ports :

   | Port | Service |
   |------|---------|
   | 22 | SSH (administration) |
   | 8501 | Streamlit (interface dev) |
   | 6333 | Qdrant Dashboard (visualisation) |

---

### Étape 2 — Installer Docker sur le serveur (5 min)

```bash
# Se connecter au serveur
ssh root@49.13.xx.xx

# Installer Docker
curl -fsSL https://get.docker.com | sh

# Vérifier
docker --version && docker compose version
```

---

### Étape 3 — Créer un compte Groq et obtenir une clé API (5 min)

1. Aller sur **https://console.groq.com** → "Sign Up"
2. Menu "API Keys" → "Create API Key"
3. Copier la clé (format `gsk_...`)

---

### Étape 4 — Déployer le projet sur le serveur (10 min)

```bash
# Sur le serveur (SSH)
apt install -y git
git clone https://github.com/VOTRE_COMPTE/atelier_presentation_ml.git
cd atelier_presentation_ml

cp RAG_POC/.env.server .env
nano .env   # coller la clé Groq
```

Contenu du `.env` :

```env
GROQ_API_KEY=gsk_votre_vraie_cle_groq
RAG_MODE=server
QDRANT_URL=http://qdrant:6333
```

```bash
# Démarrer les containers
docker compose up -d --build

# Vérifier
docker compose ps
```

---

### Étape 5 — Indexer les documents (une seule fois)

```bash
docker compose exec app python RAG_ETAPE1_indexation.py
```

Puis vérifier dans le dashboard : `http://49.13.xx.xx:6333/dashboard`
→ Collection `atelier_ml_knowledge` → nombre de points indexés visible.

---

### Étape 6 — Partager avec l'équipe

| URL | Accès |
|-----|-------|
| `http://49.13.xx.xx:8501` | Interface de test (toute l'équipe) |
| `http://49.13.xx.xx:6333/dashboard` | Dashboard Qdrant (admin) |

---

## Commandes utiles sur le serveur

```bash
# Logs en temps réel
docker compose logs -f

# Mettre à jour après un git pull
git pull && docker compose up -d --build

# Re-indexer après une mise à jour des docs
docker compose exec app python RAG_ETAPE1_indexation.py

# Tester le RAG en ligne de commande
docker compose exec app python RAG_ETAPE2_generation.py "Comment fonctionne le warm start ?"

# Arrêter tout (données conservées)
docker compose down

# Arrêter et vider la base vectorielle (re-départ propre)
docker compose down -v
```

---

## Développement local (sur votre poste)

```powershell
Copy-Item RAG_POC\.env.example RAG_POC\.env
# Mettre RAG_MODE=local et GROQ_API_KEY dans .env

pip install -r RAG_POC/requirements_rag.txt
python RAG_POC/RAG_ETAPE1_indexation.py
streamlit run RAG_POC/streamlit_app.py
```

---

## Récapitulatif des trois modes

| Mode | Qdrant | LLM | Usage |
|------|--------|-----|-------|
| `local` | Fichiers locaux (`qdrant_db/`) | Groq API | Dev solo sur son poste |
| `server` | Docker sur Hetzner | Groq API | **Sandbox partagé — recommandé** |
| `cloud` | Qdrant Cloud SaaS | Groq API | Alternative sans serveur à gérer |

---

## Alternatives LLM si Groq est indisponible

| Fournisseur | Modèle | Coût | Notes |
|-------------|--------|------|-------|
| **Groq (recommandé)** | `llama-3.1-8b-instant` | Gratuit | Ultra-rapide, multilingue FR/EN |
| Groq | `mixtral-8x7b-32768` | Gratuit | Plus puissant, contexte plus large |
| Anthropic | `claude-haiku-4-5-20251001` | ~0,25 $/1M tokens | Excellent en français |
| OpenAI | `gpt-4o-mini` | ~0,15 $/1M tokens | Fiable, bien documenté |
