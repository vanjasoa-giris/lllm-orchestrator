# Architecture du Système de Load Balancing LLM

## Vue d'ensemble

```
┌─────────────┐     ┌─────────────────────┐     ┌─────────────┐
│   Client    │────▶│   Orchestrateur     │────▶│  Worker M1  │
│  (Requête)  │     │  (Load Balancer)    │     │  (LLM API)  │
└─────────────┘     └─────────────────────┘     └─────────────┘
                           │                            │
                           │                            │
                   ┌───────▼───────┐              ┌─────▼─────┐
                   │   Monitoring  │              │ Worker M2 │
                   │   (Logs/UI)   │              │ (LLM API) │
                   └───────────────┘              └───────────┘
                                                  ┌───────────┐
                                                  │ Worker M3 │
                                                  │ (LLM API) │
                                                  └───────────┘
```

## Composants

### 1. Orchestrateur (Load Balancer)
- **Rôle** : Point d'entrée unique, distribue les requêtes
- **Technologie** : Python/FastAPI ou Go
- **Fonctions** :
  - Healthcheck des workers
  - Routing intelligent
  - Agrégation des réponses
  - Gestion des retries

### 2. Workers (M1, M2, M3)
- **Rôle** : Instances d'inférence LLM simulées
- **Technologie** : Python/FastAPI
- **Fonctions** :
  - Traitement des requêtes
  - Simulation de latence variable
  - Exposition des métriques

### 3. Configuration
- **Fichier** : `config/workers.yaml`
- **Contenu** : Adresses des workers, seuils, timeouts

## Flux de données

1. Client → Orchestrateur (requête)
2. Orchestrateur → Worker sélectionné (via stratégie)
3. Worker → Traitement → Réponse
4. Orchestrateur → Client (réponse centralisée)

## Environnement Local

| Composant | Adresse | Port |
|-----------|---------|------|
| Orchestrateur | localhost | 8000 |
| Worker M1 | localhost | 8001 |
| Worker M2 | localhost | 8002 |
| Worker M3 | localhost | 8003 |

## Déploiement Local

```bash
# Lancer les workers
python worker/main.py --port 8001 --id M1
python worker/main.py --port 8002 --id M2
python worker/main.py --port 8003 --id M3

# Lancer l'orchestrateur
python orchestrator/main.py
```
