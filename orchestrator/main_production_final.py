import asyncio
import heapq
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, AsyncIterator, Callable
from collections import defaultdict
import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request, WebSocket, Depends, Header
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
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
    priority: int
    created_at: float
    id: str
    payload: dict
    estimated_tokens: int = 0
    retries: int = 0
    last_retry_at: Optional[float] = None
    last_error: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


@dataclass
class DeadLetterItem:
    id: str
    payload: dict
    error: str
    retries: int
    created_at: float
    failed_at: float
    request_id: str


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_id: str) -> bool:
        async with self._lock:
            now = time.time()
            minute_ago = now - 60
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > minute_ago
            ]
            if len(self.requests[client_id]) >= self.requests_per_minute:
                return False
            self.requests[client_id].append(now)
            return True

    def cleanup(self):
        now = time.time()
        minute_ago = now - 60
        for client_id in list(self.requests.keys()):
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > minute_ago
            ]
            if not self.requests[client_id]:
                del self.requests[client_id]


class LLMLoadBalancer:
    def __init__(self, config_path: str = None):
        self.workers: dict[str, Worker] = {}
        self._priority_queue: list[QueueItem] = []
        self._dead_letter_queue: list[DeadLetterItem] = []
        self.config = self._load_config(config_path)
        self._initialize_workers()
        self._setup_http_client()
        self._setup_rate_limiter()
        self._active_requests: dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()

    def _load_config(self, path: str) -> dict:
        default_config = {
            "workers": [
                {"id": "M1", "url": "http://localhost:8001", "weight": 1},
                {"id": "M2", "url": "http://localhost:8002", "weight": 1},
                {"id": "M3", "url": "http://localhost:8003", "weight": 1},
            ],
            "timeout": 60,
            "max_retries": 5,
            "healthcheck_interval": 5,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 30,
            "token_based_routing": True,
            "streaming_enabled": True,
            "queue": {
                "enabled": True,
                "max_size": 100,
                "ttl": 300,
                "max_retries": 5,
                "retry_backoff_base": 2,
                "retry_backoff_max": 60,
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 60,
            },
            "dead_letter": {
                "enabled": True,
                "max_size": 1000,
            },
        }

        if path is None:
            path = os.environ.get("CONFIG_PATH", "config/workers.yaml")

        try:
            with open(path, "r") as f:
                user_config = yaml.safe_load(f)
                self._deep_update(default_config, user_config or {})
        except FileNotFoundError:
            logger.warning(f"Config not found: {path}, using defaults")

        return default_config

    def _deep_update(self, base: dict, update: dict):
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

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

    def _setup_rate_limiter(self):
        rl_config = self.config.get("rate_limiting", {})
        if rl_config.get("enabled", True):
            self.rate_limiter = RateLimiter(rl_config.get("requests_per_minute", 60))
        else:
            self.rate_limiter = None

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
        self, worker: Worker, payload: dict, request_id: str
    ) -> AsyncIterator[bytes]:
        headers = {"X-Request-ID": request_id} if request_id else {}
        async with self.http_client.stream(
            "POST",
            f"{worker.url}/infer/stream",
            json=payload,
            headers=headers,
            timeout=httpx.Timeout(self.config.get("timeout", 60)),
        ) as response:
            async for chunk in response.aiter_bytes():
                yield chunk

    def _calculate_backoff(self, retries: int) -> float:
        queue_config = self.config.get("queue", {})
        base = queue_config.get("retry_backoff_base", 2)
        max_delay = queue_config.get("retry_backoff_max", 60)
        return min(base**retries, max_delay)

    def enqueue(
        self,
        payload: dict,
        priority: int = 1,
        estimated_tokens: int = 0,
        request_id: str = None,
    ) -> str:
        queue_config = self.config.get("queue", {})
        if not queue_config.get("enabled", True):
            raise HTTPException(status_code=503, detail="Queue disabled")

        if len(self._priority_queue) >= queue_config.get("max_size", 100):
            raise HTTPException(status_code=503, detail="Queue full")

        item_id = str(uuid.uuid4())
        item = QueueItem(
            id=item_id,
            priority=priority,
            created_at=time.time(),
            payload=payload,
            estimated_tokens=estimated_tokens,
            request_id=request_id or item_id,
        )
        heapq.heappush(self._priority_queue, item)
        requests_queued_total.inc()
        queue_size.set(len(self._priority_queue))
        logger.info(f"Enqueued request {item_id} with priority {priority}")
        return item_id

    def add_to_dead_letter(self, item: QueueItem, error: str):
        dl_config = self.config.get("dead_letter", {})
        if not dl_config.get("enabled", True):
            return

        dl_item = DeadLetterItem(
            id=item.id,
            payload=item.payload,
            error=error,
            retries=item.retries,
            created_at=item.created_at,
            failed_at=time.time(),
            request_id=item.request_id,
        )
        self._dead_letter_queue.append(dl_item)

        max_size = dl_config.get("max_size", 1000)
        if len(self._dead_letter_queue) > max_size:
            self._dead_letter_queue = self._dead_letter_queue[-max_size:]

        dead_letter_size.set(len(self._dead_letter_queue))
        dead_letter_total.inc()
        logger.warning(f"Added {item.id} to dead letter queue: {error}")

    async def _process_single_request(
        self, item: QueueItem, request_id: str = None
    ) -> dict:
        estimated_tokens = item.estimated_tokens or self._estimate_tokens(
            item.payload.get("prompt", "")
        )
        worker = self.select_worker(estimated_tokens)

        if not worker:
            return None

        worker.connections += 1
        worker.active_tokens += estimated_tokens
        start_time = time.time()
        headers = {"X-Request-ID": request_id or item.request_id}

        try:
            response = await self.http_client.post(
                f"{worker.url}/infer", json=item.payload, headers=headers
            )
            response.raise_for_status()
            result = response.json()
            result["worker"] = worker.id

            latency = time.time() - start_time
            worker.latencies.append(latency)

            if "tokens_generated" in result:
                completion_tokens = result["tokens_generated"]
                worker.completion_tokens.append(completion_tokens)
                prompt_tokens = self._estimate_tokens(item.payload.get("prompt", ""))
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
            raise Exception("Worker timeout")

        except Exception as e:
            logger.error(f"Error forwarding to {worker.id}: {e}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)
            raise

        finally:
            worker.connections -= 1
            worker.active_tokens -= estimated_tokens

    async def forward_request(
        self, payload: dict, stream: bool = False, request_id: str = None
    ) -> dict:
        estimated_tokens = payload.get("max_tokens", 256)
        prompt_tokens = self._estimate_tokens(payload.get("prompt", ""))
        total_estimated = prompt_tokens + estimated_tokens

        worker = self.select_worker(total_estimated)

        if not worker:
            if self.config.get("queue", {}).get("enabled", True):
                queue_id = self.enqueue(
                    payload=payload,
                    priority=payload.get("priority", 1),
                    estimated_tokens=total_estimated,
                    request_id=request_id,
                )
                return {"status": "queued", "queue_id": queue_id}
            raise HTTPException(status_code=503, detail="No available workers")

        worker.connections += 1
        worker.active_tokens += total_estimated
        start_time = time.time()
        headers = {"X-Request-ID": request_id or str(uuid.uuid4())}

        try:
            if stream and self.config.get("streaming_enabled", True):
                return {"stream": True, "worker_id": worker.id}

            if worker.backend == LLMBackend.OPENAI:
                result = await self._call_openai(worker, payload, headers)
            elif worker.backend == LLMBackend.VLLM:
                result = await self._call_vllm(worker, payload, headers)
            else:
                response = await self.http_client.post(
                    f"{worker.url}/infer", json=payload, headers=headers
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

    async def _call_openai(self, worker: Worker, payload: dict, headers: dict) -> dict:
        api_key = worker.api_key or os.environ.get("OPENAI_API_KEY")
        model = worker.model_name or "gpt-3.5-turbo"

        openai_payload = {
            "model": model,
            "messages": [{"role": "user", "content": payload.get("prompt", "")}],
            "max_tokens": payload.get("max_tokens", 256),
            "temperature": payload.get("temperature", 0.7),
        }

        response = await self.http_client.post(
            "https://api.openai.com/v1/chat/completions",
            json=openai_payload,
            headers={
                **headers,
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

        return {
            "response": data["choices"][0]["message"]["content"],
            "tokens_generated": data["usage"]["completion_tokens"],
            "worker": worker.id,
        }

    async def _call_vllm(self, worker: Worker, payload: dict, headers: dict) -> dict:
        vllm_payload = {
            "prompt": payload.get("prompt", ""),
            "max_tokens": payload.get("max_tokens", 256),
            "temperature": payload.get("temperature", 0.7),
        }

        response = await self.http_client.post(
            f"{worker.url}/v1/completions",
            json=vllm_payload,
            headers={**headers, "Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        return {
            "response": data["choices"][0]["text"],
            "tokens_generated": data["usage"]["completion_tokens"],
            "worker": worker.id,
        }

    async def forward_request_stream(
        self, payload: dict, request_id: str = None
    ) -> AsyncIterator[bytes]:
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
        req_id = request_id or str(uuid.uuid4())

        try:
            async for chunk in self._stream_from_worker(worker, payload, req_id):
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
        if not self._priority_queue:
            return

        queue_config = self.config.get("queue", {})
        ttl = queue_config.get("ttl", 300)
        max_retries = queue_config.get("max_retries", 5)
        current_time = time.time()

        while self._priority_queue:
            item = self._priority_queue[0]

            if current_time - item.created_at >= ttl:
                heapq.heappop(self._priority_queue)
                self.add_to_dead_letter(item, "TTL expired")
                logger.warning(f"Queue item {item.id} expired (TTL)")
                continue

            backoff_delay = self._calculate_backoff(item.retries)
            if (
                item.last_retry_at
                and (current_time - item.last_retry_at) < backoff_delay
            ):
                break

            if item.retries >= max_retries:
                heapq.heappop(self._priority_queue)
                self.add_to_dead_letter(item, "Max retries exceeded")
                logger.warning(f"Queue item {item.id} exceeded max retries")
                continue

            worker = self.select_worker(item.estimated_tokens)
            if not worker:
                break

            heapq.heappop(self._priority_queue)
            item.retries += 1
            item.last_retry_at = time.time()

            try:
                await self._process_single_request(item)
                queue_size.set(len(self._priority_queue))
                logger.info(f"Queue item {item.id} processed successfully")

            except Exception as e:
                item.last_error = str(e)
                logger.error(f"Queue processing error for {item.id}: {e}")

                if item.retries < max_retries:
                    heapq.heappush(self._priority_queue, item)
                else:
                    self.add_to_dead_letter(item, str(e))

            queue_size.set(len(self._priority_queue))

    async def graceful_shutdown(self):
        logger.info("Initiating graceful shutdown...")
        self._shutdown_event.set()

        for request_id, task in list(self._active_requests.items()):
            task.cancel()

        await asyncio.gather(
            *[task for task in self._active_requests.values()], return_exceptions=True
        )

        await self.http_client.aclose()
        logger.info("Graceful shutdown completed")


requests_total = Counter(
    "llm_requests_total", "Total inference requests", ["worker_id", "status"]
)
request_latency = Histogram(
    "llm_request_latency_seconds",
    "Request latency in seconds",
    ["worker_id"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)
worker_connections = Gauge(
    "llm_worker_connections", "Active connections per worker", ["worker_id"]
)
circuit_breaker_state = Gauge(
    "llm_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["worker_id"],
)
worker_status = Gauge(
    "llm_worker_status", "Worker health status (1=healthy, 0=unhealthy)", ["worker_id"]
)
queue_size = Gauge("llm_queue_size", "Current queue size")
requests_queued_total = Counter("llm_requests_queued_total", "Total queued requests")
dead_letter_total = Counter("llm_dead_letter_total", "Requests moved to dead letter")
dead_letter_size = Gauge("llm_dead_letter_size", "Current dead letter size")

app = FastAPI(title="LLM Load Balancer - Production Ready")
lb = LLMLoadBalancer()

connected_clients: set[WebSocket] = set()


class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    stream: bool = False
    priority: int = 1


def get_client_id(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.get("/")
async def dashboard():
    try:
        return FileResponse("/app/webui/dashboard.html")
    except Exception:
        return {"status": "running", "message": "Dashboard not available"}


@app.get("/metrics")
async def metrics():
    return generate_latest()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
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
                "queue_size": len(lb._priority_queue),
                "dead_letter_size": len(lb._dead_letter_queue),
            }
            await websocket.send_json(stats_data)
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connected_clients.discard(websocket)


@app.get("/health")
async def health():
    queue_size.set(len(lb._priority_queue))
    dead_letter_size.set(len(lb._dead_letter_queue))

    for worker_id, worker in lb.workers.items():
        worker_status.labels(worker_id=worker_id).set(
            1 if worker.status == WorkerStatus.HEALTHY else 0
        )
        worker_connections.labels(worker_id=worker_id).set(worker.connections)
        state_map = {
            CircuitState.CLOSED: 0,
            CircuitState.OPEN: 1,
            CircuitState.HALF_OPEN: 2,
        }
        circuit_breaker_state.labels(worker_id=worker_id).set(
            state_map[worker.circuit_state]
        )

    return {
        "status": "healthy",
        "workers": {k: v.status.value for k, v in lb.workers.items()},
        "queue_size": len(lb._priority_queue),
        "dead_letter_size": len(lb._dead_letter_queue),
        "streaming_enabled": lb.config.get("streaming_enabled", True),
    }


@app.post("/infer")
async def infer(
    request: InferenceRequest,
    http_request: Request,
    x_request_id: Optional[str] = Header(None),
):
    if lb.rate_limiter:
        client_id = get_client_id(http_request)
        if not await lb.rate_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
            )

    payload = request.dict()
    stream = payload.pop("stream", False)
    request_id = x_request_id or str(uuid.uuid4())

    try:
        if stream:
            return StreamingResponse(
                lb.forward_request_stream(payload, request_id),
                media_type="text/event-stream",
            )

        result = await lb.forward_request(payload, request_id=request_id)
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
async def infer_raw(
    request: Request,
    x_request_id: Optional[str] = Header(None),
):
    payload = await request.json()
    stream = payload.get("stream", False)
    request_id = x_request_id or str(uuid.uuid4())

    if stream:
        return StreamingResponse(
            lb.forward_request_stream(payload, request_id),
            media_type="text/event-stream",
        )

    return await lb.forward_request(payload, request_id=request_id)


@app.get("/queue/{queue_id}")
async def get_queue_status(queue_id: str):
    for item in lb._priority_queue:
        if item.id == queue_id:
            return {
                "id": item.id,
                "status": "pending",
                "priority": item.priority,
                "retries": item.retries,
                "created_at": item.created_at,
                "request_id": item.request_id,
            }

    for item in lb._dead_letter_queue:
        if item.id == queue_id:
            return {
                "id": item.id,
                "status": "failed",
                "error": item.error,
                "retries": item.retries,
                "created_at": item.created_at,
                "failed_at": item.failed_at,
                "request_id": item.request_id,
            }

    raise HTTPException(status_code=404, detail="Queue item not found")


@app.delete("/queue/{queue_id}")
async def cancel_queue_item(queue_id: str):
    for i, item in enumerate(lb._priority_queue):
        if item.id == queue_id:
            lb._priority_queue.pop(i)
            heapq.heapify(lb._priority_queue)
            queue_size.set(len(lb._priority_queue))
            return {"status": "cancelled", "id": queue_id}

    raise HTTPException(status_code=404, detail="Queue item not found")


@app.get("/dead-letter")
async def get_dead_letter():
    return {
        "size": len(lb._dead_letter_queue),
        "items": [
            {
                "id": item.id,
                "error": item.error,
                "retries": item.retries,
                "failed_at": item.failed_at,
                "request_id": item.request_id,
            }
            for item in lb._dead_letter_queue[-50:]
        ],
    }


@app.delete("/dead-letter")
async def clear_dead_letter():
    count = len(lb._dead_letter_queue)
    lb._dead_letter_queue.clear()
    dead_letter_size.set(0)
    return {"status": "cleared", "count": count}


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
        "queue_size": len(lb._priority_queue),
        "dead_letter_size": len(lb._dead_letter_queue),
        "config": {
            "timeout": lb.config.get("timeout"),
            "token_based_routing": lb.config.get("token_based_routing", True),
            "streaming_enabled": lb.config.get("streaming_enabled", True),
            "rate_limiting_enabled": lb.rate_limiter is not None,
        },
    }


async def healthcheck_loop():
    while not lb._shutdown_event.is_set():
        try:
            tasks = [lb.healthcheck(worker) for worker in lb.workers.values()]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Healthcheck loop error: {e}")
        await asyncio.sleep(lb.config.get("healthcheck_interval", 5))


async def queue_processor():
    while not lb._shutdown_event.is_set():
        try:
            await lb.process_queue()
        except Exception as e:
            logger.error(f"Queue processor error: {e}")
        await asyncio.sleep(2)


async def rate_limiter_cleanup():
    while not lb._shutdown_event.is_set():
        try:
            if lb.rate_limiter:
                lb.rate_limiter.cleanup()
        except Exception as e:
            logger.error(f"Rate limiter cleanup error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def startup():
    asyncio.create_task(healthcheck_loop())
    asyncio.create_task(queue_processor())
    asyncio.create_task(rate_limiter_cleanup())
    logger.info("=" * 60)
    logger.info("LLM Load Balancer - Production Ready")
    logger.info("=" * 60)
    logger.info("Endpoints:")
    logger.info("  POST /infer         - Inference endpoint")
    logger.info("  GET  /stats         - Statistics")
    logger.info("  GET  /health        - Health check")
    logger.info("  GET  /metrics       - Prometheus metrics")
    logger.info("  WS   /ws            - WebSocket for real-time updates")
    logger.info("  GET  /queue/{id}    - Queue status")
    logger.info("  GET  /dead-letter   - Failed requests")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown():
    await lb.graceful_shutdown()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
