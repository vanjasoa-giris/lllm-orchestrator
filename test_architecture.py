#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Script for LLM Load Balancer
"""
import httpx
import json
import asyncio
import time

ORCHESTRATOR_URL = "http://localhost:8000"
WORKER_URLS = [
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
]

async def test_health_checks():
    """Test que tous les workers repondent au health check"""
    print("\n=== TEST 1: Health Checks ===")
    async with httpx.AsyncClient() as client:
        for i, url in enumerate(WORKER_URLS, 1):
            try:
                resp = await client.get(f"{url}/health", timeout=5)
                data = resp.json()
                print(f"[OK] Worker {i} ({url}): {data.get('status')} - Backend: {data.get('backend')}")
            except Exception as e:
                print(f"[FAIL] Worker {i} ({url}): ERROR - {e}")

async def test_orchestrator_health():
    """Test la sante de l'orchestrator"""
    print("\n=== TEST 2: Orchestrator Health ===")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{ORCHESTRATOR_URL}/health", timeout=5)
            data = resp.json()
            print(f"[OK] Orchestrator Status: {data.get('status')}")
            print(f"     Workers status: {data.get('workers')}")
            print(f"     Queue size: {data.get('queue_size')}")
            print(f"     Streaming enabled: {data.get('streaming_enabled')}")
        except Exception as e:
            print(f"[FAIL] Orchestrator ERROR: {e}")

async def test_inference():
    """Test une requete d'inference simple"""
    print("\n=== TEST 3: Simple Inference Request ===")
    payload = {
        "prompt": "Bonjour, comment ca va?",
        "max_tokens": 50,
        "temperature": 0.7,
        "stream": False
    }
    async with httpx.AsyncClient() as client:
        try:
            start = time.time()
            resp = await client.post(f"{ORCHESTRATOR_URL}/infer", json=payload, timeout=10)
            duration = time.time() - start
            data = resp.json()
            print(f"[OK] Inference Success")
            print(f"     Worker: {data.get('worker')}")
            print(f"     Prompt: {payload['prompt']}")
            print(f"     Response: {data.get('response')}")
            print(f"     Tokens generated: {data.get('tokens_generated')}")
            print(f"     Latency: {data.get('latency'):.3f}s")
            print(f"     Duration (including network): {duration:.3f}s")
        except Exception as e:
            print(f"[FAIL] Inference ERROR: {e}")

async def test_streaming():
    """Test le streaming"""
    print("\n=== TEST 4: Streaming Inference ===")
    payload = {
        "prompt": "Explique le load balancing en 10 mots",
        "max_tokens": 30,
        "stream": True
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/infer",
                json=payload,
                timeout=15
            )
            print(f"[OK] Stream started")
            token_count = 0
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = json.loads(line[6:])
                    if not chunk.get("finish"):
                        token = chunk.get("token", "")
                        print(f"  [{token_count}] {token}", end="", flush=True)
                        token_count += 1
                    else:
                        print(f"\n[OK] Stream finished")
                        print(f"     Total tokens: {chunk.get('tokens_generated')}")
                        print(f"     Latency: {chunk.get('latency'):.3f}s")
                        print(f"     Tokens/sec: {chunk.get('tokens_per_second'):.2f}")
        except Exception as e:
            print(f"[FAIL] Streaming ERROR: {e}")

async def test_stats():
    """Affiche les stats de l'orchestrator"""
    print("\n=== TEST 5: Orchestrator Stats ===")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{ORCHESTRATOR_URL}/stats", timeout=5)
            data = resp.json()
            print(f"[OK] Stats retrieved")
            print(f"     Queue size: {data.get('queue_size')}")
            for worker_id, stats in data.get('workers', {}).items():
                print(f"\n     Worker {worker_id}:")
                print(f"       Status: {stats.get('status')}")
                print(f"       Circuit: {stats.get('circuit')}")
                print(f"       Connections: {stats.get('connections')}/{stats.get('max_concurrent')}")
                print(f"       Load: {stats.get('load_percentage'):.1f}%")
                print(f"       Avg latency: {stats.get('avg_latency'):.3f}s")
                print(f"       Avg TPS: {stats.get('avg_tokens_per_second'):.2f}")
        except Exception as e:
            print(f"[FAIL] Stats ERROR: {e}")

async def main():
    print("=" * 70)
    print("LLM Load Balancer - Architecture Test Suite")
    print("=" * 70)
    
    await test_health_checks()
    await asyncio.sleep(1)
    
    await test_orchestrator_health()
    await asyncio.sleep(1)
    
    await test_inference()
    await asyncio.sleep(2)
    
    await test_streaming()
    await asyncio.sleep(2)
    
    await test_stats()
    
    print("\n" + "=" * 70)
    print("Tests completed!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
