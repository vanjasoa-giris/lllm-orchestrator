import argparse
import os
import random
import time
from collections import deque
from dataclasses import dataclass
import logging
from typing import Optional
import psutil
import torch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
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
    def __init__(
        self,
        worker_id: str,
        port: int,
        backend: str = "simulated",
        model_name: str = None,
    ):
        self.id = worker_id
        self.port = port
        self.backend = backend
        self.model_name = model_name
        self.model = None
        self.app = FastAPI(title=f"LLM Worker {worker_id}")
        self.metrics = WorkerMetrics()
        self._setup_routes()
        self._load_model()

    def _load_model(self):
        if self.backend == "hf_transformers":
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer

                logger.info(f"Loading model {self.model_name}...")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
                logger.info(f"Model {self.model_name} loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.backend = "simulated"
        elif self.backend == "vllm":
            try:
                from vllm import LLM

                logger.info(f"Loading vLLM model {self.model_name}...")
                self.model = LLM(model=self.model_name)
                logger.info(f"vLLM model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load vLLM: {e}")
                self.backend = "simulated"

    def _get_system_metrics(self):
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "gpu_memory": None,
            "gpu_utilization": None,
        }

        if torch.cuda.is_available():
            try:
                metrics["gpu_memory"] = (
                    torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated()
                    if torch.cuda.max_memory_allocated() > 0
                    else 0
                )
                metrics["gpu_utilization"] = torch.cuda.utilization()
            except:
                pass

        return metrics

    def _setup_routes(self):
        @self.app.get("/health")
        async def health():
            system_metrics = self._get_system_metrics()
            return {
                "status": "healthy",
                "worker_id": self.id,
                "backend": self.backend,
                **system_metrics,
            }

        @self.app.post("/infer")
        async def infer(request: Request):
            self.metrics.requests_total += 1
            start_time = time.time()

            try:
                payload = await request.json()
                prompt = payload.get("prompt", "")
                max_tokens = payload.get("max_tokens", 256)
                temperature = payload.get("temperature", 0.7)

                if self.backend == "simulated":
                    response_text = self._simulate_inference(prompt, max_tokens)
                elif self.backend == "hf_transformers":
                    response_text = await self._hf_inference(
                        prompt, max_tokens, temperature
                    )
                elif self.backend == "vllm":
                    response_text = await self._vllm_inference(
                        prompt, max_tokens, temperature
                    )
                else:
                    response_text = self._simulate_inference(prompt, max_tokens)

                latency = time.time() - start_time

                self.metrics.requests_success += 1
                self.metrics.latencies.append(latency)
                self.metrics.avg_latency = sum(self.metrics.latencies) / len(
                    self.metrics.latencies
                )

                return {
                    "worker_id": self.id,
                    "backend": self.backend,
                    "prompt": prompt,
                    "response": response_text,
                    "tokens_generated": max_tokens,
                    "latency": latency,
                }

            except Exception as e:
                self.metrics.requests_failed += 1
                logger.error(f"Error processing request: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/metrics")
        async def metrics():
            system_metrics = self._get_system_metrics()
            return {
                "worker_id": self.id,
                "backend": self.backend,
                "model": self.model_name,
                "requests_total": self.metrics.requests_total,
                "requests_success": self.metrics.requests_success,
                "requests_failed": self.metrics.requests_failed,
                "avg_latency": self.metrics.avg_latency,
                "success_rate": self.metrics.requests_success
                / max(1, self.metrics.requests_total),
                **system_metrics,
            }

    def _simulate_inference(self, prompt: str, tokens: int) -> str:
        base_latency = len(prompt) * 0.001
        token_latency = tokens * 0.02
        variance = random.uniform(0.5, 1.5)

        error_chance = random.random()
        if error_chance < 0.02:
            raise Exception("Simulated worker error")

        time.sleep((base_latency + token_latency) * variance)

        responses = [
            "Voici une réponse générée par le modèle LLM.",
            "L'inférence a été effectuée avec succès.",
            "Le modèle a traité votre requête et retourne ce résultat.",
            "Réponse simulée pour démontrer le load balancing.",
        ]
        return random.choice(responses)

    async def _hf_inference(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str:
        if self.model is None:
            return self._simulate_inference(prompt, max_tokens)

        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        outputs = self.model.generate(
            **inputs, max_new_tokens=max_tokens, temperature=temperature, do_sample=True
        )

        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    async def _vllm_inference(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str:
        if self.model is None:
            return self._simulate_inference(prompt, max_tokens)

        from vllm import SamplingParams

        sampling_params = SamplingParams(temperature=temperature, max_tokens=max_tokens)

        outputs = self.model.generate(prompt, sampling_params)
        return outputs[0].outputs[0].text

    def run(self):
        import uvicorn

        logger.info(
            f"Starting worker {self.id} on port {self.port} with backend: {self.backend}"
        )
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Worker (Production)")
    parser.add_argument(
        "--port", type=int, required=True, help="Port to run the worker on"
    )
    parser.add_argument(
        "--id", type=str, required=True, help="Worker ID (e.g., M1, M2, M3)"
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="simulated",
        choices=["simulated", "hf_transformers", "vllm"],
        help="LLM backend to use",
    )
    parser.add_argument(
        "--model", type=str, default=None, help="Model name for HF/vLLM"
    )
    args = parser.parse_args()

    worker = LLMWorker(args.id, args.port, args.backend, args.model)
    worker.run()
