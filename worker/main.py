import argparse
import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WorkerMetrics:
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    avg_latency: float = 0
    latencies: deque = None

    def __post_init__(self):
        self.latencies = deque(maxlen=100)


class LLMWorker:
    def __init__(self, worker_id: str, port: int):
        self.id = worker_id
        self.port = port
        self.app = FastAPI(title=f"LLM Worker {worker_id}")
        self.metrics = WorkerMetrics()
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "worker_id": self.id}

        @self.app.post("/infer")
        async def infer(request: Request):
            self.metrics.requests_total += 1
            start_time = time.time()

            try:
                payload = await request.json()
                prompt = payload.get("prompt", "")
                tokens = payload.get("max_tokens", 50)

                latency = self._simulate_inference(prompt, tokens)

                self.metrics.requests_success += 1
                self.metrics.latencies.append(latency)
                self.metrics.avg_latency = sum(self.metrics.latencies) / len(
                    self.metrics.latencies
                )

                return {
                    "worker_id": self.id,
                    "prompt": prompt,
                    "response": self._generate_response(prompt),
                    "tokens_generated": tokens,
                    "latency": latency,
                }

            except Exception as e:
                self.metrics.requests_failed += 1
                logger.error(f"Error processing request: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/metrics")
        async def metrics():
            return {
                "worker_id": self.id,
                "requests_total": self.metrics.requests_total,
                "requests_success": self.metrics.requests_success,
                "requests_failed": self.metrics.requests_failed,
                "avg_latency": self.metrics.avg_latency,
                "success_rate": self.metrics.requests_success
                / max(1, self.metrics.requests_total),
            }

    def _simulate_inference(self, prompt: str, tokens: int) -> float:
        base_latency = len(prompt) * 0.001
        token_latency = tokens * 0.02
        variance = random.uniform(0.5, 1.5)
        error_chance = random.random()

        if error_chance < 0.02:
            raise Exception("Simulated worker error")

        return (base_latency + token_latency) * variance

    def _generate_response(self, prompt: str) -> str:
        responses = [
            "Voici une réponse générée par le modèle LLM.",
            "L'inférence a été effectuée avec succès.",
            "Le modèle a traité votre requête et retourne ce résultat.",
            "Réponse simulée pour démontrer le load balancing.",
        ]
        return random.choice(responses)

    def run(self):
        import uvicorn

        logger.info(f"Starting worker {self.id} on port {self.port}")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Worker")
    parser.add_argument(
        "--port", type=int, required=True, help="Port to run the worker on"
    )
    parser.add_argument(
        "--id", type=str, required=True, help="Worker ID (e.g., M1, M2, M3)"
    )
    args = parser.parse_args()

    worker = LLMWorker(args.id, args.port)
    worker.run()
