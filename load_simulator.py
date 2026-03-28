#!/usr/bin/env python3
"""
Load Simulator for LLM Load Balancer
Simulates realistic traffic patterns to test the load balancing system.
"""

import asyncio
import aiohttp
import random
import time
import json
from datetime import datetime


ORCHESTRATOR_URL = "http://orchestrator:8000"
FALLBACK_URL = "http://localhost:8000"


class LoadSimulator:
    def __init__(self, base_url=None):
        self.base_url = base_url or FALLBACK_URL
        self.results = []

    PROMPTS = [
        "Explique moi ce qu'est le machine learning en une phrase.",
        "Donne moi une liste de 3 fruits.",
        "Qu'est-ce que 2+2?",
        "Raconte moi une blague courte.",
        "Quels sont les avantages du cloud computing?",
        "Explique la difference entre RAM et ROM.",
        "Donne moi le resume d'un article sur l'IA.",
        "Liste 5 langages de programmation populaires.",
        "Qu'est-ce qu'un serveur proxy?",
        "Explique le fonctionnement d'une blockchain.",
    ]

    async def send_request(self, session, prompt, max_tokens=100):
        start = time.time()
        try:
            async with session.post(
                f"{self.base_url}/infer",
                json={"prompt": prompt, "max_tokens": max_tokens, "temperature": 0.7},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                status = response.status
                data = await response.json()
                latency = time.time() - start
                return {
                    "status": status,
                    "latency": latency,
                    "worker": data.get("worker", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                    "success": status == 200,
                }
        except Exception as e:
            return {
                "status": 0,
                "latency": time.time() - start,
                "worker": "error",
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "error": str(e),
            }

    async def steady_load(self, duration_seconds=60, requests_per_minute=30):
        interval = 60 / requests_per_minute
        end_time = time.time() + duration_seconds
        print(f"\n=== STEADY LOAD TEST ===")
        print(f"Duration: {duration_seconds}s | Rate: {requests_per_minute} req/min")
        print("-" * 50)

        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                prompt = random.choice(self.PROMPTS)
                result = await self.send_request(session, prompt)
                self.results.append(result)

                status_icon = "OK" if result["success"] else "FAIL"
                print(
                    f"[{status_icon}] Status: {result['status']} | "
                    f"Latency: {result['latency']:.2f}s | Worker: {result['worker']}"
                )

                await asyncio.sleep(interval)

    async def spike_load(self, concurrent_requests=20):
        print(f"\n=== SPIKE LOAD TEST ===")
        print(f"Concurrent requests: {concurrent_requests}")
        print("-" * 50)

        async with aiohttp.ClientSession() as session:
            tasks = [
                self.send_request(session, random.choice(self.PROMPTS))
                for _ in range(concurrent_requests)
            ]
            results = await asyncio.gather(*tasks)

            for result in results:
                self.results.append(result)
                status_icon = "OK" if result["success"] else "FAIL"
                print(
                    f"[{status_icon}] Status: {result['status']} | "
                    f"Latency: {result['latency']:.2f}s | Worker: {result['worker']}"
                )

    async def burst_load(self, bursts=5, requests_per_burst=10, gap_seconds=5):
        print(f"\n=== BURST LOAD TEST ===")
        print(f"Bursts: {bursts} | Requests per burst: {requests_per_burst}")
        print("-" * 50)

        async with aiohttp.ClientSession() as session:
            for burst_num in range(bursts):
                print(f"\n--- Burst {burst_num + 1}/{bursts} ---")
                tasks = [
                    self.send_request(session, random.choice(self.PROMPTS))
                    for _ in range(requests_per_burst)
                ]
                results = await asyncio.gather(*tasks)

                for result in results:
                    self.results.append(result)
                    status_icon = "OK" if result["success"] else "FAIL"
                    print(
                        f"[{status_icon}] Status: {result['status']} | "
                        f"Latency: {result['latency']:.2f}s | Worker: {result['worker']}"
                    )

                if burst_num < bursts - 1:
                    print(f"Waiting {gap_seconds}s...")
                    await asyncio.sleep(gap_seconds)

    async def variable_load(self, duration_seconds=120):
        print(f"\n=== VARIABLE LOAD TEST ===")
        print(f"Duration: {duration_seconds}s")
        print("-" * 50)

        patterns = [
            (10, 2),  # (requests_per_minute, duration_seconds)
            (60, 5),
            (120, 3),
            (30, 5),
            (90, 4),
            (15, 3),
            (100, 5),
        ]

        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            pattern_index = 0

            while time.time() - start_time < duration_seconds:
                if pattern_index >= len(patterns):
                    pattern_index = 0

                rpm, duration = patterns[pattern_index]
                interval = 60 / rpm if rpm > 0 else 1
                pattern_end = time.time() + duration

                print(f"\nPattern: {rpm} req/min for {duration}s")

                while (
                    time.time() < pattern_end
                    and time.time() - start_time < duration_seconds
                ):
                    prompt = random.choice(self.PROMPTS)
                    result = await self.send_request(session, prompt)
                    self.results.append(result)

                    status_icon = "OK" if result["success"] else "FAIL"
                    print(
                        f"[{status_icon}] Status: {result['status']} | "
                        f"Latency: {result['latency']:.2f}s | Worker: {result['worker']}"
                    )

                    await asyncio.sleep(interval)

                pattern_index += 1

    def print_summary(self):
        if not self.results:
            print("\nNo results to summarize.")
            return

        total = len(self.results)
        successful = sum(1 for r in self.results if r["success"])
        failed = total - successful
        avg_latency = sum(r["latency"] for r in self.results) / total
        min_latency = min(r["latency"] for r in self.results)
        max_latency = max(r["latency"] for r in self.results)

        worker_distribution = {}
        for r in self.results:
            worker = r.get("worker", "unknown")
            worker_distribution[worker] = worker_distribution.get(worker, 0) + 1

        print("\n" + "=" * 50)
        print("           LOAD TEST SUMMARY")
        print("=" * 50)
        print(f"Total Requests:     {total}")
        print(f"Successful:         {successful} ({successful / total * 100:.1f}%)")
        print(f"Failed:             {failed} ({failed / total * 100:.1f}%)")
        print(f"Avg Latency:        {avg_latency:.3f}s")
        print(f"Min Latency:        {min_latency:.3f}s")
        print(f"Max Latency:        {max_latency:.3f}s")
        print("\nWorker Distribution:")
        for worker, count in sorted(worker_distribution.items()):
            print(f"  {worker}: {count} ({count / total * 100:.1f}%)")
        print("=" * 50)


async def main():
    simulator = LoadSimulator()

    print("=" * 50)
    print("   LLM LOAD BALANCER - LOAD SIMULATOR")
    print("=" * 50)

    test_type = input(
        "\nSelect test type:\n"
        "1. Steady Load (constant rate)\n"
        "2. Spike Load (sudden burst)\n"
        "3. Burst Load (repeated bursts)\n"
        "4. Variable Load (mixed patterns)\n"
        "5. All Tests\n"
        "Choice (1-5): "
    ).strip()

    if test_type == "1":
        await simulator.steady_load(duration_seconds=30, requests_per_minute=20)
    elif test_type == "2":
        await simulator.spike_load(concurrent_requests=15)
    elif test_type == "3":
        await simulator.burst_load(bursts=3, requests_per_burst=8, gap_seconds=3)
    elif test_type == "4":
        await simulator.variable_load(duration_seconds=60)
    elif test_type == "5":
        await simulator.spike_load(concurrent_requests=10)
        await simulator.steady_load(duration_seconds=20, requests_per_minute=15)
        await simulator.burst_load(bursts=2, requests_per_burst=6, gap_seconds=3)
    else:
        print("Invalid choice. Running default test...")
        await simulator.spike_load(concurrent_requests=10)

    simulator.print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
