# 🚀 POUR BIEN LANCER LE VISUALIZER - RÉSUMÉ

## Les 3 Choses Essentielles

### 1️⃣ DÉMARRE LES CONTAINERS

```bash
docker-compose -f docker-compose.v2.yml up -d
sleep 15
```

**Vérifie que tout tourne**:
```bash
docker-compose -f docker-compose.v2.yml ps
```

Doit montrer 6 containers tous "running":
- llm-worker-m1
- llm-worker-m2
- llm-worker-m3
- llm-orchestrator ⭐
- llm-prometheus
- llm-grafana

---

### 2️⃣ ENVOIE UNE REQUÊTE (C'est Important!)

```bash
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello", "max_tokens": 50}'
```

**Doit retourner**:
```json
{
  "worker": "M1",
  "response": "...",
  "latency": 0.052,
  "tokens_generated": 50
}
```

⚠️ **IMPORTANT**: Cette requête "réveille" les loops de healthcheck et WebSocket.
Sans ça, le dashboard montre "Connecting..." indéfiniment.

---

### 3️⃣ OUVRE LE DASHBOARD

```
http://localhost:8000
```

**Tu devrais voir**:
- ✅ Status du WebSocket: "Connected - Receiving live updates"
- ✅ 3 cartes de workers (M1, M2, M3) avec 🟢 (healthy)
- ✅ Connexions: 0-1 chacun
- ✅ Latency: ~50-100ms
- ✅ Circuit breaker: "Normal"
- ✅ Queue size: 0

---

## Génère de la Charge (Optionnel)

```bash
# Boucle simple
for i in {1..10}; do
  curl -X POST http://localhost:8000/infer \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Request '$i'", "max_tokens": 50}' -s &
done
wait
```

**Sur le dashboard tu verras**:
- Connexions montant à 1-2 par worker
- Latency graph montant
- Distribution équitable entre M1, M2, M3

---

## Si tu vois "Connecting..." Indéfiniment

**Cause**: Les loops d'healthcheck n'ont pas démarré

**Fix**:
```bash
# Envoie une requête pour "réveiller" les loops
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "wake", "max_tokens": 5}'

# Attends 2 secondes
sleep 2

# Rafraîchis le dashboard
# (F5 ou Cmd+R)

# Maintenant ça doit dire "Connected"
```

---

## Les 3 Dashboards

```
WebUI (Real-time, 1s update):
→ http://localhost:8000  ⭐⭐⭐ START HERE

Grafana (Professional, 10-30s update):
→ http://localhost:3000
→ Login: admin / admin

Prometheus (Raw metrics DB):
→ http://localhost:9090
→ For PromQL queries
```

---

## Diagnostic Rapide

```bash
# Tout marche?
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8000/stats | python -m json.tool
```

---

## Si Vraiment Rien Ne Marche

```bash
# Redémarrage complet
docker-compose -f docker-compose.v2.yml down -v
docker-compose -f docker-compose.v2.yml up -d
sleep 15

# Test basique
curl http://localhost:8000/health

# Si erreur, voir les logs
docker logs llm-orchestrator
docker logs llm-worker-m1
```

---

## Checklist Avant de Dire "Ça Ne Marche Pas"

- [ ] Containers tous running? (`docker-compose ps`)
- [ ] Port 8000 répond? (`curl http://localhost:8000/health`)
- [ ] Port 8001 répond? (`curl http://localhost:8001/health`)
- [ ] J'ai envoyé une requête? (`curl .../infer`)
- [ ] J'ai attendu 2-3 secondes après? (pour les loops)
- [ ] Le dashboard charge? (`http://localhost:8000`)
- [ ] J'ai vu "Connected" et pas "Connecting..."?

Si tout ça OK → ✅ Ça marche!

---

**À présent lance et dis-moi:**
1. Est-ce que les containers sont tous "running"?
2. Est-ce que tu reçois une réponse de `/infer`?
3. Qu'est-ce que tu vois sur http://localhost:8000?

Je t'aide à partir de là! 🔧
