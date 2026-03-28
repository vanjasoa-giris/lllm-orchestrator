# =====================================================
# LLM Load Balancer - Docker Quick Start Guide
# =====================================================

## Windows

1. **Demarrer** (cree les images et lance les containers):
   ```cmd
   start_docker.bat
   ```

2. **Arreter**:
   ```cmd
   stop_docker.bat
   ```

3. **Redemarrer**:
   ```cmd
   restart_docker.bat
   ```

## Linux / Mac

```bash
# Construction et demarrage
docker-compose build
docker-compose up -d

# Arreter
docker-compose down

# Voir les logs
docker-compose logs -f

# Redemarrer
docker-compose restart
```

## URLs

| Service | URL |
|---------|-----|
| Orchestrateur | http://localhost:8000 |
| Dashboard | http://localhost:8000/ |
| Stats | http://localhost:8000/stats |
| Metrics | http://localhost:8000/metrics |
| Health | http://localhost:8000/health |

## Workers

| Worker | URL |
|--------|-----|
| M1 | http://localhost:8001 |
| M2 | http://localhost:8002 |
| M3 | http://localhost:8003 |

## Commandes Utiles

```bash
# Voir le statut des containers
docker-compose ps

# Voir les logs d'un service
docker-compose logs -f orchestrator
docker-compose logs -f worker-m1

# Executer une commande dans un container
docker exec -it llm-orchestrator bash

# Redemarrer un service
docker-compose restart orchestrator

# Reconstruire sans cache
docker-compose build --no-cache
```

## Test de l'API

```bash
# Health check
curl http://localhost:8000/health

# Inference
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Bonjour, comment ca va?", "max_tokens": 100}'

# Stats
curl http://localhost:8000/stats

# Dead letter queue
curl http://localhost:8000/dead-letter
```

## Connexion a un vrai LLM

### OpenAI
Modifiez `config/workers.docker.yaml`:
```yaml
workers:
  - id: OPENAI-1
    url: https://api.openai.com/v1
    backend: openai
    api_key: sk-your-key
    model_name: gpt-4-turbo-preview
    max_concurrent: 50
```

### vLLM
```yaml
workers:
  - id: VLLM-1
    url: http://your-vllm-server:8000
    backend: vllm
    model_name: meta-llama/Llama-2-70b-chat-hf
    max_concurrent: 20
```
