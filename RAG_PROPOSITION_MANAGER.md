# Proposition — Environnement de test RAG partagé

## Contexte

Dans le cadre de l'atelier ML, nous souhaitons mettre en place un **RAG** (Retrieval-Augmented Generation) :
un assistant qui répond à des questions en langage naturel en s'appuyant sur la documentation du projet,
et non sur une connaissance générale. Exemple : *"Comment fonctionne le warm start ?"* → réponse précise
tirée de nos propres fichiers.

Pour que l'équipe puisse tester et développer cette brique, nous avons besoin d'un environnement partagé,
accessible depuis un navigateur, disponible 24h/24 sans dépendre du poste d'un développeur.

---

## Ce que nous proposons

Un serveur loué en Europe, avec une interface web accessible à toute l'équipe via un lien.

```
                    Équipe (navigateur)
                           ↓
              ┌────────────────────────┐
              │   Serveur Hetzner      │  ← Nos données, notre code
              │   Allemagne            │     Base de recherche (Qdrant)
              │   Ubuntu + Docker      │     Interface web de test (Streamlit)
              └──────────┬─────────────┘
                         ↓  appel sécurisé HTTPS
                    API Groq (cloud)
                    Intelligence artificielle
                    Llama 3.1 8B — modèle open-source
```

Le modèle d'IA **ne tourne pas sur notre serveur** : il est appelé à la demande via une API externe.
Aucun GPU n'est nécessaire de notre côté.

---

## Choix technologiques

| Composant | Technologie | Pourquoi ce choix |
|-----------|-------------|-------------------|
| Serveur | Hetzner CX22 — Allemagne | Hébergeur européen fiable, RGPD, moins cher qu'AWS/Azure |
| Base de recherche | Qdrant (open-source) | Spécialisé recherche sémantique, pas de vendor lock-in |
| Modèle IA | Llama 3.1 8B via Groq | Modèle open-source, multilingue FR/EN, très rapide (<1 s) |
| Interface | Streamlit (Python) | Développement rapide, adapté aux équipes data/ML |
| Déploiement | Docker | Reproductible, facile à maintenir |

---

## Gestion des données — qui fait quoi

La base de recherche (Qdrant) stocke les documents du projet sous forme vectorielle.
Sa gestion ne demande aucune maintenance régulière.

| Rôle | Qui | Action |
|------|-----|--------|
| Administrateur | 1 dev désigné | Lance la ré-indexation quand les documents changent (1 commande) |
| Développeur | Toute l'équipe | Pose des questions via l'interface web — ne touche pas à la base |

Les données sont persistantes : elles survivent aux redémarrages du serveur sans aucune intervention.
Un dashboard de supervision est accessible à l'administrateur pour vérifier ce qui est indexé.

---

## Coût mensuel estimé

| Poste | Coût |
|-------|------|
| Serveur Hetzner CX22 (2 vCPU, 4 Go RAM, Allemagne) | **3,79 €/mois** |
| API Groq — modèle Llama 3.1 8B | **0 € (free tier)** |
| **Total** | **3,79 €/mois** |

Le free tier Groq couvre environ 500 000 tokens par jour — largement suffisant pour une équipe
de développeurs en phase de test. En cas de dépassement, le surcoût resterait **inférieur à 5 €/mois**.

---

## Ce que l'équipe peut faire avec cet environnement

- Poser des questions sur le projet en français depuis un navigateur, sans rien installer
- Voir quelles parties de la documentation ont servi à construire la réponse
- Tester et faire évoluer le RAG sans infrastructure lourde ni dépendance à un poste individuel
- Partager les résultats sur une URL commune, disponible 24h/24

---

*Mise en place estimée : 1 journée développeur. Aucune maintenance particulière ensuite.*
