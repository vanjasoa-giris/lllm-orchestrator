import argparse
import asyncio
import os
import random
import time
from collections import deque
from dataclasses import dataclass
import logging
from typing import Optional, AsyncIterator
import psutil
try:
    import torch
except ImportError:
    torch = None
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import sse_starlette.sse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class WorkerMetrics:
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    requests_streaming: int = 0

    avg_latency: float = 0
    avg_prefill_latency: float = 0
    avg_decode_latency: float = 0
    avg_tokens_per_second: float = 0

    latencies: deque = None
    prefill_latencies: deque = None
    decode_latencies: deque = None
    tokens_per_second: deque = None

    def __post_init__(self):
        self.latencies = deque(maxlen=100)
        self.prefill_latencies = deque(maxlen=100)
        self.decode_latencies = deque(maxlen=100)
        self.tokens_per_second = deque(maxlen=100)


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
        self.tokenizer = None
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
                if torch.cuda.is_available():
                    self.model = self.model.cuda()
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
            "gpu_memory_total": None,
            "gpu_utilization": None,
        }

        if torch is not None and torch.cuda.is_available():
            try:
                metrics["gpu_memory"] = torch.cuda.memory_allocated() / (1024**3)
                metrics["gpu_memory_total"] = torch.cuda.get_device_properties(
                    0
                ).total_memory / (1024**3)
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

                prefill_start = time.time()

                if self.backend == "simulated":
                    response_text, tokens_generated, prefill_lat, decode_lat = (
                        self._simulate_inference(prompt, max_tokens)
                    )
                elif self.backend == "hf_transformers":
                    (
                        response_text,
                        tokens_generated,
                        prefill_lat,
                        decode_lat,
                    ) = await self._hf_inference(prompt, max_tokens, temperature)
                elif self.backend == "vllm":
                    (
                        response_text,
                        tokens_generated,
                        prefill_lat,
                        decode_lat,
                    ) = await self._vllm_inference(prompt, max_tokens, temperature)
                else:
                    response_text, tokens_generated, prefill_lat, decode_lat = (
                        self._simulate_inference(prompt, max_tokens)
                    )

                latency = time.time() - start_time

                self.metrics.requests_success += 1
                self.metrics.latencies.append(latency)
                self.metrics.prefill_latencies.append(prefill_lat)
                self.metrics.decode_latencies.append(decode_lat)

                if latency > 0:
                    tps = tokens_generated / latency
                    self.metrics.tokens_per_second.append(tps)

                self.metrics.avg_latency = sum(self.metrics.latencies) / len(
                    self.metrics.latencies
                )
                self.metrics.avg_prefill_latency = sum(
                    self.metrics.prefill_latencies
                ) / len(self.metrics.prefill_latencies)
                self.metrics.avg_decode_latency = sum(
                    self.metrics.decode_latencies
                ) / len(self.metrics.decode_latencies)
                self.metrics.avg_tokens_per_second = sum(
                    self.metrics.tokens_per_second
                ) / len(self.metrics.tokens_per_second)

                return {
                    "worker_id": self.id,
                    "backend": self.backend,
                    "prompt": prompt,
                    "response": response_text,
                    "tokens_generated": tokens_generated,
                    "prefill_latency": prefill_lat,
                    "decode_latency": decode_lat,
                    "latency": latency,
                    "tokens_per_second": tps,
                }

            except Exception as e:
                self.metrics.requests_failed += 1
                logger.error(f"Error processing request: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/infer/stream")
        async def infer_stream(request: Request):
            self.metrics.requests_total += 1
            self.metrics.requests_streaming += 1
            start_time = time.time()

            async def generate():
                try:
                    payload = await request.json()
                    prompt = payload.get("prompt", "")
                    max_tokens = payload.get("max_tokens", 256)
                    temperature = payload.get("temperature", 0.7)

                    prefill_start = time.time()

                    if self.backend == "simulated":
                        tokens = self._simulate_streaming(
                            prompt, max_tokens, temperature
                        )
                    elif self.backend == "hf_transformers":
                        tokens = await self._hf_streaming(
                            prompt, max_tokens, temperature
                        )
                    elif self.backend == "vllm":
                        tokens = await self._vllm_streaming(
                            prompt, max_tokens, temperature
                        )
                    else:
                        tokens = self._simulate_streaming(
                            prompt, max_tokens, temperature
                        )

                    prefill_latency = time.time() - prefill_start

                    generated_tokens = 0
                    for token_text in tokens:
                        generated_tokens += 1

                        chunk = {
                            "token": token_text,
                            "tokens_generated": generated_tokens,
                            "prefill_latency": prefill_latency
                            if generated_tokens == 1
                            else None,
                            "finish": False,
                        }
                        yield f"data: {chunk}\n\n"

                        await asyncio.sleep(0.01)

                    latency = time.time() - start_time
                    decode_latency = latency - prefill_latency

                    self.metrics.latencies.append(latency)
                    self.metrics.prefill_latencies.append(prefill_latency)
                    self.metrics.decode_latencies.append(decode_latency)

                    if latency > 0:
                        tps = generated_tokens / latency
                        self.metrics.tokens_per_second.append(tps)

                    final_chunk = {
                        "finish": True,
                        "tokens_generated": generated_tokens,
                        "latency": latency,
                        "tokens_per_second": tps,
                    }
                    yield f"data: {final_chunk}\n\n"

                    self.metrics.requests_success += 1

                except Exception as e:
                    self.metrics.requests_failed += 1
                    yield f'data: {{"error": "{str(e)}"}}\n\n'

            return StreamingResponse(generate(), media_type="text/event-stream")

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
                "requests_streaming": self.metrics.requests_streaming,
                "avg_latency": self.metrics.avg_latency,
                "avg_prefill_latency": self.metrics.avg_prefill_latency,
                "avg_decode_latency": self.metrics.avg_decode_latency,
                "avg_tokens_per_second": self.metrics.avg_tokens_per_second,
                "success_rate": self.metrics.requests_success
                / max(1, self.metrics.requests_total),
                **system_metrics,
            }

    def _simulate_inference(self, prompt: str, tokens: int, temperature: float = 0.7):
        prompt_tokens = len(prompt) // 4

        prefill_latency = prompt_tokens * 0.001 + random.uniform(0.05, 0.15)
        decode_latency = tokens * (0.01 + random.uniform(-0.005, 0.005))
        total_latency = prefill_latency + decode_latency

        time.sleep(total_latency)

        error_chance = random.random()
        if error_chance < 0.02:
            raise Exception("Simulated worker error")

        responses = [
            "Voici une réponse générée par le modèle LLM.",
            "L'inférence a été effectuée avec succès.",
            "Le modèle a traité votre requête et retourne ce résultat.",
            "Réponse simulée pour démontrer le load balancing.",
        ]

        response_text = " ".join(random.choices(responses, k=min(tokens // 10, 4)))

        return response_text, tokens, prefill_latency, decode_latency

    def _simulate_streaming(self, prompt: str, tokens: int, temperature: float = 0.7):
        prompt_tokens = len(prompt) // 4
        prefill_latency = prompt_tokens * 0.001 + random.uniform(0.05, 0.15)

        time.sleep(prefill_latency)

        word_pool = [
            "Le",
            "modèle",
            "génère",
            "une",
            "réponse",
            "token",
            "par",
            "token",
            "pour",
            "démontrer",
            "le",
            "streaming",
            "en",
            "temps",
            "réel",
            "Ceci",
            "est",
            "une",
            "simulation",
            "de",
            "prétraitement",
            "rapide",
        ]

        for _ in range(tokens):
            yield random.choice(word_pool) + " "

    async def _hf_inference(self, prompt: str, max_tokens: int, temperature: float):
        if self.model is None or self.tokenizer is None or torch is None:
            return self._simulate_inference(prompt, max_tokens)

        prefill_start = time.time()

        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        prompt_tokens = inputs["input_ids"].shape[1]
        prefill_latency = time.time() - prefill_start

        decode_start = time.time()

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=self.tokenizer.pad_token_id,
        )

        decode_latency = time.time() - decode_start

        response_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        return response_text, max_tokens, prefill_latency, decode_latency

    async def _hf_streaming(self, prompt: str, max_tokens: int, temperature: float):
        if self.model is None or self.tokenizer is None or torch is None:
            for token in self._simulate_streaming(prompt, max_tokens, temperature):
                yield token
            return

        prefill_start = time.time()

        inputs = self.tokenizer(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        prompt_tokens = inputs["input_ids"].shape[1]

        time.sleep(prompt_tokens * 0.001)

        generated_ids = inputs["input_ids"]

        for _ in range(max_tokens):
            with torch.no_grad():
                outputs = self.model(generated_ids)
                next_token_logits = outputs.logits[:, -1, :]

                if temperature > 0:
                    next_token_logits = next_token_logits / temperature
                    probs = torch.softmax(next_token_logits, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1)
                else:
                    next_token = torch.argmax(next_token_logits, dim=-1, keepdim=True)

            generated_ids = torch.cat([generated_ids, next_token], dim=-1)

            token_text = self.tokenizer.decode(next_token[0], skip_special_tokens=True)
            yield token_text

            if next_token.item() == self.tokenizer.eos_token_id:
                break

    async def _vllm_inference(self, prompt: str, max_tokens: int, temperature: float):
        if self.model is None:
            return self._simulate_inference(prompt, max_tokens)

        prefill_start = time.time()

        from vllm import SamplingParams

        sampling_params = SamplingParams(
            temperature=temperature, max_tokens=max_tokens, stream=False
        )

        outputs = self.model.generate(prompt, sampling_params)

        prefill_latency = time.time() - prefill_start
        decode_latency = 0

        response_text = outputs[0].outputs[0].text

        return response_text, max_tokens, prefill_latency, decode_latency

    async def _vllm_streaming(self, prompt: str, max_tokens: int, temperature: float):
        if self.model is None:
            for token in self._simulate_streaming(prompt, max_tokens, temperature):
                yield token
            return

        from vllm import SamplingParams

        sampling_params = SamplingParams(
            temperature=temperature, max_tokens=max_tokens, stream=True
        )

        results = self.model.generate(prompt, sampling_params)

        for output in results:
            for token in output.outputs:
                yield token.text

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
