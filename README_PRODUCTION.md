# Livrable 4 : Code Production-Ready pour LLM Load Balancer

## 📦 Contenu

### Fichier Principal
- **`orchestrator/main_production_final.py`** - Orchestrateur production complet

### Entry Points
- **`orchestrator_entrypoint_production.py`** - Point d'entrée pour l'orchestrateur
- **`worker/main_llm.py`** - Worker production (inchangé, déjà complet)

### Configuration
- **`config/workers.yaml`** - Configuration production-ready

### Déploiement
- **`deploy.sh`** - Script de déploiement Linux/Mac

## 🚀 Démarrage Rapide

### Option 1: Script de déploiement
```bash
chmod +x deploy.sh
./deploy.sh start
```

### Option 2: Manuel
```bash
# Terminal 1: Workers
python3 worker/main_llm.py --id M1 --port 8001 --backend simulated &
python3 worker/main_llm.py --id M2 --port 8002 --backend simulated &
python3 worker/main_llm.py --id M3 --port 8003 --backend simulated &

# Terminal 2: Orchestrateur
python3 orchestrator_entrypoint_production.py
```

### Option 3: Docker
```bash
docker-compose -f docker-compose.yml up
```

## 🔧 API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/infer` | POST | Inference LLM |
| `/infer/raw` | POST | Inference avec payload raw |
| `/stats` | GET | Statistiques détaillées |
| `/health` | GET | Health check |
| `/metrics` | GET | Metrics Prometheus |
| `/ws` | WebSocket | Real-time updates |
| `/queue/{id}` | GET/DELETE | Statut/annulation queue |
| `/dead-letter` | GET/DELETE | Requêtes échouées |

## 📊 Fonctionnalités Implémentées

### ✅ Load Balancing
- Token-aware routing (40% poids)
- Latency-based scoring (30% poids)
- Availability scoring (30% poids)
- Least connections

### ✅ Résilience
- Circuit Breaker (CLOSED → OPEN → HALF_OPEN)
- Health checks périodiques (5s)
- Auto-recovery (2 succès consécutifs)

### ✅ Queue Management
- Priority queue (heap-based)
- TTL (300s)
- Auto-retry avec exponential backoff
- Dead letter queue pour échecs

### ✅ Rate Limiting
- 60 req/min par défaut
- Configurable

### ✅ Distributed Tracing
- Request IDs propagés
- Headers X-Request-ID

### ✅ Observabilité
- Prometheus metrics
- WebSocket real-time
- Detailed stats per worker

## 🔗 Connexion à un vrai LLM

### OpenAI
```yaml
workers:
  - id: OPENAI-1
    url: https://api.openai.com/v1
    backend: openai
    api_key: sk-xxx
    model_name: gpt-4-turbo-preview
```

### vLLM
```yaml
workers:
  - id: VLLM-1
    url: http://192.168.1.100:8000
    backend: vllm
    model_name: meta-llama/Llama-2-70b-chat-hf
```

### HuggingFace Transformers
```yaml
workers:
  - id: HF-1
    url: http://localhost:8004
    backend: hf_transformers
    model_name: meta-llama/Llama-2-7b-hf
```

## 📁 Structure des Fichiers

```
test_part_2/
├── orchestrator/
│   └── main_production_final.py   # ⭐ VERSION PRODUCTION
├── worker/
│   └── main_llm.py                # Worker production
├── config/
│   └── workers.yaml               # Configuration
├── orchestrator_entrypoint_production.py
├── deploy.sh                      # Script déploiement
└── README_PRODUCTION.md
```

## 🔒 Sécurité

- Rate limiting par IP client
- Headers X-Request-ID pour tracing
- Timeout configurable (60s)
- Graceful shutdown

## 📈 Monitoring

```bash
# Metrics Prometheus
curl http://localhost:8000/metrics

# Stats JSON
curl http://localhost:8000/stats

# Health check
curl http://localhost:8000/health

# Queue status
curl http://localhost:8000/queue/{queue_id}

# Dead letter
curl http://localhost:8000/dead-letter
```
