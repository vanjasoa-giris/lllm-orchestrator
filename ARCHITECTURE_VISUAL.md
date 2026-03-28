# 🏗️ LLM Orchestrator - Visual Architecture Guide

## 📊 Three-Layer Visualization Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                         OBSERVATION LAYER                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  🎨 LAYER 3: PROFESSIONAL DASHBOARDS                               │
│  ┌─────────────────────────────────────┐                           │
│  │ Grafana (localhost:3000)            │                           │
│  │ ├─ Request Rate graph               │                           │
│  │ ├─ Latency P95/P99 trend            │                           │
│  │ ├─ Worker connections               │                           │
│  │ ├─ Error rate by worker             │                           │
│  │ ├─ Circuit breaker timeline         │                           │
│  │ └─ Queue size gauge                 │                           │
│  │                                       │                           │
│  │ 🔷 UPDATE FREQUENCY: 10-30s          │                           │
│  │ 🔷 DATA SOURCE: Prometheus          │                           │
│  │ 🔷 HISTORY: 15+ days                │                           │
│  └─────────────────────────────────────┘                           │
│           ▲                                                          │
│           │ (queries metrics)                                        │
│           │                                                          │
│  ┌─────────────────────────────────────┐                           │
│  │ Prometheus (localhost:9090)         │                           │
│  │ ├─ Time series database             │                           │
│  │ ├─ Scrapes /metrics every 15s       │                           │
│  │ ├─ PromQL query language            │                           │
│  │ ├─ Alerting rules support           │                           │
│  │ └─ 15-day data retention            │                           │
│  │                                       │                           │
│  │ 🔷 UPDATE FREQUENCY: 15s             │                           │
│  │ 🔷 SOURCES: :8001/metrics (all)    │                           │
│  │ 🔷 QUERIES: rate(), histogram_      │                           │
│  │            quantile()               │                           │
│  └─────────────────────────────────────┘                           │
│           ▲                                                          │
│           │ (metrics feed)                                           │
│           │                                                          │
│  🟢 LAYER 1: REAL-TIME DASHBOARD (HERO!)                           │
│  ┌─────────────────────────────────────┐                           │
│  │ WebUI (localhost:8000)              │                           │
│  │ ├─ Worker Status Cards              │ 🟢🔴🟠 indicators         │
│  │ │  ├─ Health: 🟢healthy/🔴unhealthy│                           │
│  │ │  ├─ Connections: 0-5              │                           │
│  │ │  ├─ Latency: 45-250ms             │                           │
│  │ │  └─ Circuit: ✓Normal/⚠️Open/⏳Half│                           │
│  │ │                                    │                           │
│  │ ├─ System Status                     │                           │
│  │ │  ├─ Queue size: 0-5                │                           │
│  │ │  ├─ Total connections: 0-15        │                           │
│  │ │  └─ Healthy workers: 0-3           │                           │
│  │ │                                    │                           │
│  │ ├─ Latency Graph (line chart)        │                           │
│  │ │  ├─ 20-point rolling history       │                           │
│  │ │  ├─ Per-worker lines (M1/M2/M3)   │                           │
│  │ │  └─ Color-coded: 🟢/🟡/🔴        │                           │
│  │ │                                    │                           │
│  │ ├─ Connections Chart (bar chart)     │                           │
│  │ │  ├─ Current connections per worker │                           │
│  │ │  └─ Color-coded bars               │                           │
│  │ │                                    │                           │
│  │ └─ Architecture Diagram              │                           │
│  │    └─ Visual flow: Client → Orch → Workers                      │
│  │                                       │                           │
│  │ 🔷 UPDATE FREQUENCY: 1s (WebSocket)  │                           │
│  │ 🔷 HISTORY: 20 data points          │                           │
│  │ 🔷 CONNECTION: Live WebSocket (/ws) │                           │
│  └─────────────────────────────────────┘                           │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                            ▲
                            │ (consumes data)
                            │
                     (via WebSocket)
                            │
                            │
┌─────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATION LAYER                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Orchestrator (localhost:8000, localhost:9000)                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  FastAPI + LoadBalancer Engine                              │  │
│  │                                                              │  │
│  │  1️⃣ REQUEST ROUTING                                         │  │
│  │     POST /infer → select_worker() → forward_request()       │  │
│  │                                                              │  │
│  │  2️⃣ WORKER SELECTION (Adaptive Score)                      │  │
│  │     score = (1/(connections+1)) × (1/latency) × weight     │  │
│  │     → Favors: free workers, fast workers, weighted workers  │  │
│  │                                                              │  │
│  │  3️⃣ HEALTH CHECKS (every 5s)                               │  │
│  │     GET /health on each worker                              │  │
│  │     → Update status (healthy/unhealthy)                     │  │
│  │                                                              │  │
│  │  4️⃣ CIRCUIT BREAKER PATTERN                                 │  │
│  │     ┌─ CLOSED (normal) ─ 5 failures ─ OPEN (reject)       │  │
│  │     │                                    │                 │  │
│  │     └──────── 30s timeout + 2 successes ─┘                │  │
│  │     → Prevents cascade failures                            │  │
│  │                                                              │  │
│  │  5️⃣ REQUEST QUEUEING (fallback)                            │  │
│  │     No healthy workers? → Queue request                    │  │
│  │     Retry every 10s when capacity available                │  │
│  │                                                              │  │
│  │  6️⃣ METRICS GENERATION                                      │  │
│  │     └─ Exported on :9000/metrics (Prometheus format)       │  │
│  │                                                              │  │
│  │  7️⃣ REAL-TIME STATS (WebSocket)                             │  │
│  │     └─ Broadcast to /ws clients every 1s                   │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                    ▲              ▲              ▲                  │
│                    │              │              │                  │
│                    │ (forward)    │ (health)    │ (metrics)        │
│                    │              │              │                  │
│                    ▼              ▼              ▼                  │
│     Worker M1    Worker M2      Worker M3   Prometheus            │
│     :8001        :8002         :8003       :9090                  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                            ▲
                            │ (HTTP requests)
                            │
┌─────────────────────────────────────────────────────────────────────┐
│                        WORKER LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Worker M1       │  │  Worker M2       │  │  Worker M3       │  │
│  │  :8001           │  │  :8002           │  │  :8003           │  │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤  │
│  │ POST /infer      │  │ POST /infer      │  │ POST /infer      │  │
│  │ ├─ Simulate LLM  │  │ ├─ Simulate LLM  │  │ ├─ Simulate LLM  │  │
│  │ ├─ latency=45ms  │  │ ├─ latency=60ms  │  │ ├─ latency=55ms  │  │
│  │ └─ 2% error rate │  │ └─ 1% error rate │  │ └─ 3% error rate │  │
│  │                  │  │                  │  │                  │  │
│  │ GET /health      │  │ GET /health      │  │ GET /health      │  │
│  │ └─ status=ok     │  │ └─ status=ok     │  │ └─ status=ok     │  │
│  │                  │  │                  │  │                  │  │
│  │ GET /metrics     │  │ GET /metrics     │  │ GET /metrics     │  │
│  │ └─ prometheus    │  │ └─ prometheus    │  │ └─ prometheus    │  │
│  │    format        │  │    format        │  │    format        │  │
│  │                  │  │                  │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│         ▲                     ▲                     ▲                │
│         │ Client requests     │                     │                │
│         │ (balance via)       │                     │                │
│         └─────────────────────┴─────────────────────┘                │
│                                                                       │
│  Simulated Inference Backend:                                       │
│  ├─ Latency: base + token_cost + variance                           │
│  ├─ Error: 2% chance of simulated failure                           │
│  ├─ Response: Generic LLM response                                  │
│  └─ Ready to replace with: vLLM, Ollama, OpenAI API                │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                            ▲
                            │ (HTTP)
                            │
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Application / Load Test                                            │
│  ├─ curl + httpx (async)                                            │
│  ├─ POST /infer {prompt, max_tokens}                                │
│  └─ demo_load.py (4 scenarios)                                      │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request Flow Diagram

```
Step 1: Client Sends Request
┌──────────────┐
│ Client       │
│ POST /infer  │
└──────┬───────┘
       │ {"prompt": "hello", "max_tokens": 50}
       │
       ▼
┌────────────────────────────────────────┐
│ Orchestrator: /infer endpoint         │
└────┬───────────────────────────────────┘
     │
     │ Step 2: Select Best Worker
     ├─ Get all healthy workers
     ├─ Calculate scores for each:
     │  score = (1/(connections+1)) * (1/latency) * weight
     ├─ Return worker with highest score
     │
     ▼ (E.g., M1 has score 0.95)
┌────────────────────────────────────────┐
│ Worker M1: POST /infer                │
│ Forward request...                     │
└────┬───────────────────────────────────┘
     │
     │ Step 3: Simulate Inference
     │ latency = base_latency + token_latency + variance
     │         = (len(prompt)*0.001) + (50*0.02) + variance
     │         = 0.5ms + 1000ms + variance
     │         ≈ 1050ms
     │
     ▼
┌────────────────────────────────────────┐
│ Worker Response                        │
│ {                                      │
│   "worker_id": "M1",                   │
│   "response": "...",                   │
│   "tokens_generated": 50,              │
│   "latency": 1.052                     │
│ }                                      │
└────┬───────────────────────────────────┘
     │
     │ Step 4: Record Metrics
     │ ├─ requests_total{worker_id="M1", status="success"} ++
     │ ├─ request_latency{worker_id="M1"}.observe(1.052)
     │ └─ worker_connections{worker_id="M1"} --
     │
     ▼
┌────────────────────────────────────────┐
│ Orchestrator: Return to Client         │
└────┬───────────────────────────────────┘
     │
     ▼
┌──────────────┐
│ Client       │
│ Receives     │
│ Response ✓   │
└──────────────┘

Metrics Available Immediately:
├─ Prometheus: Scraped in 15s
├─ Grafana: Updated in 20-30s
└─ WebUI: Updated in 1s (WebSocket)
```

---

## ⚡ Real-Time Update Flow

```
Timeline (seconds):

0s  - Client sends request to Orchestrator
      └─ Orchestrator forwards to M1
      └─ M1 processes (latency 1.05s)

1s  - WebUI refreshes via WebSocket
      └─ Shows M1: 1 connection, latency increasing

1.05s - M1 sends response
      - Orchestrator records metrics
      - worker_connections{M1} = 0
      - request_latency recorded

1.1s - WebUI updates (next 1s cycle)
      └─ Shows completed request, M1 now free

15s - Prometheus scrapes :8001/metrics
      └─ Pulls all accumulated metrics

20s - Grafana refreshes panels
      └─ Shows point on line graph

[WebUI gets instant updates]
[Grafana gets updates every 10-30s]
[Prometheus stores all history]
```

---

## 🎯 Data Flow Architecture

```
Component: Metrics Collection

Worker M1 -> Metrics Endpoint (:8001/metrics)
   │
   └─ Exposed metrics:
      ├─ llm_requests_total{status="success"} = 45
      ├─ llm_request_latency_seconds bucket[1.0] = 12
      ├─ llm_worker_connections = 0
      └─ llm_circuit_breaker_state = 0 (closed)

               ↓ (Prometheus scrapes every 15s)

Prometheus Time Series Database
   │
   ├─ Query 1: rate(llm_requests_total[1m])
   │           → 3 requests/second
   │
   ├─ Query 2: histogram_quantile(0.95, llm_request_latency_seconds)
   │           → 245ms (95th percentile)
   │
   └─ Query 3: llm_worker_connections
               → M1=0, M2=1, M3=0

       ↓                       ↓
       │                       │
    Grafana              Custom WebUI
  (dashboards)         (WebSocket feed)
     │                      │
     ├─ Line graph      ├─ Real-time card
     │  (RPS over       │  (M1: 0 conn)
     │   time)          │
     ├─ Bar chart       ├─ Line graph
     │  (P95            │  (20-point
     │   latency)       │   history)
     │                  │
     └─ Updates         └─ Updates
        30s             1s
```

---

## 🛠️ System State Management

```
In-Memory State (Orchestrator):

workers = {
  "M1": Worker {
    id: "M1",
    url: "http://localhost:8001",
    status: HEALTHY,
    connections: 0,
    latencies: [45, 52, 48, 55, ...],  # last 10
    consecutive_failures: 0,
    circuit_state: CLOSED,
    weight: 1
  },
  "M2": Worker { ... },
  "M3": Worker { ... }
}

request_queue = [
  QueueItem {
    id: "req-123",
    payload: {"prompt": "...", "max_tokens": 50},
    priority: 1,
    created_at: 1699564234.5,
    retries: 0
  }
]

Health Check Loop (every 5s):
├─ For each worker:
│  ├─ GET /health
│  ├─ If 200 OK:
│  │  └─ consecutive_failures = 0, status = HEALTHY
│  └─ If timeout/error:
│     └─ consecutive_failures++, maybe trigger circuit

Queue Processing Loop (every 10s):
├─ If any queued items AND healthy workers:
│  └─ Retry first item
└─ If max retries exceeded:
   └─ Remove from queue, log

Metrics Export (/metrics):
└─ Prometheus scrapes every 15s
   ├─ Reads current state
   └─ Exposes all counters/gauges/histograms
```

---

## 📈 Scaling Paths

```
Lab Setup (Current):
├─ 3 simulated workers (M1, M2, M3)
├─ 1 orchestrator
└─ Single machine deployment

     ↓ (add Prometheus + Grafana)

Production v1:
├─ 3 real workers (vLLM, Ollama, etc.)
├─ 1 orchestrator with persistent queue (Redis)
├─ Prometheus + Grafana monitoring
└─ Single region

     ↓ (add Kubernetes + multi-orchestrator)

Production v2:
├─ N workers (auto-scaled via Kubernetes)
├─ N orchestrators (load balanced)
├─ Multi-region with DNS failover
├─ Prometheus + Grafana + Jaeger tracing
└─ Persistent queue on database

     ↓ (add cost optimization)

Production v3 (Enterprise):
├─ Multi-cloud (AWS + GCP + Azure)
├─ Cost-optimized routing (cheap + fast)
├─ Advanced scheduling (GPU affinity, priority queues)
├─ Full observability (logs + metrics + traces)
└─ SLO monitoring + automated remediation
```

---

## 🎬 Demo Scenario Timeline

```
T+0s:   Start docker-compose.v2.yml
        └─ 7 containers start (3 workers + orchestrator + prometheus + grafana + webui)

T+10s:  All services healthy
        └─ http://localhost:8000 ready (WebUI)
        └─ http://localhost:3000 ready (Grafana)
        └─ http://localhost:9090 ready (Prometheus)

T+10s:  Start demo_load.py
        └─ Scenario 1: Sequential 3 requests (3s)
           ├─ Request 1 → M1 (45ms)
           ├─ Request 2 → M2 (52ms)
           └─ Request 3 → M3 (48ms)

T+13s:  Scenario 2: Concurrent spike (15 requests, <1s)
        └─ All workers get requests simultaneously
        └─ See connections spike to 5 in WebUI
        └─ See latency graph jump

T+15s:  Scenario 3: Steady load (3 req/sec, 20s)
        └─ Watch distribution balance
        └─ See queue size = 0
        └─ Monitor latency trends

T+35s:  Scenario 4: Variable load (30s)
        └─ Quiet → Spike → Quiet → Spike
        └─ See queue build up during spikes
        └─ See circuit breaker (if simulated failures)

T+65s:  End of demo
        └─ Print statistics:
           ├─ Total requests: 48
           ├─ Success rate: 96%
           ├─ Queue peak: 2
           └─ Avg latency: 52ms

T+75s:  Prometheus has data (5 scrapes done)
        └─ Grafana shows 60-second graph
        └─ WebUI still has last 20 points

✨ You have live visualization of orchestration in action!
```

---

## 🔑 Key Concepts Visualized

### 1. **Load Balancing** (Adaptive Scoring)
```
Request arrives → Evaluate all workers:

M1: connections=0, latency=45ms, weight=1
    score = (1/1) × (1/45) × 1 = 0.022 ✓ BEST

M2: connections=2, latency=52ms, weight=1
    score = (1/3) × (1/52) × 1 = 0.006

M3: connections=1, latency=48ms, weight=1
    score = (1/2) × (1/48) × 1 = 0.010

→ Select M1 (highest score)
→ Shown in WebUI as highlight/color change
```

### 2. **Circuit Breaker** (State Machine)
```
Normal operation:
  [CLOSED] ──OK─→ [CLOSED]
  
5+ consecutive failures:
  [CLOSED] ──FAIL×5─→ [OPEN]
  
After 30s:
  [OPEN] ──TIMEOUT─→ [HALF_OPEN]
  
2+ successes in HALF_OPEN:
  [HALF_OPEN] ──OK×2─→ [CLOSED]

Shown in WebUI:
├─ 🟢 CLOSED = green card, normal operation
├─ 🟠 OPEN = orange card, requests rejected
└─ 🟠 HALF_OPEN = orange card, testing recovery
```

### 3. **Queue Management** (Fallback)
```
Happy path:
Client → Orchestrator → Healthy worker → Response

Unhappy path (all workers down):
Client → Orchestrator → No healthy workers
                        ↓
                      Queue request
                        ↓
                      Wait & retry
                        ↓
                      Worker recovers
                        ↓
                      Process from queue
                        ↓
                      Return response

Shown in WebUI:
├─ Queue size counter (0-5 usually)
└─ Status indicator changes during queueing
```

---

**This architecture supports the concepts shown in `tasks.md` with full real-time visualization! 🎉**
