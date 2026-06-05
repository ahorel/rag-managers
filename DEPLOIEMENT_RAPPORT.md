# Rapport de déploiement — MatchConsult RAG Managers
**Date :** 5 juin 2026  
**Statut : DÉPLOYÉ ET OPÉRATIONNEL**

---

## Résumé

MatchConsult est une application de matching CV / fiche de poste basée sur RAG (Retrieval-Augmented Generation).  
Elle tourne sur un serveur OVH VPS avec 3 containers Docker : Qdrant (base vectorielle), FastAPI (backend), React/Nginx (frontend).

---

## Accès

| Ressource | URL |
|-----------|-----|
| Interface web | http://51.83.44.48 |
| API backend | http://51.83.44.48:8000 |
| Dashboard Qdrant | http://51.83.44.48:6333/dashboard |
| Repository GitHub | https://github.com/ahorel/rag-managers |
| Branche déployée | `ovh-rag-managers` |

---

## Accès serveur SSH

```bash
ssh ubuntu@51.83.44.48
```

| Champ | Valeur |
|-------|--------|
| VPS | vps-fcd494c4.vps.ovh.net |
| IP publique | 51.83.44.48 |
| Utilisateur | ubuntu |
| OS | Ubuntu 26.04 LTS |

---

## Infrastructure

### Serveur OVH VPS-1

| Spec | Valeur |
|------|--------|
| Provider | OVH Cloud |
| Type | VPS-1 |
| CPU | 4 vCore |
| RAM | 8 GB |
| Stockage | 75 GB SSD NVMe |
| Bande passante | 400 Mbit/s illimitée |
| Localisation | France — Gravelines |
| Prix | 6,49 € HT/mois (7,79 € TTC) |
| Backup | Automatique inclus |

### Architecture Docker

```
Navigateur
    ↓  http://51.83.44.48
┌─────────────────────────────────────────┐
│  OVH VPS-1 — Ubuntu 26.04               │
│                                         │
│  ┌──────────────┐  ┌──────────────────┐ │
│  │   Qdrant     │←─│  Backend FastAPI  │ │
│  │  port 6333   │  │  port 8000       │ │
│  └──────────────┘  └────────┬─────────┘ │
│                             ↓           │
│  ┌──────────────────────────────────┐   │
│  │  Frontend React + Nginx          │   │
│  │  port 80                         │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
                    ↓
            Groq API (cloud)
            Llama 3.1 8B Instant
```

### Containers Docker

| Container | Image | Port | Statut |
|-----------|-------|------|--------|
| matchconsult_frontend | rag-managers-frontend | 80 | Up |
| matchconsult_backend | rag-managers-backend | 8000 | Up |
| matchconsult_qdrant | qdrant/qdrant:latest | 6333 | Up |

---

## Configuration

### Variables d'environnement (.env sur le serveur)

```env
GROQ_API_KEY=gsk_*** (voir SERVEUR_ACCES.txt — ne pas commiter)
QDRANT_URL=http://qdrant:6333
GROQ_MODEL=llama-3.1-8b-instant
DEMO_MODE=false
CV_DIRECTORY=./data/cvs
CORS_ORIGINS=http://51.83.44.48
```

> Le fichier `.env` est sur le serveur dans `/opt/rag-managers/.env` — il n'est pas commité dans git.

### LLM utilisé

| Champ | Valeur |
|-------|--------|
| Provider | Groq (cloud gratuit) |
| Modèle | Llama 3.1 8B Instant |
| Quota | ~500 000 tokens/jour |

---

## Repository GitHub

| Champ | Valeur |
|-------|--------|
| URL | https://github.com/ahorel/rag-managers |
| Branche de production | `ovh-rag-managers` |
| Branche principale | `main` |

### Cloner le projet

```bash
git clone -b ovh-rag-managers https://github.com/ahorel/rag-managers.git
```

---

## Vérification de santé

```bash
# Test backend
curl http://51.83.44.48:8000/api/health
# Résultat : {"status":"ok","cvs_loaded":0,"model_ready":true}

# État des containers
ssh ubuntu@51.83.44.48
cd /opt/rag-managers
docker compose ps
```

---

## Étapes réalisées

1. Création compte OVH + commande VPS-1 Ubuntu 26.04
2. Connexion SSH et mise à jour Ubuntu
3. Installation Docker
4. Ajout utilisateur `ubuntu` au groupe docker
5. Installation Git
6. Création repo GitHub `ahorel/rag-managers` branche `ovh-rag-managers`
7. Clone du projet sur le serveur dans `/opt/rag-managers`
8. Création du fichier `.env` avec clé Groq et IP serveur
9. Build et démarrage des 3 containers Docker (`docker compose up -d --build`)
10. Vérification : interface web, dashboard Qdrant, API health check

---

## Prochaine étape — Ajouter des CVs

Pour indexer des CVs dans Qdrant, copiez les fichiers PDF/DOCX sur le serveur :

```bash
# Depuis votre poste Windows (PowerShell)
scp "C:\chemin\vers\cv.pdf" ubuntu@51.83.44.48:/opt/rag-managers/backend/data/cvs/

# Puis redémarrer le backend pour ré-indexer
ssh ubuntu@51.83.44.48
cd /opt/rag-managers
docker compose restart backend
```

---

## Commandes de maintenance

```bash
# Connexion au serveur
ssh ubuntu@51.83.44.48
cd /opt/rag-managers

# Voir l'état des containers
docker compose ps

# Logs en temps réel
docker compose logs -f

# Mettre à jour depuis GitHub et relancer
git pull && docker compose up -d --build

# Redémarrer un service
docker compose restart backend

# Arrêter tout (données conservées)
docker compose down

# Arrêter et vider Qdrant (repartir de zéro)
docker compose down -v && docker compose up -d --build
```
