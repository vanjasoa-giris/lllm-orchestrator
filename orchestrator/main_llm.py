import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, AsyncIterator
import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import StreamingResponse, FileResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel
import json

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class LLMBackend(Enum):
    SIMULATED = "simulated"
    OPENAI = "openai"
    VLLM = "vllm"
    HF_TRANSFORMERS = "hf_transformers"


@dataclass
class Worker:
    id: str
    url: str
    backend: LLMBackend = LLMBackend.SIMULATED
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    status: WorkerStatus = WorkerStatus.UNHEALTHY
    connections: int = 0
    active_tokens: int = 0

    latencies: list = field(default_factory=list)
    prompt_tokens: list = field(default_factory=list)
    completion_tokens: list = field(default_factory=list)
    tokens_per_second: list = field(default_factory=list)

    prefill_latencies: list = field(default_factory=list)
    decode_latencies: list = field(default_factory=list)

    consecutive_failures: int = 0
    consecutive_successes: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_open_time: Optional[float] = None
    weight: int = 1

    gpu_memory: Optional[float] = None
    gpu_memory_total: Optional[float] = None
    cpu_usage: Optional[float] = None

    max_concurrent_requests: int = 10
    current_load: float = 0.0


@dataclass
class QueueItem:
    id: str
    payload: dict
    priority: int = 1
    created_at: float = field(default_factory=time.time)
    retries: int = 0
    estimated_tokens: int = 0


class LLMLoadBalancer:
    def __init__(self, config_path: str = None):
        self.workers: dict[str, Worker] = {}
        self.request_queue: list[QueueItem] = []
        self.config = self._load_config(config_path)
        self._initialize_workers()
        self._setup_http_client()

    def _load_config(self, path: str) -> dict:
        default_config = {
            "workers": [
                {"id": "M1", "url": "http://localhost:8001", "weight": 1},
                {"id": "M2", "url": "http://localhost:8002", "weight": 1},
                {"id": "M3", "url": "http://localhost:8003", "weight": 1},
            ],
            "timeout": 60,
            "max_retries": 3,
            "healthcheck_interval": 5,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 30,
            "token_based_routing": True,
            "streaming_enabled": True,
        }

        if path is None:
            path = os.environ.get("CONFIG_PATH", "config/workers.yaml")

        try:
            with open(path, "r") as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config or {})
        except FileNotFoundError:
            logger.warning(f"Config not found: {path}, using defaults")

        return default_config

    def _initialize_workers(self):
        for w in self.config.get("workers", []):
            backend = LLMBackend(w.get("backend", "simulated"))
            self.workers[w["id"]] = Worker(
                id=w["id"],
                url=w["url"],
                backend=backend,
                api_key=w.get("api_key", os.environ.get("OPENAI_API_KEY")),
                model_name=w.get("model_name"),
                weight=w.get("weight", 1),
                max_concurrent_requests=w.get("max_concurrent", 10),
            )
        logger.info(f"Initialized {len(self.workers)} workers with token-based routing")

    def _setup_http_client(self):
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.get("timeout", 60)),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    def _estimate_tokens(self, prompt: str) -> int:
        return len(prompt) // 4

    def _calculate_score(self, worker: Worker, estimated_tokens: int = 0) -> float:
        if worker.status != WorkerStatus.HEALTHY:
            return 0

        if worker.circuit_state == CircuitState.OPEN:
            return 0

        available_slots = worker.max_concurrent_requests - worker.connections
        if available_slots <= 0:
            return 0

        avg_latency = (
            sum(worker.latencies[-10:]) / len(worker.latencies[-10:])
            if worker.latencies
            else 1
        )

        avg_tps = (
            sum(worker.tokens_per_second[-10:]) / len(worker.tokens_per_second[-10:])
            if worker.tokens_per_second
            else 1
        )

        load_factor = worker.connections / worker.max_concurrent_requests

        latency_score = 1 / avg_latency if avg_latency > 0 else 0

        if avg_tps > 0:
            estimated_time = estimated_tokens / avg_tps
            token_efficiency = 1 / (estimated_time + 0.1)
        else:
            token_efficiency = 0

        availability_score = (
            worker.max_concurrent_requests - worker.connections
        ) / worker.max_concurrent_requests

        base_score = (
            latency_score * 0.3 + token_efficiency * 0.4 + availability_score * 0.3
        )

        return base_score * worker.weight

    def select_worker(self, estimated_tokens: int = 0) -> Optional[Worker]:
        healthy_workers = [
            w
            for w in self.workers.values()
            if w.status == WorkerStatus.HEALTHY
            and w.circuit_state != CircuitState.OPEN
            and w.connections < w.max_concurrent_requests
        ]

        if not healthy_workers:
            self._check_circuit_breaker_transitions()
            return None

        selected = max(
            healthy_workers, key=lambda w: self._calculate_score(w, estimated_tokens)
        )

        if selected.circuit_state == CircuitState.HALF_OPEN:
            selected.circuit_state = CircuitState.CLOSED

        return selected

    def _check_circuit_breaker_transitions(self):
        current_time = time.time()
        timeout = self.config.get("circuit_breaker_timeout", 30)

        for worker in self.workers.values():
            if worker.circuit_state == CircuitState.OPEN:
                if (
                    worker.circuit_open_time
                    and (current_time - worker.circuit_open_time) > timeout
                ):
                    worker.circuit_state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit for {worker.id} moved to HALF_OPEN")

    async def healthcheck(self, worker: Worker):
        try:
            response = await self.http_client.get(f"{worker.url}/health", timeout=2.0)
            if response.status_code == 200:
                worker.consecutive_successes += 1
                worker.consecutive_failures = 0

                data = response.json()
                if "gpu_memory" in data:
                    worker.gpu_memory = data.get("gpu_memory")
                if "gpu_memory_total" in data:
                    worker.gpu_memory_total = data.get("gpu_memory_total")
                if "cpu_usage" in data:
                    worker.cpu_usage = data.get("cpu_usage")

                if (
                    worker.status != WorkerStatus.HEALTHY
                    and worker.consecutive_successes >= 2
                ):
                    worker.status = WorkerStatus.HEALTHY
                    worker.circuit_state = CircuitState.CLOSED
                    logger.info(f"Worker {worker.id} recovered")
            else:
                worker.consecutive_failures += 1
                self._handle_failure(worker)
        except Exception as e:
            logger.debug(f"Healthcheck failed for {worker.id}: {e}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)

    def _handle_failure(self, worker: Worker):
        threshold = self.config.get("circuit_breaker_threshold", 5)

        if worker.consecutive_failures >= 3:
            worker.status = WorkerStatus.UNHEALTHY

        if (
            worker.consecutive_failures >= threshold
            and worker.circuit_state == CircuitState.CLOSED
        ):
            worker.circuit_state = CircuitState.OPEN
            worker.circuit_open_time = time.time()
            logger.warning(
                f"Circuit opened for {worker.id} after {worker.consecutive_failures} failures"
            )

    async def _stream_from_worker(
        self, worker: Worker, payload: dict
    ) -> AsyncIterator[bytes]:
        async with self.http_client.stream(
            "POST",
            f"{worker.url}/infer/stream",
            json=payload,
            timeout=httpx.Timeout(self.config.get("timeout", 60)),
        ) as response:
            async for chunk in response.aiter_bytes():
                yield chunk

    async def forward_request(self, payload: dict, stream: bool = False) -> dict:
        estimated_tokens = payload.get("max_tokens", 256)
        prompt_tokens = self._estimate_tokens(payload.get("prompt", ""))
        total_estimated = prompt_tokens + estimated_tokens

        worker = self.select_worker(total_estimated)

        if not worker:
            if self.request_queue and self.config.get("queue", {}).get("enabled", True):
                queued = QueueItem(
                    id=str(uuid.uuid4()),
                    payload=payload,
                    estimated_tokens=total_estimated,
                )
                self.request_queue.append(queued)
                return {"status": "queued", "queue_id": queued.id}
            raise HTTPException(status_code=503, detail="No available workers")

        worker.connections += 1
        worker.active_tokens += total_estimated
        start_time = time.time()

        try:
            if stream and self.config.get("streaming_enabled", True):
                return {"stream": True, "worker_id": worker.id}

            if worker.backend == LLMBackend.OPENAI:
                result = await self._call_openai(worker, payload)
            elif worker.backend == LLMBackend.VLLM:
                result = await self._call_vllm(worker, payload)
            else:
                response = await self.http_client.post(
                    f"{worker.url}/infer", json=payload
                )
                response.raise_for_status()
                result = response.json()
                result["worker"] = worker.id

            latency = time.time() - start_time
            worker.latencies.append(latency)

            if "tokens_generated" in result:
                completion_tokens = result["tokens_generated"]
                worker.completion_tokens.append(completion_tokens)
                worker.prompt_tokens.append(prompt_tokens)

                if latency > 0:
                    tps = completion_tokens / latency
                    worker.tokens_per_second.append(tps)

                if "prefill_latency" in result:
                    worker.prefill_latencies.append(result["prefill_latency"])
                if "decode_latency" in result:
                    worker.decode_latencies.append(result["decode_latency"])

            result["latency"] = latency
            worker.consecutive_failures = 0

            return result

        except httpx.TimeoutException:
            logger.error(f"Timeout for worker {worker.id}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)
            raise HTTPException(status_code=504, detail="Worker timeout")
        except Exception as e:
            logger.error(f"Error forwarding to {worker.id}: {e}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)
            raise HTTPException(status_code=502, detail=str(e))
        finally:
            worker.connections -= 1
            worker.active_tokens -= total_estimated

    async def forward_request_stream(self, payload: dict) -> AsyncIterator[bytes]:
        estimated_tokens = payload.get("max_tokens", 256)
        prompt_tokens = self._estimate_tokens(payload.get("prompt", ""))
        total_estimated = prompt_tokens + estimated_tokens

        worker = self.select_worker(total_estimated)

        if not worker:
            yield b'data: {"error": "No available workers"}\n\n'
            return

        worker.connections += 1
        worker.active_tokens += total_estimated
        start_time = time.time()

        try:
            async for chunk in self._stream_from_worker(worker, payload):
                yield chunk

            worker.latencies.append(time.time() - start_time)
            worker.consecutive_failures = 0

        except Exception as e:
            logger.error(f"Stream error from {worker.id}: {e}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)
            yield f'data: {{"error": "{str(e)}"}}\n\n'.encode()
        finally:
            worker.connections -= 1
            worker.active_tokens -= total_estimated

    async def process_queue(self):
        if not self.request_queue:
            return

        queue_config = self.config.get("queue", {})
        max_size = queue_config.get("max_size", 100)
        ttl = queue_config.get("ttl", 300)

        current_time = time.time()

        self.request_queue = [
            item for item in self.request_queue if current_time - item.created_at < ttl
        ]

        worker = self.select_worker()
        if worker and self.request_queue:
            item = self.request_queue.pop(0)
            item.retries += 1
            if item.retries > 5:
                logger.warning(f"Queue item {item.id} max retries exceeded")
                return

            try:
                await self.forward_request(item.payload)
            except Exception as e:
                logger.error(f"Queue processing error: {e}")


# === PROMETHEUS METRICS ===
requests_total = Counter(
    'llm_requests_total',
    'Total inference requests',
    ['worker_id', 'status']
)
request_latency = Histogram(
    'llm_request_latency_seconds',
    'Request latency in seconds',
    ['worker_id'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)
worker_connections = Gauge(
    'llm_worker_connections',
    'Active connections per worker',
    ['worker_id']
)
circuit_breaker_state = Gauge(
    'llm_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['worker_id']
)
worker_status = Gauge(
    'llm_worker_status',
    'Worker health status (1=healthy, 0=unhealthy)',
    ['worker_id']
)
queue_size = Gauge(
    'llm_queue_size',
    'Current queue size'
)
requests_queued_total = Counter(
    'llm_requests_queued_total',
    'Total queued requests'
)

app = FastAPI(title="LLM Load Balancer - Production Ready")
lb = LLMLoadBalancer()

# Store connected WebSocket clients
connected_clients: set[WebSocket] = set()


class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    stream: bool = False


@app.get("/")
async def dashboard():
    """Serve dashboard HTML"""
    try:
        dashboard_path = "/app/webui/dashboard.html"
        return FileResponse(dashboard_path)
    except Exception as e:
        logger.error(f"Error loading dashboard from {dashboard_path}: {e}")
        return {"error": f"Dashboard not found: {e}"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time stats"""
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            # Send stats every 1 second
            stats_data = {
                "timestamp": time.time(),
                "workers": {
                    k: {
                        "status": v.status.value,
                        "connections": v.connections,
                        "avg_latency": sum(v.latencies[-10:]) / len(v.latencies[-10:])
                        if v.latencies
                        else 0,
                        "circuit": v.circuit_state.value,
                        "consecutive_failures": v.consecutive_failures,
                    }
                    for k, v in lb.workers.items()
                },
                "queue_size": len(lb.request_queue),
            }
            await websocket.send_json(stats_data)
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connected_clients.discard(websocket)


@app.get("/health")
async def health():
    # Update metrics
    queue_size.set(len(lb.request_queue))
    for worker_id, worker in lb.workers.items():
        worker_status.labels(worker_id=worker_id).set(
            1 if worker.status == WorkerStatus.HEALTHY else 0
        )
        worker_connections.labels(worker_id=worker_id).set(worker.connections)
        state_map = {CircuitState.CLOSED: 0, CircuitState.OPEN: 1, CircuitState.HALF_OPEN: 2}
        circuit_breaker_state.labels(worker_id=worker_id).set(
            state_map[worker.circuit_state]
        )
    
    return {
        "status": "healthy",
        "workers": {k: v.status.value for k, v in lb.workers.items()},
        "queue_size": len(lb.request_queue),
        "streaming_enabled": lb.config.get("streaming_enabled", True),
    }


@app.post("/infer")
async def infer(request: InferenceRequest):
    payload = request.dict()
    stream = payload.pop("stream", False)

    try:
        if stream:
            return StreamingResponse(
                lb.forward_request_stream(payload), media_type="text/event-stream"
            )

        result = await lb.forward_request(payload)
        worker_id = result.get("worker", "unknown")
        requests_total.labels(worker_id=worker_id, status="success").inc()
        if "latency" in result:
            request_latency.labels(worker_id=worker_id).observe(result["latency"])
        return result
    except HTTPException as e:
        status_code = e.status_code
        if status_code == 503:
            requests_queued_total.inc()
            requests_total.labels(worker_id="queued", status="queued").inc()
        else:
            requests_total.labels(worker_id="unknown", status="error").inc()
        raise


@app.post("/infer/raw")
async def infer_raw(request: Request):
    payload = await request.json()
    stream = payload.get("stream", False)

    if stream:
        return StreamingResponse(
            lb.forward_request_stream(payload), media_type="text/event-stream"
        )

    return await lb.forward_request(payload)


@app.get("/stats")
async def stats():
    workers_data = {}
    for k, v in lb.workers.items():
        avg_tps = (
            sum(v.tokens_per_second[-10:]) / len(v.tokens_per_second[-10:])
            if v.tokens_per_second
            else 0
        )
        avg_prefill = (
            sum(v.prefill_latencies[-10:]) / len(v.prefill_latencies[-10:])
            if v.prefill_latencies
            else 0
        )
        avg_decode = (
            sum(v.decode_latencies[-10:]) / len(v.decode_latencies[-10:])
            if v.decode_latencies
            else 0
        )

        workers_data[k] = {
            "status": v.status.value,
            "connections": v.connections,
            "active_tokens": v.active_tokens,
            "max_concurrent": v.max_concurrent_requests,
            "load_percentage": (v.connections / v.max_concurrent_requests * 100)
            if v.max_concurrent_requests > 0
            else 0,
            "avg_latency": sum(v.latencies[-10:]) / len(v.latencies[-10:])
            if v.latencies
            else 0,
            "avg_tokens_per_second": avg_tps,
            "avg_prefill_latency": avg_prefill,
            "avg_decode_latency": avg_decode,
            "circuit": v.circuit_state.value,
            "backend": v.backend.value,
            "gpu_memory": v.gpu_memory,
            "gpu_memory_total": v.gpu_memory_total,
            "cpu_usage": v.cpu_usage,
        }

    return {
        "workers": workers_data,
        "queue_size": len(lb.request_queue),
        "config": {
            "timeout": lb.config.get("timeout"),
            "token_based_routing": lb.config.get("token_based_routing", True),
            "streaming_enabled": lb.config.get("streaming_enabled", True),
        },
    }


async def healthcheck_loop():
    while True:
        tasks = [lb.healthcheck(worker) for worker in lb.workers.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(lb.config.get("healthcheck_interval", 5))


async def queue_processor():
    while True:
        await lb.process_queue()
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup():
    asyncio.create_task(healthcheck_loop())
    asyncio.create_task(queue_processor())
    logger.info("LLM Load Balancer started with token-based routing")
    logger.info("Dashboard available at http://localhost:8000")
    logger.info("WebSocket endpoint at ws://localhost:8000/ws")
    logger.info("Metrics available at http://localhost:8000/metrics")


@app.on_event("shutdown")
async def shutdown():
    await lb.http_client.aclose()
    logger.info("LLM Load Balancer stopped")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
