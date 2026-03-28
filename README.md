# Load Balancing LLM - Projet Test Local

## 🚀 Quick Start avec Docker (Recommandé)

### Prérequis
- Docker Desktop installé et en cours d'exécution
- Aucune autre installation nécessaire (tout est inclus dans les containers)

### Étape 1 : Démarrer tous les services

**Windows (PowerShell ou CMD) :**
```bash
start_docker.bat
```

**Linux / Mac :**
```bash
docker-compose build
docker-compose up -d
```

### Étape 2 : Attendre le démarrage (10 secondes)

```bash
# Windows
timeout /t 10

# Linux / Mac
sleep 10
```

### Étape 3 : Vérifier que tout fonctionne

```bash
docker-compose ps
```

Doit afficher 4 containers en état "running" :
- `llm-worker-m1`
- `llm-worker-m2`
- `llm-worker-m3`
- `llm-orchestrator`

### Étape 4 : Tester avec une requête

```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Bonjour", "max_tokens": 50}'
```

### Étape 5 : Ouvrir le Dashboard

Accédez à : **http://localhost:8000**

---

## 🛑 Arrêter les services

**Windows :**
```bash
stop_docker.bat
```

**Linux / Mac :**
```bash
docker-compose down
```

---

## 📊 URLs des Services

| Service | URL | Description |
|---------|-----|-------------|
| **Orchestrateur** | http://localhost:8000 | Load Balancer + Dashboard |
| Dashboard | http://localhost:8000/ | Interface Web temps réel |
| Stats | http://localhost:8000/stats | Métriques JSON |
| Health | http://localhost:8000/health | État de santé |
| **Worker M1** | http://localhost:8001 | Instance LLM 1 |
| **Worker M2** | http://localhost:8002 | Instance LLM 2 |
| **Worker M3** | http://localhost:8003 | Instance LLM 3 |

---

## 📋 Commandes Utiles

```bash
# Voir les logs en temps réel
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f orchestrator
docker-compose logs -f worker-m1

# Redémarrer un service
docker-compose restart orchestrator

# Reconstruire sans cache
docker-compose build --no-cache

# Exécuter une commande dans un container
docker exec -it llm-orchestrator bash
```

---

## Installation Locale (Alternative)

```bash
pip install -r requirements.txt
```

## Lancement Manuel (Sans Docker)

### Terminal 1 - Worker M1
```bash
python worker/main.py --port 8001 --id M1
```

### Terminal 2 - Worker M2
```bash
python worker/main.py --port 8002 --id M2
```

### Terminal 3 - Worker M3
```bash
python worker/main.py --port 8003 --id M3
```

### Terminal 4 - Orchestrateur
```bash
python orchestrator/main.py
```

## API Endpoints

| Service | Endpoint | Description |
|---------|----------|-------------|
| Orchestrateur | `POST /infer` | Envoyer une requête |
| Orchestrateur | `GET /health` | État de santé |
| Orchestrateur | `GET /stats` | Métriques |
| Worker | `GET /health` | Healthcheck worker |
| Worker | `GET /metrics` | Métriques worker |

## Test

```bash
pytest tests/ -v
```

## Exemple de requête

```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Bonjour", "max_tokens": 50}'
```

## Structure du projet

```
├── orchestrator/
│   └── main.py          # Load Balancer
├── worker/
│   └── main.py          # Worker LLM
├── config/
│   └── workers.yaml     # Configuration
├── tests/
│   ├── test_load_balancer.py
│   └── test_integration.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── STRATEGY.md
│   └── RESILIENCE.md
└── requirements.txt
```
