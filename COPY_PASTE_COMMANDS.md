# 📋 COPY-PASTE COMMANDS

Copie-colle directement, ligne par ligne.

---

## ÉTAPE 1: Nettoie (si relance)

```bash
docker-compose -f docker-compose.v2.yml down -v
```

---

## ÉTAPE 2: Démarre

```bash
docker-compose -f docker-compose.v2.yml up -d
```

---

## ÉTAPE 3: Attends 15 secondes

```bash
sleep 15
```

---

## ÉTAPE 4: Vérifie que ça tourne

```bash
docker-compose -f docker-compose.v2.yml ps
```

**Tu devrais voir 6 containers, tous "running"**

---

## ÉTAPE 5: Envoie une requête (C'EST IMPORTANT!)

```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello", "max_tokens": 50}'
```

**Tu devrais voir**:
```json
{"worker": "M1", "response": "...", "latency": 0.05, ...}
```

---

## ÉTAPE 6: Ouvre le dashboard

**Dans ton browser**, copie-colle:
```
http://localhost:8000
```

---

## ÉTAPE 7: Si tu vois "Connecting..."

Attends 2-3 secondes, puis refresh (F5).

Si ça ne marche pas:
```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "wake", "max_tokens": 5}'

sleep 2
```

Puis refresh le browser.

---

## ÉTAPE 8: Génère de la charge (Optionnel)

```bash
for i in {1..10}; do
  curl -X POST http://localhost:8000/infer \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Request '$i'", "max_tokens": 50}' -s &
done
wait
```

**Sur le dashboard tu verras les données arriver en temps réel!**

---

## AUTRES DASHBOARDS (Bonus)

Grafana:
```
http://localhost:3000
Login: admin / admin
```

Prometheus:
```
http://localhost:9090
```

---

## REDÉMARRAGE COMPLET (Si ça crash)

```bash
docker-compose -f docker-compose.v2.yml down
docker system prune -f
docker-compose -f docker-compose.v2.yml up -d
sleep 15
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello", "max_tokens": 50}'
```

Puis ouvre le dashboard: `http://localhost:8000`

---

## VER IF RAPIDE SI ERREUR

```bash
# Logs orchestrator
docker logs llm-orchestrator | tail -30

# Logs worker 1
docker logs llm-worker-m1 | tail -20

# Vérifier les ports
netstat -an | grep 8000
netstat -an | grep 8001
```

---

**C'est tout! Lance étape par étape et dis-moi ce que tu vois! 🚀**
