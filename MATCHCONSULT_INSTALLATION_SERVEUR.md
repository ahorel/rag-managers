# MatchConsult — Installation serveur pas à pas

## Architecture déployée

```
Navigateur commercial
        ↓  http://IP_SERVEUR
 ┌──────────────────────────────────────────────────────┐
 │  Hetzner CX22  (3,79 €/mois) — Ubuntu 24.04         │
 │                                                      │
 │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
 │  │   Qdrant     │  │   Backend    │  │ Frontend  │  │
 │  │  (Docker)    │←─│  FastAPI     │←─│ React+    │  │
 │  │  CVs indexés │  │  (Docker)    │  │ Nginx     │  │
 │  │  Dashboard   │  │  port 8000   │  │ port 80   │  │
 │  │  :6333       │  └──────┬───────┘  └───────────┘  │
 │  └──────────────┘         ↓                          │
 └──────────────────────────────────────────────────────┘
                        Groq API (cloud)
                        Llama 3.1 8B Instant
```

---

## ÉTAPE 1 — Clé API Groq

1. Aller sur **https://console.groq.com** → "Sign Up"
2. Menu "API Keys" → "Create API Key" → nommer `matchconsult`
3. **Copier la clé** (format `gsk_...`) — elle ne s'affiche qu'une fois

---

## ÉTAPE 2 — Créer le serveur Hetzner

**Sur https://hetzner.com/cloud**

1. "Add Server" avec ces paramètres :

   | Champ | Valeur |
   |-------|--------|
   | Location | Nuremberg |
   | Image | **Ubuntu 24.04** |
   | Type | **CX22** — 2 vCPU / 4 GB RAM / 40 GB SSD |
   | Networking | IPv4 activé |
   | Name | `matchconsult` |

2. **Noter l'IP publique** : `49.13.xx.xx`

---

## ÉTAPE 3 — Ouvrir les ports firewall Hetzner

Menu **Firewalls** → "Create Firewall" → nommer `matchconsult-fw`

Ajouter ces règles **Inbound** :

| Port | Usage |
|------|-------|
| 22 | SSH — administration |
| 80 | Interface web commerciaux |
| 6333 | Qdrant Dashboard — admin |

"Apply to" → sélectionner le serveur `matchconsult` → Apply.

---

## ÉTAPE 4 — Se connecter au serveur

```bash
ssh root@49.13.xx.xx
```

Si le message "Are you sure..." apparaît → taper `yes`.

---

## ÉTAPE 5 — Mettre à jour Ubuntu et installer Docker

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
```

Vérifier :

```bash
docker --version
docker compose version
```

---

## ÉTAPE 6 — Installer Git

```bash
apt install -y git
```

---

## ÉTAPE 7 — Cloner le projet

```bash
git clone https://github.com/Pat-ldh/matchconsult.git /opt/matchconsult
cd /opt/matchconsult
```

Vérifier la présence des fichiers :

```bash
ls
```

Vous devez voir : `docker-compose.yml`, `backend/`, `frontend/`, `ARCHITECTURE_ET_DEPLOIEMENT.md`

---

## ÉTAPE 8 — Créer le fichier de configuration

```bash
cp backend/.env.example .env
nano .env
```

Remplir les valeurs :

```env
GROQ_API_KEY=gsk_votre_vraie_cle_groq
QDRANT_URL=http://qdrant:6333
GROQ_MODEL=llama-3.1-8b-instant
DEMO_MODE=false
CV_DIRECTORY=./data/cvs
CORS_ORIGINS=http://49.13.xx.xx
```

Sauvegarder : `Ctrl + O` → Entrée → `Ctrl + X`

---

## ÉTAPE 9 — Déposer les CVs

Depuis votre poste, copier les CVs (PDF ou DOCX) sur le serveur :

```bash
# Depuis votre poste Windows (dans PowerShell ou Git Bash)
scp "C:\chemin\vers\cv_consultant1.pdf" root@49.13.xx.xx:/opt/matchconsult/backend/data/cvs/
scp "C:\chemin\vers\cv_consultant2.docx" root@49.13.xx.xx:/opt/matchconsult/backend/data/cvs/
```

Vérifier que les CVs sont bien sur le serveur :

```bash
# Sur le serveur
ls /opt/matchconsult/backend/data/cvs/
```

---

## ÉTAPE 10 — Démarrer tous les services Docker

```bash
cd /opt/matchconsult
docker compose up -d --build
```

> Première exécution : téléchargement des images + build du frontend React.
> Durée : **5 à 8 minutes**.

Vérifier que les 3 containers tournent :

```bash
docker compose ps
```

Résultat attendu :
```
NAME                     STATUS    PORTS
matchconsult_qdrant      Up        0.0.0.0:6333->6333/tcp
matchconsult_backend     Up        0.0.0.0:8000->8000/tcp
matchconsult_frontend    Up        0.0.0.0:80->80/tcp
```

Si un container n'est pas "Up" :
```bash
docker compose logs backend
docker compose logs frontend
docker compose logs qdrant
```

---

## ÉTAPE 11 — Vérifier que tout fonctionne

**Test 1 — Backend opérationnel**

```bash
curl http://49.13.xx.xx:8000/api/health
```

Résultat attendu :
```json
{"status": "ok", "cvs_loaded": N, "model_ready": true}
```

> `cvs_loaded` doit être égal au nombre de CVs déposés à l'étape 9.

**Test 2 — Interface web**

Ouvrir dans un navigateur :
```
http://49.13.xx.xx
```
→ L'interface MatchConsult s'affiche.
→ Coller une fiche de poste → cliquer Analyser → résultats en < 5 secondes.

**Test 3 — Dashboard Qdrant**

```
http://49.13.xx.xx:6333/dashboard
```
→ Collection `matchconsult_cvs` visible.
→ Nombre de points = nombre de CVs indexés.

---

## Installation terminée

Partager à l'équipe commerciale :

```
http://49.13.xx.xx
```

---

## Ajouter un consultant (après installation)

```bash
# Depuis votre poste — copier le nouveau CV
scp "C:\chemin\nouveau_cv.pdf" root@49.13.xx.xx:/opt/matchconsult/backend/data/cvs/

# Sur le serveur — redémarrer le backend pour ré-indexer
ssh root@49.13.xx.xx
cd /opt/matchconsult
docker compose restart backend
```

---

## Commandes de maintenance

```bash
# Se connecter au serveur
ssh root@49.13.xx.xx
cd /opt/matchconsult

# Récupérer une mise à jour du code
git pull && docker compose up -d --build

# Voir les logs en temps réel
docker compose logs -f

# Redémarrer un service
docker compose restart backend

# Arrêter tout (données conservées)
docker compose down

# Arrêter et vider Qdrant (si ré-indexation complète nécessaire)
docker compose down -v && docker compose up -d --build
```
