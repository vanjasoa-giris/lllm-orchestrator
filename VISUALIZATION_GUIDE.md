# 📊 LLM Load Balancer - Visualization Setup Guide

## 🎯 Quick Start (3 options)

### **Option 1: Full Stack (Recommended for Demo)**
```bash
# Start everything with Docker Compose
docker-compose -f docker-compose.v2.yml up -d

# Wait 10 seconds for services to start
sleep 10

# Run the demo load generator
python demo_load.py
```

**Access Points:**
- 🎨 **Dashboard (Custom WebUI)**: http://localhost:8000
- 📊 **Grafana**: http://localhost:3000 (admin/admin)
- 📈 **Prometheus**: http://localhost:9090
- 🔧 **Orchestrator Health**: http://localhost:8000/health
- 📉 **Raw Metrics**: http://localhost:8000/metrics

---

### **Option 2: Local Development (No Docker)**
```bash
# Install dependencies
pip install -r requirements.txt

# Terminal 1 - Worker M1
python worker/main.py --port 8001 --id M1

# Terminal 2 - Worker M2
python worker/main.py --port 8002 --id M2

# Terminal 3 - Worker M3
python worker/main.py --port 8003 --id M3

# Terminal 4 - Orchestrator (NEW VERSION)
python orchestrator/main_v2.py

# Terminal 5 - Load Generator (in another terminal)
python demo_load.py
```

**Access Points:**
- 🎨 **Dashboard**: http://localhost:8000
- View in real-time as requests flow through the system

---

### **Option 3: Kubernetes Deployment (Advanced)**
```bash
kubectl apply -f k8s/manifests.yaml
# Coming soon...
```

---

## 🎨 Dashboard Features

### **Real-Time Metrics (WebSocket)**
The custom dashboard at `http://localhost:8000` shows:

- **Worker Cards**: Live status, connections, latency, circuit breaker state
- **System Status**: Queue size, active connections, healthy workers count
- **Latency Graph**: 20-point history per worker (line chart)
- **Connections Graph**: Current active connections (bar chart)
- **Health Indicators**: Color-coded status (🟢 healthy, 🔴 unhealthy, 🟠 circuit open)

Updates every 1 second via WebSocket for zero-latency visualization.

---

## 📊 Grafana Setup

### **Pre-configured Dashboards**
Once Grafana starts, dashboards are automatically provisioned at:
```
http://localhost:3000
```

**Login**: `admin` / `admin`

**Available Dashboards:**
1. **LLM Load Balancer** - Main dashboard with:
   - Requests per second (rate)
   - P95 latency trends
   - Worker connection counts
   - Circuit breaker state changes
   - Queue size over time

### **Manual Dashboard Creation**

If you want to create custom dashboards:

1. Add Prometheus data source:
   - URL: `http://prometheus:9090`
   - Access: Server

2. Import dashboard JSON:
   - Use `config/grafana/provisioning/dashboards/llm-dashboard.json`

3. Available metrics to query:
   ```
   llm_requests_total{job="orchestrator"}
   llm_request_latency_seconds
   llm_worker_connections
   llm_circuit_breaker_state
   llm_queue_size
   ```

---

## 📈 Prometheus Metrics

### **Query Examples**

**In Prometheus UI** (`http://localhost:9090`):

```promql
# Requests per second
rate(llm_requests_total[1m])

# P95 latency
histogram_quantile(0.95, llm_request_latency_seconds)

# Active connections by worker
llm_worker_connections

# Circuit breaker state (0=closed, 1=open, 2=half_open)
llm_circuit_breaker_state

# Queue size
llm_queue_size
```

---

## 🔄 Load Testing Scenarios

The `demo_load.py` script provides 4 scenarios:

1. **Sequential Requests**: Simple load
2. **Concurrent Spike**: Burst of 15 requests
3. **Steady Load**: 3 req/sec for 20 seconds
4. **Variable Load**: Realistic traffic patterns

Run custom scenarios:
```python
from demo_load import LoadGenerator

gen = LoadGenerator()
await gen.spike_load(50, concurrent=True)  # 50 concurrent requests
await gen.steady_load(60, rate_per_sec=5)   # 5 req/sec for 60s
gen.print_stats()
```

---

## 🛠️ Configuration

### **Orchestrator Config** (`config/workers.yaml`)
```yaml
workers:
  - id: M1
    url: http://localhost:8001
    weight: 1

load_balancer:
  strategy: adaptive
  timeout: 30
  max_retries: 3

circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 30

healthcheck:
  interval: 5
  timeout: 2
```

### **Worker Config**
```bash
WORKER_ID=M1           # Worker identifier
WORKER_PORT=8001       # Port to listen on
BACKEND=simulated      # Backend type: simulated, vllm, ollama, etc.
```

---

## 🐛 Troubleshooting

### **Dashboard not connecting**
```bash
# Check WebSocket connection
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  http://localhost:8000/ws

# View orchestrator logs
docker logs llm-orchestrator
```

### **Prometheus not scraping**
```bash
# Check metrics endpoint
curl http://localhost:8000/metrics

# Verify Prometheus targets
curl http://localhost:9090/api/v1/targets
```

### **Workers not responding**
```bash
# Test worker health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

### **High latency or timeouts**
- Check Docker container logs: `docker logs llm-worker-m1`
- Verify network connectivity: `docker network ls`
- Monitor system resources: `docker stats`

---

## 📚 Architecture Overview

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ (HTTP POST)
       ▼
┌──────────────────────────────────┐
│   Orchestrator (8000)            │
│  - Load Balancer                 │
│  - Health Checks                 │
│  - Circuit Breaker               │
│  - Metrics/Prometheus (8001)     │
│  - WebSocket (live dashboard)    │
└──────┬──────────────┬──────────────┘
       │              │
       ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Worker M1  │ │  Worker M2  │ │  Worker M3  │
│   (8001)    │ │   (8002)    │ │   (8003)    │
└─────────────┘ └─────────────┘ └─────────────┘

Monitoring Stack:
┌─────────────────────────────────┐
│  Prometheus (9090)              │  ← Scrapes metrics from orchestrator & workers
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Grafana (3000)                 │  ← Visualizes Prometheus metrics
└─────────────────────────────────┘

Custom Dashboard:
┌─────────────────────────────────┐
│  WebUI (8000)                   │  ← Real-time via WebSocket
│  - Live status cards            │
│  - Latency/connection graphs    │
│  - Circuit breaker indicators   │
└─────────────────────────────────┘
```

---

## ✨ Features Showcased

### **Orchestration**
- ✅ Adaptive load balancing (score-based worker selection)
- ✅ Health checks (5s interval)
- ✅ Circuit breaker pattern
- ✅ Request queueing and retry logic

### **Monitoring**
- ✅ Real-time WebSocket dashboard
- ✅ Prometheus metrics export
- ✅ Grafana dashboards
- ✅ Performance telemetry (latency, throughput)

### **Resilience**
- ✅ Automatic failover
- ✅ Circuit breaker state transitions
- ✅ Graceful degradation under load
- ✅ Queue persistence for unavailable workers

---

## 🚀 Next Steps

1. **Replace simulators with real LLMs**:
   - vLLM: `BACKEND=vllm` in worker env
   - Ollama: `BACKEND=ollama` in worker env
   - HuggingFace: Load real models

2. **Scale horizontally**:
   - Add more workers by duplicating M1/M2/M3 in docker-compose

3. **Production deployment**:
   - Use Kubernetes manifests (coming soon)
   - Set up persistent storage for queue
   - Configure TLS/SSL certificates

4. **Advanced monitoring**:
   - Add distributed tracing (Jaeger)
   - Centralize logs (Loki/ELK)
   - Set up alerting (Alertmanager)

---

## 📞 Support

For issues or questions:
1. Check logs: `docker logs <container_name>`
2. Verify network: `docker network inspect llm-network`
3. Test endpoints: Use the test scripts in `tests/`

Happy orchestrating! 🎉
