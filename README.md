# Load Balancing LLM - Projet Test Local

Ce projet implémente un système de load balancing pour l'inférence de modèles de langage (LLM).

---

## Lancer la simulation

### Étape 1 : Construire le projet

```bash
docker-compose -f docker-compose.v2.yml build
```

### Étape 2 : Démarrer tous les services

```bash
docker-compose -f docker-compose.v2.yml up -d
```

### Étape 3 : Attendre le démarrage (15 secondes)

```bash
sleep 15
```

### Étape 4 : Vérifier que tout fonctionne

```bash
docker-compose -f docker-compose.v2.yml ps
```

Doit afficher 8 services en cours d'exécution :
- `llm-rabbitmq`
- `llm-worker-m1`, `llm-worker-m2`, `llm-worker-m3`
- `llm-orchestrator`
- `llm-prometheus`
- `llm-grafana`
- `llm-load-simulator`

---

## Voir le dashboard

Ouvrez dans votre navigateur : **http://localhost:8000**

Autres interfaces disponibles :
| Service | URL | Identifiants |
|---------|-----|--------------|
| **Dashboard** | http://localhost:8000 | - |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | - |
| RabbitMQ | http://localhost:15672 | guest / guest |

---

## Tester manuellement

```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Bonjour", "max_tokens": 50}'
```

---

## Arrêter la simulation

```bash
docker-compose -f docker-compose.v2.yml down
```

---

## Commandes utiles

```bash
# Logs du simulateur de charge
docker logs -f llm-load-simulator

# Logs de l'orchestrateur
docker logs -f llm-orchestrator

# Redémarrer un service
docker-compose -f docker-compose.v2.yml restart orchestrator

# Reconstruire sans cache
docker-compose -f docker-compose.v2.yml build --no-cache
```

---

## Structure du projet

```
├── orchestrator/          # Load Balancer
├── worker/                # Workers LLM
├── config/                # Configuration
├── docker-compose.yml     # Version simple
├── docker-compose.v2.yml  # Version complète (avec RabbitMQ + Monitoring + Simulator)
└── requirements.txt
```
