# MatchConsult — Guide de test & chaîne technique

**Version :** V2  
**URL production :** http://51.83.44.48  
**Qdrant dashboard :** http://51.83.44.48:6333/dashboard

---

## 1. Quel LLM est utilisé ?

La solution utilise un **mécanisme de fallback automatique** dans cet ordre de priorité :

```
1. Groq  →  llama-3.1-8b-instant  (rapide, gratuit, utilisé en prod)
2. Anthropic  →  claude-sonnet-4-6  (fallback si Groq indisponible)
3. Mode démo  →  réponses simulées statiques (si aucune clé configurée)
```

**En production sur le VPS**, la clé Groq est configurée dans le fichier `.env` du serveur.  
Elle peut être mise à jour ou remplacée **à la volée** depuis la page `⚙ Administration` de l'interface web, sans redémarrer le serveur.

Le modèle **Groq llama-3.1-8b-instant** est un LLM Llama 3.1 hébergé par Groq Cloud.  
Latence typique pour structurer un email client : **< 2 secondes**.

---

## 2. La chaîne technique complète

### Vue d'ensemble

```
[Commercial]
     │
     │  Copie-colle l'email du client dans l'interface
     ▼
[Interface Web — React/TypeScript]
     │
     │  POST /api/analyze  { mission_text: "..." }
     ▼
[Backend FastAPI — Python]
     │
     ├─ Étape 1 : STRUCTURATION (LLM)
     │     Groq llama-3.1-8b-instant reçoit le texte brut
     │     → retourne une fiche de poste JSON structurée :
     │        titre, type mission, durée, date démarrage,
     │        localisation, remote, langues, domaine métier,
     │        compétences techniques, soft skills, contexte client
     │
     ├─ Étape 2 : EMBEDDING (Sentence-Transformers)
     │     Le texte structuré est converti en vecteur 384 dimensions
     │     via le modèle paraphrase-multilingual-MiniLM-L12-v2
     │     (multilingue FR/EN, tourne en local dans le container)
     │
     ├─ Étape 3 : RECHERCHE VECTORIELLE (Qdrant)
     │     Le vecteur est comparé aux 50 CVs indexés dans Qdrant
     │     via similarité cosinus → score 0.0 à 1.0 par CV
     │
     ├─ Étape 4 : SCORING MULTI-CRITÈRES
     │     Score final /100 = somme pondérée :
     │     ┌─────────────────┬──────┬──────────────────────────────────────┐
     │     │ Critère         │ Max  │ Logique                              │
     │     ├─────────────────┼──────┼──────────────────────────────────────┤
     │     │ Compétences     │  55  │ Score cosinus × 55                   │
     │     │ Domaine métier  │  25  │ 25 si domaine exact, 12 si similaire │
     │     │ Disponibilité   │  15  │ 15 si intercontrat immédiat          │
     │     │ Localisation    │   5  │ Ville + remote matchés               │
     │     └─────────────────┴──────┴──────────────────────────────────────┘
     │
     │     Domaines similaires configurés :
     │       finance ↔ assurance
     │       telecom ↔ innovation
     │       industrie ↔ mobilite
     │
     ├─ Étape 5 : EXPLICATIONS (LLM)
     │     Pour chaque consultant retenu, Groq génère en parallèle
     │     une phrase d'explication personnalisée (ex: "Expert Java avec
     │     expérience bancaire confirmée, disponible immédiatement à Paris")
     │
     └─ Réponse JSON : fiche de poste + liste classée de consultants
          avec score détaillé, compétences matchées/manquantes,
          disponibilité, localisation, domaines, email de contact

     │
     ▼
[Interface Web]
     │  Affiche la fiche de poste générée + les consultants matchés
     │  Le commercial peut cliquer "Envoyer au staffing"
     ▼
[Email HTML automatique]
     SMTP → liste de destinataires configurée dans Administration
     Contenu : fiche de poste + tableau des consultants avec scores
```

### Infrastructure (Docker Compose sur VPS OVH)

```
┌─────────────────────────────────┐
│  VPS OVH — Ubuntu 26.04         │
│  IP : 51.83.44.48               │
│                                 │
│  ┌──────────────────────────┐   │
│  │ matchconsult_frontend    │   │  :80  → nginx sert le build React
│  │ (nginx + React build)    │   │
│  └──────────────────────────┘   │
│  ┌──────────────────────────┐   │
│  │ matchconsult_backend     │   │  :8000 → FastAPI (Python)
│  │ (FastAPI + sentence-     │   │         sentence-transformers local
│  │  transformers)           │   │         appels Groq API (externe)
│  └──────────────────────────┘   │
│  ┌──────────────────────────┐   │
│  │ matchconsult_qdrant      │   │  :6333 → base vectorielle Qdrant
│  │ (base vectorielle)       │   │          stocke les embeddings des CVs
│  └──────────────────────────┘   │
└─────────────────────────────────┘
```

---

## 3. Cas de tests basiques

### Pré-requis

- Avoir déployé la solution sur le VPS (`docker compose up -d`)
- Avoir uploadé au moins un CV dans `backend/data/cvs/`
- Avoir configuré la clé API Groq dans `⚙ Administration` ou dans `.env`

---

### Test 1 — Structuration d'un email client (LLM)

**Objectif :** Vérifier que le LLM analyse correctement un texte libre.

**Action :** Coller ce texte dans le champ "Expression de besoin" :

```
Bonjour,
Nous avons besoin d'un développeur Java Senior pour une mission de 6 mois
chez un de nos clients dans le secteur bancaire à Paris.
Stack : Java 17, Spring Boot, microservices, Kafka.
Démarrage : début juillet. Remote partiel possible. Anglais courant requis.
```

**Résultat attendu :**
- Titre : `Développeur Java Senior`
- Domaine : `finance` (ou `assurance`)
- Compétences : `Java 17`, `Spring Boot`, `microservices`, `Kafka`
- Localisation : `Paris`, Remote : `partial`
- Langues : `FR`, `EN`
- Date démarrage : `juillet 2025` (ou proche)

---

### Test 2 — Matching des consultants

**Objectif :** Vérifier que les consultants sont classés avec un score cohérent.

**Action :** Même texte que Test 1. Observer les résultats.

**Ce qu'il faut vérifier :**
- Les consultants avec `domaine: finance` ou `assurance` apparaissent **en tête** (bonus +25 ou +12 pts)
- Les consultants `intercontrat` ont un **score de disponibilité élevé** (+ 15 pts)
- Le détail du score est visible sur chaque carte (barre compétences / domaine / disponibilité / localisation)

---

### Test 3 — Filtres avancés

**Objectif :** Vérifier que les filtres réduisent les résultats.

**Action :**
1. Ouvrir "Filtres de recherche"
2. Cocher "Intercontrat uniquement"
3. Sélectionner domaine `telecom`
4. Lancer l'analyse

**Résultat attendu :** Seuls les consultants en intercontrat et ayant `telecom` ou `innovation` dans leurs domaines apparaissent.

---

### Test 4 — Mode démo (sans CV)

**Objectif :** Vérifier que l'application fonctionne sans CVs chargés.

**Action :** Lancer une analyse — si aucun CV n'est indexé dans Qdrant, la liste des consultants sera vide mais la fiche de poste sera bien générée.

**À vérifier :** L'interface affiche bien `0 consultants matchés` sans planter.

---

### Test 5 — Page Administration

**Objectif :** Vérifier la configuration à la volée.

**Action :**
1. Aller sur `⚙ Administration`
2. Modifier un destinataire email
3. Cliquer "Enregistrer tout"

**Résultat attendu :** Message de confirmation vert `✓ Configuration enregistrée.`

**Note :** Les mots de passe apparaissent masqués (`***`) en lecture — cela est normal et sécurisé.

---

### Test 6 — Envoi email au staffing

**Objectif :** Vérifier l'envoi de la shortlist par email.

**Pré-requis :** SMTP configuré dans Administration.

**Action :**
1. Lancer une analyse
2. Cliquer "✉ Envoyer au staffing"
3. Sélectionner les consultants souhaités
4. Cliquer "Envoyer"

**Résultat attendu :** Email HTML reçu avec la fiche de poste et le tableau des consultants.

---

### Test 7 — Vérification santé de l'API

**Via curl ou navigateur :**

```bash
# Health check
curl http://51.83.44.48:8000/api/health

# Réponse attendue :
# {"status":"ok","cvs_loaded":N,"model_ready":true,"demo_mode":false}

# Liste des domaines configurés
curl http://51.83.44.48:8000/api/domains
```

---

## 4. Ajouter des CVs

Les CVs sont à déposer sur le serveur dans `/opt/rag-managers/backend/data/cvs/`.  
Formats acceptés : **PDF, DOCX, TXT**.

```bash
# Copier un CV depuis votre poste
scp mon_consultant.pdf ubuntu@51.83.44.48:/opt/rag-managers/backend/data/cvs/

# Redémarrer le backend pour recharger les embeddings
ssh ubuntu@51.83.44.48
cd /opt/rag-managers
docker compose restart backend
```

Le fichier `backend/data/consultants_meta.json` permet d'enrichir les CVs avec des métadonnées (disponibilité, localisation, domaines, email…). Voir le README pour la structure.

---

## 5. Mise à jour de la solution

```bash
ssh ubuntu@51.83.44.48
cd /opt/rag-managers
git pull origin ovh-rag-managers
docker compose up -d --build
```

---

*MatchConsult V2 — Orange Business · Sourcing ESN*
