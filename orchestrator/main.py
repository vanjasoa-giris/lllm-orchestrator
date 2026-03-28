import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class Worker:
    id: str
    url: str
    status: WorkerStatus = WorkerStatus.UNHEALTHY
    connections: int = 0
    latencies: list = field(default_factory=list)
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_open_time: Optional[float] = None
    weight: int = 1


@dataclass
class QueueItem:
    id: str
    payload: dict
    priority: int = 1
    created_at: float = field(default_factory=time.time)
    retries: int = 0


class LoadBalancer:
    def __init__(self, config_path: str = "../config/workers.yaml"):
        self.workers: dict[str, Worker] = {}
        self.request_queue: list[QueueItem] = []
        self.config = self._load_config(config_path)
        self._initialize_workers()

    def _load_config(self, path: str) -> dict:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config not found: {path}, using defaults")
            return {
                "workers": [
                    {"id": "M1", "url": "http://localhost:8001", "weight": 1},
                    {"id": "M2", "url": "http://localhost:8002", "weight": 1},
                    {"id": "M3", "url": "http://localhost:8003", "weight": 1},
                ],
                "timeout": 30,
                "max_retries": 3,
            }

    def _initialize_workers(self):
        for w in self.config.get("workers", []):
            self.workers[w["id"]] = Worker(
                id=w["id"], url=w["url"], weight=w.get("weight", 1)
            )
        logger.info(f"Initialized {len(self.workers)} workers")

    def _calculate_score(self, worker: Worker) -> float:
        if worker.status != WorkerStatus.HEALTHY:
            return 0

        avg_latency = (
            sum(worker.latencies[-10:]) / len(worker.latencies[-10:])
            if worker.latencies
            else 1
        )
        return (1 / (worker.connections + 1)) * (1 / avg_latency) * worker.weight

    def select_worker(self) -> Optional[Worker]:
        healthy_workers = [
            w
            for w in self.workers.values()
            if w.status == WorkerStatus.HEALTHY and w.circuit_state != CircuitState.OPEN
        ]

        if not healthy_workers:
            return None

        return max(healthy_workers, key=self._calculate_score)

    async def healthcheck(self, worker: Worker):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{worker.url}/health")
                if response.status_code == 200:
                    worker.consecutive_successes += 1
                    worker.consecutive_failures = 0
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
        except Exception:
            worker.consecutive_failures += 1
            self._handle_failure(worker)

    def _handle_failure(self, worker: Worker):
        if worker.consecutive_failures >= 3:
            worker.status = WorkerStatus.UNHEALTHY
        if (
            worker.consecutive_failures >= 5
            and worker.circuit_state == CircuitState.CLOSED
        ):
            worker.circuit_state = CircuitState.OPEN
            worker.circuit_open_time = time.time()
            logger.warning(f"Circuit opened for {worker.id}")

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
            async with httpx.AsyncClient(
                timeout=self.config.get("timeout", 30)
            ) as client:
                response = await client.post(f"{worker.url}/infer", json=payload)
                latency = time.time() - start_time
                worker.latencies.append(latency)

                if response.status_code == 200:
                    result = response.json()
                    result["worker"] = worker.id
                    result["latency"] = latency
                    return result
                else:
                    raise HTTPException(
                        status_code=response.status_code, detail=response.text
                    )

        except httpx.TimeoutException:
            logger.error(f"Timeout for worker {worker.id}")
            raise HTTPException(status_code=504, detail="Worker timeout")
        except Exception as e:
            logger.error(f"Error forwarding to {worker.id}: {e}")
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


app = FastAPI(title="LLM Load Balancer Orchestrator")
lb = LoadBalancer()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "workers": {k: v.status.value for k, v in lb.workers.items()},
    }


@app.post("/infer")
async def infer(request: Request):
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
            }
            for k, v in lb.workers.items()
        },
        "queue_size": len(lb.request_queue),
    }


async def healthcheck_loop():
    while True:
        for worker in lb.workers.values():
            await lb.healthcheck(worker)
        await asyncio.sleep(5)


async def queue_processor():
    while True:
        await lb.process_queue()
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup():
    asyncio.create_task(healthcheck_loop())
    asyncio.create_task(queue_processor())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
