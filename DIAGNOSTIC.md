# 🔍 DIAGNOSTIC - POURQUOI TU NE VOIS RIEN

Copie-colle ce diagnostic et envoie-moi la sortie.

```bash
#!/bin/bash

echo "========== DIAGNOSTIC LLM ORCHESTRATOR =========="
echo ""

echo "[1] Docker et Docker Compose"
docker --version
docker-compose --version
echo ""

echo "[2] Containers running?"
docker-compose -f docker-compose.v2.yml ps
echo ""

echo "[3] Test port 8000 (Orchestrator)"
curl -s http://localhost:8000/health || echo "❌ Port 8000 not responding"
echo ""

echo "[4] Test port 8001 (Worker M1)"
curl -s http://localhost:8001/health || echo "❌ Port 8001 not responding"
echo ""

echo "[5] Test endpoint /infer"
curl -s -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "max_tokens": 10}' || echo "❌ /infer failed"
echo ""

echo "[6] Orchestrator logs (last 20 lines)"
docker logs --tail 20 llm-orchestrator 2>&1 || echo "❌ No orchestrator logs"
echo ""

echo "[7] Worker M1 logs (last 10 lines)"
docker logs --tail 10 llm-worker-m1 2>&1 || echo "❌ No worker logs"
echo ""

echo "[8] Prometheus targets"
curl -s http://localhost:9090/api/v1/targets 2>&1 | head -20 || echo "❌ Prometheus not responding"
echo ""

echo "[9] Prometheus metrics"
curl -s http://localhost:9000/metrics 2>&1 | head -5 || echo "❌ Metrics endpoint not responding"
echo ""

echo "[10] Network inspection"
docker network inspect llm-network 2>&1 | grep -A 30 "Containers" || echo "❌ Network not found"
echo ""

echo "========== END DIAGNOSTIC =========="
```

---

## Copies ce diagnostic et run-le:

```bash
bash diagnostic.sh
```

---

## Puis réponds à ces questions:

1. **Les containers tournent?** (all "running"?)
   - [ ] Oui
   - [ ] Non → Lesquels sont pas up?

2. **Port 8000 répond?**
   - [ ] Oui (status 200)
   - [ ] Non (Connection refused / Timeout)

3. **Port 8001 répond?**
   - [ ] Oui (healthy)
   - [ ] Non (Connection refused)

4. **Endpoint /infer fonctionne?**
   - [ ] Oui (retourne JSON avec "worker")
   - [ ] Non (error / timeout)

5. **Les logs de l'orchestrator?** (copie-colle les erreurs)
   - ...

6. **Les logs des workers?** (copie-colle les erreurs)
   - ...

7. **Prometheus scrape les targets?**
   - [ ] Oui (tous "UP")
   - [ ] Non (tous "DOWN" ou erreur)

8. **WebUI accessible?**
   - [ ] Oui (http://localhost:8000 charge une page)
   - [ ] Non (blank page / "Connecting...")

---

## Problèmes communs et solutions

### "Connection refused" sur port 8000
```bash
# Cause 1: Container pas démarré
docker logs llm-orchestrator

# Cause 2: Port utilisé par autre chose
lsof -i :8000

# Cause 3: Container crash au démarrage
docker-compose -f docker-compose.v2.yml up  # (pas -d) pour voir logs
```

### "Connecting..." sur WebUI mais rien ne charge
```bash
# Cause: Pas de requête d'inférence envoyée
# Les loops de healthcheck n'ont pas commencé

# Solution: Envoie une requête d'abord
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "wake", "max_tokens": 5}'

# Puis rafraîchis le browser
```

### Workers pas en communication
```bash
# Vérification: Sont-ils sur le même network?
docker network inspect llm-network

# Doit lister 4 containers: orch + M1 + M2 + M3

# Si pas là: Redémarre tout
docker-compose -f docker-compose.v2.yml down
docker-compose -f docker-compose.v2.yml up -d
```

### Prometheus ne scrape pas
```bash
# Vérification: Config file existe?
cat config/prometheus.yml

# Doit avoir des "static_configs" avec targets

# Si manquant: Crée le fichier ou copie depuis config/

# Si existe mais Prometheus pas à jour: Redémarre
docker-compose -f docker-compose.v2.yml restart prometheus
```

---

## Envoie-moi exactement:

1. **Commande** que tu as lancée
2. **Résultat complet** du diagnostic
3. **Erreurs** visibles dans les logs
4. **Ce que tu vois** sur http://localhost:8000

Et je t'aiderai à fixer! 🔧
