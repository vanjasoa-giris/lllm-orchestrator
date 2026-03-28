# 🚀 GUIDE DE DÉMARRAGE - LLM ORCHESTRATOR VISUALIZER

## 🎯 ÉTAPE 1: Vérification des Prérequis

### Vérifie que tu as Docker et Docker Compose
```bash
docker --version      # Doit être >= 20.10
docker-compose --version  # Doit être >= 2.0
```

### ✅ Si tu as:
```
Docker version 29.2.1 ✅
Docker Compose v5.1.0 ✅
```

---

## 🚀 ÉTAPE 2: Nettoyage Initial

Si tu relances après avoir testé avant:

```bash
# Arrête tout
docker-compose -f docker-compose.v2.yml down

# Supprime les volumes (réinitialise Prometheus + Grafana)
docker volume rm llm-prometheus-data 2>/dev/null || true
docker volume rm llm-grafana-data 2>/dev/null || true

# Nettoie les images
docker system prune -f
```

---

## 🚀 ÉTAPE 3: Démarrer le Stack Complet

**Option A: Commande Simple (Recommandée)**

```bash
# À la racine du projet
cd /chemin/vers/llm-orchestrator

# Démarre tout
docker-compose -f docker-compose.v2.yml up -d

# Affiche le status
docker-compose -f docker-compose.v2.yml ps
```

**Attendus après 10-15 secondes**:
```
NAME                        STATUS
llm-worker-m1              running
llm-worker-m2              running
llm-worker-m3              running
llm-orchestrator           running
llm-prometheus             running
llm-grafana                running
```

**Option B: Avec Logs Visibles (Pour Déboguer)**

```bash
# Démarre tout avec logs
docker-compose -f docker-compose.v2.yml up

# (Tu veras les logs en temps réel)
# Ctrl+C pour arrêter (containers continuent de tourner)
```

---

## 🎨 ÉTAPE 4: Accéder aux Dashboards

### WebUI Real-Time (PLUS IMPRESSIONNANT!)
```
http://localhost:8000
```
- Status cards des workers (🟢🔴🟠)
- Latency graph en temps réel
- Queue size monitoring
- Mises à jour: toutes les 1 seconde

### Grafana (Professional Dashboards)
```
http://localhost:3000
Login: admin / admin
```
- Pre-built dashboards
- RPS graph
- Latency trends
- Worker connections

### Prometheus (Metrics DB)
```
http://localhost:9090
```
- Time series database
- Query interface (PromQL)
- Targets status

---

## 🧪 ÉTAPE 5: Générer de la Charge

### Terminal Nouveau (pendant que Docker tourne)

```bash
# Vérifie que les workers répondent
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health

# Doit retourner: {"status": "healthy", "worker_id": "M1"}
```

### Envoyer une Première Requête

```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello", "max_tokens": 50}'

# Doit retourner: {"worker": "M1", "response": "...", "latency": 0.045, ...}
```

### Voir les Métriques

```bash
# Endpoint metrics
curl http://localhost:8000/metrics | head -30

# Doit montrer les métriques Prometheus
```

### Stats Globales

```bash
curl http://localhost:8000/stats | python -m json.tool

# Doit montrer l'état de tous les workers
```

---

## 🔄 ÉTAPE 6: Générer Charge Réaliste

Si tu as `demo_load.py`:

```bash
python demo_load.py
```

Sinon, génère manuellement:

```bash
# Boucle simple (10 requêtes rapides)
for i in {1..10}; do
  curl -X POST http://localhost:8000/infer \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Test '$i'", "max_tokens": 50}' \
    -s | jq '.worker, .latency'
done
```

**Pendant la boucle**:
1. Ouvre `http://localhost:8000` dans un browser
2. Tu verras les workers s'illuminer (🟢)
3. Latency graph montant
4. Connections counter changeant

---

## ✅ ÉTAPE 7: Vérifier que Tout Fonctionne

### Checklist d'Inspection

```bash
# 1. Tous les containers tournent?
docker-compose -f docker-compose.v2.yml ps
# Status: running pour tous les 6 services

# 2. Workers répondent au health check?
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
# Status: "healthy"

# 3. Orchestrator route les requêtes?
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "max_tokens": 10}'
# Status: 200, has "worker" field

# 4. WebUI accessible?
curl http://localhost:8000
# HTML page returned

# 5. Prometheus scrape les metrics?
curl http://localhost:9090/api/v1/targets
# Doit lister les 4 targets (orch + 3 workers)

# 6. Grafana accessible?
curl -u admin:admin http://localhost:3000/api/user
# HTTP 200, returns user info
```

---

## 🐛 TROUBLESHOOTING

### "Je n'vois rien sur le Dashboard"

**Cause 1: WebUI ne s'affiche pas**
```bash
# Vérifie que l'orchestrator tourne
docker logs llm-orchestrator | tail -20

# Doit afficher:
# "Uvicorn running on http://0.0.0.0:8000"
```

**Cause 2: Dashboard dit "Connecting..."**
```bash
# Vérifie le WebSocket endpoint
docker logs llm-orchestrator | grep -i websocket

# Essaye une requête d'inférence d'abord
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello", "max_tokens": 10}'

# Puis rafraîchis le dashboard
```

**Cause 3: Pas de données dans Prometheus**
```bash
# Attends 20-30 secondes (première scrape)
# Puis va à: http://localhost:9090/api/v1/targets
# Tous les targets doivent être "UP"

# Si DOWN, vérifie les logs:
docker logs llm-prometheus
docker logs llm-orchestrator
```

### "Containers ne démarrent pas"

```bash
# Vérifie les erreurs de build
docker-compose -f docker-compose.v2.yml build --no-cache

# Vérifie les logs détaillés
docker-compose -f docker-compose.v2.yml up

# Cherche les erreurs
```

### "Port déjà utilisé (8000, 8001, etc)"

```bash
# Voir qui utilise le port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Tue le processus ou change le port dans docker-compose.v2.yml
```

### "WebUI affiche "Disconnected" en rouge"

```bash
# Le WebSocket n'est pas connecté
# Cause 1: L'orchestrator n'a pas démarré les loops
# Solution: Envoie une requête d'abord

curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "wake up", "max_tokens": 10}'

# Puis vérifie le dashboard (should say "Connected")
```

---

## 🎬 FLUX COMPLET DE TEST

**Temps total: ~5 minutes**

```bash
# T+0: Nettoie (si relance)
docker-compose -f docker-compose.v2.yml down
docker volume prune -f

# T+1: Démarre
docker-compose -f docker-compose.v2.yml up -d
sleep 15  # Attends que tout soit prêt

# T+16: Vérifie les workers
curl http://localhost:8001/health

# T+20: Ouvre le dashboard en browser
# http://localhost:8000

# T+21: Envoie des requêtes (dans un autre terminal)
for i in {1..20}; do
  curl -X POST http://localhost:8000/infer \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Req '$i'", "max_tokens": 50}' -s
  sleep 0.5
done

# T+50: Vérifie les dashboards
# - WebUI: http://localhost:8000 (should show activity)
# - Grafana: http://localhost:3000 (login admin/admin)
# - Prometheus: http://localhost:9090/targets (should show UP)

# T+60+: Analyse les résultats
```

---

## 📊 CE QUE TU DEVRAIS VOIR

### Sur le WebUI (http://localhost:8000)

```
┌─────────────────────────────────────┐
│  LLM Load Balancer Dashboard        │
├─────────────────────────────────────┤
│                                     │
│  Queue Size: 0                      │
│  Active Connections: 3              │
│  Healthy Workers: 3                 │
│                                     │
│  ┌──────────┐  ┌──────────┐        │
│  │   M1     │  │   M2     │        │
│  │ 🟢Healthy│  │ 🟢Healthy│        │
│  │ Conn: 1  │  │ Conn: 1  │        │
│  │ Lat: 52ms│  │ Lat: 48ms│        │
│  └──────────┘  └──────────┘        │
│                                     │
│  [Latency Graph - Line Chart]       │
│  [Connections - Bar Chart]          │
│                                     │
└─────────────────────────────────────┘
```

### Dans les Logs (docker-compose logs)

```
llm-orchestrator    | INFO:     Application startup complete
llm-worker-m1       | Starting worker M1 on port 8001
llm-worker-m2       | Starting worker M2 on port 8002
llm-worker-m3       | Starting worker M3 on port 8003
llm-prometheus      | Listening on :9090
llm-grafana         | Listening on port 3000
```

---

## 🚫 SI RIEN NE FONCTIONNE

### Étape 1: Redémarrage Complet

```bash
# Arrête tout brutalement
docker-compose -f docker-compose.v2.yml down -v

# Nettoie les images
docker system prune -af

# Redémarre
docker-compose -f docker-compose.v2.yml up --build
```

### Étape 2: Vérifie les Logs Détaillés

```bash
# Chaque container individuellement
docker logs llm-orchestrator
docker logs llm-worker-m1
docker logs llm-prometheus
docker logs llm-grafana

# Cherche les erreurs (ERROR, CRITICAL, exception)
```

### Étape 3: Test Manuel (Sans Docker)

```bash
# Si Docker ne marche pas, teste en local
pip install -r requirements.txt

# Terminal 1
python worker/main.py --port 8001 --id M1

# Terminal 2
python worker/main.py --port 8002 --id M2

# Terminal 3
python worker/main.py --port 8003 --id M3

# Terminal 4
python orchestrator/main_v2.py

# Terminal 5
curl http://localhost:8000/health
```

---

## ✅ RÉSUMÉ QUICK

```bash
# START
docker-compose -f docker-compose.v2.yml up -d

# WAIT
sleep 15

# CHECK
docker-compose -f docker-compose.v2.yml ps

# ACCESS
http://localhost:8000        # WebUI ⭐
http://localhost:3000        # Grafana
http://localhost:9090        # Prometheus

# TEST
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello", "max_tokens": 50}'

# LOAD
python demo_load.py  # si exists

# WATCH
# Rafraîchis http://localhost:8000 pour voir les updates
```

---

**À présent tu devrais voir le dashboard s'animer! 🎉**

Si tu vois encore rien, signale-moi exactement:
1. Commande que tu as lancée
2. Erreur précise que tu reçois (ou rien n'apparaît)
3. Résultat de `docker-compose -f docker-compose.v2.yml ps`
