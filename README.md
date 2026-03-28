# Load Balancing LLM - Projet Test Local

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

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
