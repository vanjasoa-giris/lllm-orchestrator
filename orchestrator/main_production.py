import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
    CUSTOM = "custom"


@dataclass
class Worker:
    id: str
    url: str
    backend: LLMBackend = LLMBackend.SIMULATED
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    status: WorkerStatus = WorkerStatus.UNHEALTHY
    connections: int = 0
    latencies: list = field(default_factory=list)
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_open_time: Optional[float] = None
    weight: int = 1
    gpu_memory: Optional[float] = None
    cpu_usage: Optional[float] = None


@dataclass
class QueueItem:
    id: str
    payload: dict
    priority: int = 1
    created_at: float = field(default_factory=time.time)
    retries: int = 0


class LoadBalancer:
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
            "timeout": 30,
            "max_retries": 3,
            "healthcheck_interval": 5,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 30,
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
            )
        logger.info(f"Initialized {len(self.workers)} workers")

    def _setup_http_client(self):
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.get("timeout", 30)),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    def _calculate_score(self, worker: Worker) -> float:
        if worker.status != WorkerStatus.HEALTHY:
            return 0

        if worker.circuit_state == CircuitState.OPEN:
            return 0

        avg_latency = (
            sum(worker.latencies[-10:]) / len(worker.latencies[-10:])
            if worker.latencies
            else 1
        )

        latency_score = 1 / avg_latency
        connection_score = 1 / (worker.connections + 1)
        weight_score = worker.weight

        return latency_score * connection_score * weight_score

    def select_worker(self) -> Optional[Worker]:
        healthy_workers = [
            w
            for w in self.workers.values()
            if w.status == WorkerStatus.HEALTHY and w.circuit_state != CircuitState.OPEN
        ]

        if not healthy_workers:
            self._check_circuit_breaker_transitions()
            return None

        selected = max(healthy_workers, key=self._calculate_score)

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

    async def _call_openai(self, worker: Worker, payload: dict) -> dict:
        headers = {"Authorization": f"Bearer {worker.api_key}"}
        data = {
            "model": worker.model_name or "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": payload.get("prompt", "")}],
            "max_tokens": payload.get("max_tokens", 256),
            "temperature": payload.get("temperature", 0.7),
        }

        response = await self.http_client.post(
            "https://api.openai.com/v1/chat/completions", json=data, headers=headers
        )
        response.raise_for_status()
        result = response.json()

        return {
            "worker": worker.id,
            "response": result["choices"][0]["message"]["content"],
            "model": result["model"],
            "usage": result.get("usage", {}),
        }

    async def _call_vllm(self, worker: Worker, payload: dict) -> dict:
        data = {
            "prompt": payload.get("prompt", ""),
            "max_tokens": payload.get("max_tokens", 256),
            "temperature": payload.get("temperature", 0.7),
        }

        response = await self.http_client.post(
            f"{worker.url}/v1/completions", json=data
        )
        response.raise_for_status()
        result = response.json()

        return {
            "worker": worker.id,
            "response": result["choices"][0]["text"],
            "model": worker.model_name,
        }

    async def forward_request(self, payload: dict) -> dict:
        worker = self.select_worker()

        if not worker:
            if self.request_queue:
                queued = QueueItem(id=str(uuid.uuid4()), payload=payload)
                self.request_queue.append(queued)
                return {"status": "queued", "queue_id": queued.id}
            raise HTTPException(status_code=503, detail="No available workers")

        worker.connections += 1
        start_time = time.time()

        try:
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
            result["latency"] = latency

            worker.consecutive_failures = 0
            return result

        except httpx.TimeoutException:
            logger.error(f"Timeout for worker {worker.id}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)
            raise HTTPException(status_code=504, detail="Worker timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from {worker.id}: {e}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            logger.error(f"Error forwarding to {worker.id}: {e}")
            worker.consecutive_failures += 1
            self._handle_failure(worker)
            raise HTTPException(status_code=502, detail=str(e))
        finally:
            worker.connections -= 1

    async def process_queue(self):
        if not self.request_queue:
            return

        worker = self.select_worker()
        if worker:
            item = self.request_queue.pop(0)
            item.retries += 1
            if item.retries > 5:
                logger.warning(f"Queue item {item.id} max retries exceeded")
                return
            self.request_queue.append(item)


app = FastAPI(title="LLM Load Balancer Orchestrator (Production)")
lb = LoadBalancer()


class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "workers": {k: v.status.value for k, v in lb.workers.items()},
        "queue_size": len(lb.request_queue),
    }


@app.post("/infer")
async def infer(request: InferenceRequest):
    payload = request.dict()
    return await lb.forward_request(payload)


@app.post("/infer/raw")
async def infer_raw(request: Request):
    payload = await request.json()
    return await lb.forward_request(payload)


@app.get("/stats")
async def stats():
    return {
        "workers": {
            k: {
                "status": v.status.value,
                "connections": v.connections,
                "avg_latency": sum(v.latencies[-10:]) / len(v.latencies[-10:])
                if v.latencies
                else 0,
                "circuit": v.circuit_state.value,
                "backend": v.backend.value,
                "gpu_memory": v.gpu_memory,
                "cpu_usage": v.cpu_usage,
            }
            for k, v in lb.workers.items()
        },
        "queue_size": len(lb.request_queue),
        "config": {
            "timeout": lb.config.get("timeout"),
            "max_retries": lb.config.get("max_retries"),
        },
    }


async def healthcheck_loop():
    while True:
        for worker in lb.workers.values():
            await lb.healthcheck(worker)
        await asyncio.sleep(lb.config.get("healthcheck_interval", 5))


async def queue_processor():
    while True:
        await lb.process_queue()
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup():
    asyncio.create_task(healthcheck_loop())
    asyncio.create_task(queue_processor())
    logger.info("Load Balancer started")


@app.on_event("shutdown")
async def shutdown():
    await lb.http_client.aclose()
    logger.info("Load Balancer stopped")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
