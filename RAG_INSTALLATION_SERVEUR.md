# Installation du serveur RAG — Guide pas à pas

## Rappel de l'architecture

```
Votre navigateur
      ↓
Serveur Hetzner (3,79 €/mois)
  ├── Qdrant     → stocke les documents indexés
  └── Streamlit  → interface web de questions-réponses
           ↓  appel HTTPS
      Groq API   → modèle Llama 3.1 8B (LLM gratuit dans le cloud)
```

Groq est le service cloud qui fait tourner le modèle d'IA.
Votre serveur ne fait pas tourner de LLM — il appelle Groq comme on appelle une API REST.

---

## ÉTAPE 1 — Créer votre clé API Groq

**Dans votre navigateur sur https://console.groq.com**

1. Cliquer **"Sign Up"** → créer un compte (email + mot de passe)
2. Vérifier votre email → cliquer le lien de confirmation
3. Se connecter sur https://console.groq.com
4. Dans le menu gauche → cliquer **"API Keys"**
5. Cliquer **"Create API Key"**
6. Donner un nom : `rag-sandbox`
7. Cliquer **"Submit"**
8. **Copier immédiatement la clé affichée** (format `gsk_xxxxxxxxxxxxxxxxxxxx`)

> La clé ne s'affiche qu'une seule fois. La noter dans un endroit sûr.

> Quota gratuit inclus : ~500 000 tokens/jour et 14 400 requêtes/jour.
> Largement suffisant pour une équipe de dev en phase de test.

---

## ÉTAPE 2 — Créer le serveur sur Hetzner

**Dans votre navigateur sur https://hetzner.com/cloud**

1. Créer un compte → vérifier l'email → se connecter
2. Cliquer **"Add Server"**
3. Remplir exactement comme suit :

   | Champ | Valeur |
   |-------|--------|
   | Location | **Nuremberg** (eu-central) |
   | Image | **Ubuntu 24.04** |
   | Type | **CX22** — 2 vCPU / 4 GB RAM / 40 GB SSD |
   | Networking | **IPv4** coché |
   | Name | `rag-sandbox` |

4. Cliquer **"Create & Buy Now"**
5. Attendre ~30 secondes
6. **Noter l'IP publique** affichée, exemple : `49.13.xx.xx`

---

## ÉTAPE 3 — Ouvrir les ports dans le firewall Hetzner

**Toujours dans l'interface Hetzner**

1. Menu gauche → **Firewalls** → **Create Firewall**
2. Nommer le firewall `rag-firewall`
3. Ajouter ces 3 règles **Inbound** (bouton "Add Rule" pour chacune) :

   | Port | Protocole | Source | Usage |
   |------|-----------|--------|-------|
   | 22 | TCP | Any | SSH — connexion admin |
   | 8501 | TCP | Any | Streamlit — interface dev |
   | 6333 | TCP | Any | Qdrant Dashboard — visualisation |

4. Cliquer **"Create Firewall"**
5. Onglet **"Apply to"** → sélectionner `rag-sandbox` → **"Apply"**

---

## ÉTAPE 4 — Se connecter au serveur en SSH

**Dans votre terminal (Git Bash ou PowerShell)**

```bash
ssh root@49.13.xx.xx
```

> Remplacer `49.13.xx.xx` par votre vraie IP Hetzner.

Si le message suivant apparaît :
```
Are you sure you want to continue connecting (yes/no)?
```
→ Taper `yes` puis Entrée.

Vous êtes connecté quand vous voyez :
```
root@rag-sandbox:~#
```

---

## ÉTAPE 5 — Mettre à jour Ubuntu

```bash
apt update && apt upgrade -y
```

> Durée : ~1 minute.

---

## ÉTAPE 6 — Installer Docker

```bash
curl -fsSL https://get.docker.com | sh
```

> Durée : ~1 minute.

Vérifier l'installation :

```bash
docker --version
docker compose version
```

Résultat attendu :
```
Docker version 27.x.x, build ...
Docker Compose version v2.x.x
```

---

## ÉTAPE 7 — Installer Git

```bash
apt install -y git
```

Vérifier :

```bash
git --version
```

---

## ÉTAPE 8 — Cloner le projet depuis GitHub

```bash
git clone https://github.com/ahorel/orange_atelier_ia_gen.git
```

Se placer dans le dossier :

```bash
cd orange_atelier_ia_gen
```

Vérifier que les fichiers sont présents :

```bash
ls
```

Vous devez voir : `Dockerfile`, `docker-compose.yml`, `RAG_POC/`, `ML_ETAPES/`, etc.

---

## ÉTAPE 9 — Créer le fichier de configuration avec la clé Groq

Copier le template :

```bash
cp RAG_POC/.env.server .env
```

Ouvrir l'éditeur :

```bash
nano .env
```

Le fichier contient :

```
GROQ_API_KEY=gsk_votre_cle_groq
RAG_MODE=server
QDRANT_URL=http://qdrant:6333
```

**Remplacer `gsk_votre_cle_groq` par la clé copiée à l'étape 1.**

Exemple après modification :
```
GROQ_API_KEY=gsk_AbCdEfGhIjKlMnOpQrStUvWxYz123456789
RAG_MODE=server
QDRANT_URL=http://qdrant:6333
```

Sauvegarder et quitter :
- `Ctrl + O` → Entrée
- `Ctrl + X`

Vérifier que la clé est bien enregistrée :

```bash
cat .env
```

---

## ÉTAPE 10 — Démarrer les containers Docker

```bash
docker compose up -d --build
```

> Première exécution : télécharge les images et construit l'image de l'app.
> Durée : **3 à 5 minutes**.

Vérifier que les deux containers tournent :

```bash
docker compose ps
```

Résultat attendu :
```
NAME            STATUS    PORTS
rag_qdrant      Up        0.0.0.0:6333->6333/tcp
rag_streamlit   Up        0.0.0.0:8501->8501/tcp
```

Si un container n'est pas "Up", afficher les erreurs :

```bash
docker compose logs
```

---

## ÉTAPE 11 — Indexer les documents dans Qdrant

```bash
docker compose exec app python RAG_ETAPE1_indexation.py
```

> Première exécution : télécharge le modèle d'embedding (~90 MB).
> Durée : **1 à 2 minutes**.

Résultat attendu en fin d'exécution :
```
✅ Étape 1 terminée — Base Qdrant prête
Mode    : SERVER
```

---

## ÉTAPE 12 — Vérifier que tout fonctionne

**Test 1 — Interface Streamlit**

Ouvrir dans un navigateur :
```
http://49.13.xx.xx:8501
```
→ L'interface de questions-réponses s'affiche.
→ Poser une question : `"Comment fonctionne le warm start ?"`
→ Une réponse générée par Groq (Llama 3.1 8B) doit s'afficher en moins de 2 secondes.

**Test 2 — Dashboard Qdrant**

Ouvrir dans un navigateur :
```
http://49.13.xx.xx:6333/dashboard
```
→ Le dashboard Qdrant s'affiche.
→ Cliquer sur la collection `atelier_ml_knowledge`.
→ Le nombre de points doit être supérieur à 0.

**Test 3 — Test en ligne de commande**

```bash
docker compose exec app python RAG_ETAPE2_generation.py "Qu'est-ce que le seuil de confiance ?"
```
→ La réponse s'affiche dans le terminal avec les chunks sources et le texte généré.

---

## L'installation est terminée

Partager à l'équipe :

| URL | Qui l'utilise |
|-----|--------------|
| `http://49.13.xx.xx:8501` | Tous les devs — interface de test |
| `http://49.13.xx.xx:6333/dashboard` | Admin — visualiser la base Qdrant |

---

## Commandes de maintenance

```bash
# Se reconnecter au serveur
ssh root@49.13.xx.xx
cd orange_atelier_ia_gen

# Récupérer les mises à jour du code et relancer
git pull && docker compose up -d --build

# Re-indexer après une modification des documents
docker compose exec app python RAG_ETAPE1_indexation.py

# Voir les logs en temps réel
docker compose logs -f

# Redémarrer les containers
docker compose restart

# Arrêter (données conservées)
docker compose down

# Arrêter et vider la base vectorielle (repartir de zéro)
docker compose down -v
```
