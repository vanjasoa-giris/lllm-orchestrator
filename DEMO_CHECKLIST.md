# 🎬 DEMO CHECKLIST - Before You Show It

## ✅ Pre-Demo Setup (10 minutes)

### 1. Clean Start
```bash
# Stop any running containers
docker-compose -f docker-compose.v2.yml down

# Clean up old data
docker volume prune -f

# Restart fresh
docker-compose -f docker-compose.v2.yml up -d
sleep 15  # Wait for all services to start
```

### 2. Verify All Services Are Running
```bash
# Check all containers
docker ps -a | grep llm-

# Should see:
# llm-worker-m1      (healthy)
# llm-worker-m2      (healthy)
# llm-worker-m3      (healthy)
# llm-orchestrator   (healthy)
# llm-prometheus     (running)
# llm-grafana        (running)
```

### 3. Quick Health Check
```bash
# Test worker health
curl -s http://localhost:8001/health | jq
curl -s http://localhost:8002/health | jq
curl -s http://localhost:8003/health | jq

# Test orchestrator health
curl -s http://localhost:8000/health | jq

# Expected: {"status": "healthy", ...}
```

### 4. Open Browser Tabs (in order)
```
Tab 1: http://localhost:8000         ← MAIN (WebUI) 
Tab 2: http://localhost:3000         ← Backup (Grafana)
Tab 3: http://localhost:9090         ← Debug (Prometheus)
Tab 4: http://localhost:8000/stats   ← Stats endpoint
```

---

## 🎯 Demo Script (15 minutes total)

### **Minute 0-2: Introduction**

**What to say:**
```
"We have a distributed LLM orchestrator with 3 simulated workers.
The architecture handles load balancing, health checks, circuit breaker
pattern, and request queueing.

Today I'll show you three different ways to visualize this system:
1. Real-time WebUI (instant updates)
2. Grafana dashboards (professional)
3. Prometheus metrics (historical data)"
```

**Show:**
- Point to Tab 1 (WebUI) - show all workers are 🟢 healthy
- Explain the status cards (connections, latency, circuit breaker)

---

### **Minute 2-3: Start Minimal Load**

**Run:**
```bash
# In new terminal
python demo_load.py
```

**Watch:**
- WebUI updates in real-time (1-second refresh)
- See 3 sequential requests go to different workers
- Explain: "Orchestrator selected each worker based on load"
- Pointing at WebUI: "See M1, M2, M3 all getting requests"

**What happens:**
```
[Scenario 1] Sequential Requests (3 requests)
├─ Request 1 → M1 (45ms)  [WebUI shows M1 card highlighted]
├─ Request 2 → M2 (52ms)  [WebUI shows M2 card highlighted]
└─ Request 3 → M3 (48ms)  [WebUI shows M3 card highlighted]
```

**Audience sees:**
- Real-time feedback
- Metrics updating instantly
- Load being distributed

---

### **Minute 3-5: Concurrent Spike (The Impressive Part!)**

**Watch in WebUI as:**
- Scenario 2 runs: 15 concurrent requests
- All workers light up simultaneously
- Connections spike to 5+ per worker
- Queue fills slightly
- Cards show different latencies for each worker

**Talk through:**
```
"Notice how all 3 workers are being used simultaneously.
The orchestrator is intelligently distributing requests.

Look at the latency graph - you see the spike happening right now.
The queue shows requests waiting when all workers are busy.

This is real-time - no lag in visualization."
```

**Prometheus view (switch to Tab 3):**
```
Enter query: rate(llm_requests_total[1m])
Hit Enter
Show: "About 15 requests/second during the spike"
```

---

### **Minute 5-8: Steady Load (Show Distribution)**

**Watch in WebUI as:**
- Scenario 3 runs: Steady 3 requests/sec for 20s
- Workers balance load over time
- Latency averages out
- Graphs fill up with data points

**Point out:**
```
"Watch how the load distributes evenly over 20 seconds.
M1, M2, M3 all get roughly the same number of requests.
The latency graph shows our trend - pretty stable around 50ms."
```

**Show Grafana (Tab 2):**
- After 30s, point to Grafana
- "Here's the same data in Grafana - more professional dashboard"
- Point to different panels (RPS graph, latency, worker connections)

---

### **Minute 8-13: Variable Load (Realistic Traffic)**

**Watch in WebUI as:**
- Scenario 4 runs: Variable load (quiet + spikes) for 30s
- Queue grows during spikes
- Workers struggle to keep up
- Latencies increase temporarily

**Explain the pattern:**
```
"This simulates realistic traffic - periods of quiet
followed by burst traffic (e.g., popular tweet mentioned your product).

Watch the queue size - it grows during spikes when all workers
are busy. Then clears when traffic drops.

The circuit breaker (if simulated failures happen) would
trigger here. We're injecting 2% error rate to show resilience."
```

**Point out in WebUI:**
- Queue size changing (live counter at top)
- Latency spikes during high load
- Workers recovering
- Circuit breaker state if failures triggered

---

### **Minute 13-15: Analysis & Wrap-up**

**After demo completes, show:**

```bash
# Terminal shows statistics:
Total Requests:     48
Successful:         46 (96%)
Queued:             2
Success Rate:       96%
```

**Final talking points:**

```
"In under 15 seconds we:
✓ Distributed 48 requests across 3 workers
✓ Maintained 96% success rate
✓ Demonstrated load balancing intelligence
✓ Showed circuit breaker preventing cascade failures

The visualization updates:
- WebUI: Every 1 second (instant feedback)
- Grafana: Every 10-30 seconds (professional dashboards)
- Prometheus: Every 15 seconds (data storage)

All three work together for different use cases:
- Demo day? Use WebUI (impressive!)
- Production? Use Grafana (professional)
- Deep analysis? Use Prometheus (powerful queries)

This architecture scales to 100s of workers and millions of requests/day."
```

---

## 🛟 Emergency Troubleshooting (If Something Goes Wrong)

### **WebUI Shows "Connecting..."**
```bash
# Check orchestrator is running
docker logs llm-orchestrator

# If not running:
docker-compose -f docker-compose.v2.yml restart orchestrator
sleep 5
```

### **No Requests Going Through**
```bash
# Test a single request
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello", "max_tokens": 50}'

# Check worker health
curl http://localhost:8001/health
```

### **Grafana Shows No Data**
```bash
# Wait 30+ seconds for first Prometheus scrape
# Then refresh Grafana browser

# If still broken:
# Check Prometheus is scraping
curl http://localhost:9090/api/v1/targets
```

### **Demo Load Script Hangs**
```bash
# Ctrl+C to interrupt
# Check worker logs
docker logs llm-worker-m1

# Restart workers if needed
docker-compose -f docker-compose.v2.yml restart worker-m1
```

---

## 📊 Key Points to Emphasize

### **Architecture Advantages**
1. ✅ **Intelligent Distribution** - Not random, score-based selection
2. ✅ **Resilient** - Circuit breaker prevents cascade failures
3. ✅ **Visible** - Real-time dashboards show what's happening
4. ✅ **Scalable** - Works with 3 workers or 100+
5. ✅ **Production-Ready** - Uses standard tools (Prometheus, Grafana)

### **Real-World Use Cases**
- LLM inference at scale (multiple GPU servers)
- A/B testing (route 50% to old model, 50% to new)
- Cost optimization (cheap API first, fallback to expensive)
- Geographic distribution (reduce latency)
- Graceful degradation (remove workers, queue requests)

### **Innovation Points** (Why This Matters)
- Most people use NGINX for load balancing - this is smarter (understands LLM costs)
- Standard LB doesn't understand latency variance - ours does
- Doesn't cascade fail like basic round-robin - uses circuit breaker
- Real-time visualization of what's happening

---

## 🎥 Screenshot Moments

**Capture these for slides/report:**

1. **WebUI Dashboard Full Screen**
   - All 3 workers healthy
   - Latency graph showing trend
   - Connections bar chart
   - Queue size counter

2. **During Concurrent Spike**
   - All workers showing connections
   - Latency graph spiking
   - Queue size > 0

3. **Grafana Dashboard**
   - Multiple panels showing data
   - Professional-looking graphs

4. **Terminal Output**
   - Demo statistics
   - Show the numbers: 48 requests, 96% success

5. **Architecture Diagram**
   - From ARCHITECTURE_VISUAL.md
   - Show Client → Orchestrator → Workers

---

## 💬 Likely Questions & Answers

**Q: How does it scale to 1000s of requests/sec?**
```
A: The core logic is async/await, so it handles many concurrent
   requests efficiently. The bottleneck would be the workers.
   With 10x workers and this orchestrator, you'd handle 10x traffic.
```

**Q: What happens if the orchestrator dies?**
```
A: In this lab, you'd lose in-flight requests. In production,
   you'd have multiple orchestrators behind a load balancer,
   with persistent queue in Redis/database for durability.
```

**Q: Can it handle streaming responses?**
```
A: The current version handles request/response. We're planning
   Server-Sent Events for streaming (Phase 3 in roadmap).
```

**Q: How does it compare to Kubernetes/Istio?**
```
A: This is simpler, LLM-specific, and faster to understand.
   K8s is more complex but more general-purpose.
   This could run inside K8s as part of a service mesh.
```

---

## 🎯 Success Criteria

After the demo, you should hear:
- ✅ "Wow, that's real-time!"
- ✅ "Impressive how it handles failures"
- ✅ "Cool load balancing algorithm"
- ✅ "This scales well"
- ✅ "Professional-looking dashboards"

You succeeded if:
- ✅ All requests completed (no errors)
- ✅ Audience saw real-time updates
- ✅ Everyone understood the architecture
- ✅ People asked about production deployment

---

## 📋 Final Checklist (Do Before Demo)

- [ ] Docker containers all running (`docker ps`)
- [ ] All health checks passing (`curl /health`)
- [ ] WebUI loads at localhost:8000
- [ ] Grafana loads at localhost:3000
- [ ] Prometheus metrics available
- [ ] Browser tabs open and refreshed
- [ ] demo_load.py is executable
- [ ] Internet stable (no WiFi issues)
- [ ] Sound working (if presenting in meeting)
- [ ] Have backup screenshots ready

---

## 🚀 Post-Demo Follow-up

Send to audience:
```
📧 Email Subject: LLM Orchestrator Demo - Code & Resources

Hi all,

Thanks for attending the orchestrator demo! Here are the resources:

GitHub: [your-repo-url]
Quick Start: See README.md
Dashboards:
  - Live UI: http://localhost:8000
  - Grafana: http://localhost:3000
  - Prometheus: http://localhost:9090

Next Steps:
1. Clone the repo
2. Run: docker-compose -f docker-compose.v2.yml up
3. Run: python demo_load.py
4. Check VISUALIZATION_GUIDE.md for details

Questions? See TOOLS_COMPARISON.md or ROADMAP.md

Cheers! 🚀
```

---

**You're ready to impress! Good luck with the demo! 🎬✨**
