#!/usr/bin/env python3
"""
Chaos Load Simulator - Infinite Random Simulation
Simulates various random scenarios to test the load balancer resilience.
"""

import asyncio
import aiohttp
import random
import time
import sys
from datetime import datetime
from collections import defaultdict


class ChaosSimulator:
    def __init__(self):
        self.base_url = "http://orchestrator:8000"
        self.results = []
        self.stats = defaultdict(int)
        self.scenario_count = 0

    PROMPTS = [
        "Qu'est-ce que l'intelligence artificielle?",
        "Explique le machine learning.",
        "Donne-moi une liste de编程语言.",
        "Comment fonctionne un serveur?",
        "Qu'est-ce qu'une blockchain?",
        "Explique le deep learning.",
        "Cite 5 avantages du cloud.",
        "Comment optimiser une base de données?",
        "Qu'est-ce que Docker?",
        "Explique REST API.",
    ]

    SCENARIOS = [
        ("LIGHT_LOAD", "scenario_light_load"),
        ("MEDIUM_LOAD", "scenario_medium_load"),
        ("HEAVY_LOAD", "scenario_heavy_load"),
        ("SPIKE", "scenario_spike"),
        ("BURST", "scenario_burst"),
        ("RANDOM_MIX", "scenario_random_mix"),
        ("CONTINUOUS_STREAM", "scenario_continuous_stream"),
        ("MASSIVE_PARALLEL", "scenario_massive_parallel"),
    ]

    async def send_request(self, session, prompt, max_tokens=100):
        start = time.time()
        try:
            async with session.post(
                f"{self.base_url}/infer",
                json={
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": random.uniform(0.5, 0.9),
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                latency = time.time() - start
                data = await response.json()
                status = response.status
                self.stats["total"] += 1
                if status == 200:
                    self.stats["success"] += 1
                else:
                    self.stats["failed"] += 1
                return {
                    "status": status,
                    "latency": latency,
                    "worker": data.get("worker", "?"),
                    "success": status == 200,
                }
        except asyncio.TimeoutError:
            self.stats["timeout"] += 1
            return {
                "status": 0,
                "latency": time.time() - start,
                "worker": "timeout",
                "success": False,
            }
        except Exception as e:
            self.stats["error"] += 1
            return {
                "status": 0,
                "latency": time.time() - start,
                "worker": "error",
                "success": False,
            }

    async def scenario_light_load(self, session):
        print("  🌱 LIGHT LOAD: 3 requêtes séquentielles")
        for i in range(3):
            r = await self.send_request(session, random.choice(self.PROMPTS), 50)
            self.results.append(r)
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} {r['worker']} - {r['latency']:.2f}s")
            await asyncio.sleep(0.3)

    async def scenario_medium_load(self, session):
        print("  ⚡ MEDIUM LOAD: 10 requêtes parallèles")
        tasks = [
            self.send_request(session, random.choice(self.PROMPTS), 80)
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            self.results.append(r)
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} {r['worker']} - {r['latency']:.2f}s")

    async def scenario_heavy_load(self, session):
        print("  🔥 HEAVY LOAD: 25 requêtes parallèles")
        tasks = [
            self.send_request(session, random.choice(self.PROMPTS), 120)
            for _ in range(25)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            self.results.append(r)
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} {r['worker']} - {r['latency']:.2f}s")

    async def scenario_spike(self, session):
        count = random.randint(15, 30)
        print(f"  ⚡⚡ SPIKE: {count} requêtes simultanées!")
        tasks = [
            self.send_request(session, random.choice(self.PROMPTS), 100)
            for _ in range(count)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            self.results.append(r)
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} {r['worker']} - {r['latency']:.2f}s")

    async def scenario_burst(self, session):
        bursts = random.randint(2, 4)
        print(f"  💥 BURST: {bursts} salves de 8 requêtes")
        for b in range(bursts):
            print(f"    --- Salve {b + 1}/{bursts} ---")
            tasks = [
                self.send_request(session, random.choice(self.PROMPTS), 60)
                for _ in range(8)
            ]
            results = await asyncio.gather(*tasks)
            for r in results:
                self.results.append(r)
                icon = "✅" if r["success"] else "❌"
                print(f"      {icon} {r['worker']} - {r['latency']:.2f}s")
            await asyncio.sleep(random.uniform(0.5, 2))

    async def scenario_random_mix(self, session):
        print("  🎲 RANDOM MIX: 5 requêtes normales + 3 longues")
        tasks = [
            *[
                self.send_request(
                    session, random.choice(self.PROMPTS), random.randint(50, 100)
                )
                for _ in range(5)
            ],
            *[
                self.send_request(
                    session, random.choice(self.PROMPTS), random.randint(150, 250)
                )
                for _ in range(3)
            ],
        ]
        random.shuffle(tasks)
        results = await asyncio.gather(*tasks)
        for r in results:
            self.results.append(r)
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} {r['worker']} - {r['latency']:.2f}s")

    async def scenario_continuous_stream(self, session):
        duration = random.randint(3, 6)
        print(f"  🌊 CONTINUOUS: {duration}s de requêtes continues")
        end_time = time.time() + duration
        count = 0
        while time.time() < end_time:
            r = await self.send_request(session, random.choice(self.PROMPTS), 80)
            self.results.append(r)
            count += 1
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} {r['worker']} - {r['latency']:.2f}s")
            await asyncio.sleep(random.uniform(0.1, 0.4))
        print(f"    → {count} requêtes traitées")

    async def scenario_massive_parallel(self, session):
        count = random.randint(40, 60)
        print(f"  🚀 MASSIVE PARALLEL: {count} requêtes en parallèle!")
        tasks = [
            self.send_request(session, random.choice(self.PROMPTS), 100)
            for _ in range(count)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            self.results.append(r)
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} {r['worker']} - {r['latency']:.2f}s")

    def print_header(self):
        print("\n" + "=" * 70)
        print("  🔄 CHAOS LOAD SIMULATOR - INFINITE LOOP")
        print("=" * 70)
        print(f"  Started: {datetime.now().strftime('%H:%M:%S')}")
        print("  Press Ctrl+C to stop")
        print("=" * 70)

    def print_stats(self):
        total = len(self.results)
        if total == 0:
            return

        success = sum(1 for r in self.results if r["success"])
        failed = total - success

        workers = defaultdict(int)
        latencies = []
        for r in self.results:
            workers[r["worker"]] += 1
            latencies.append(r["latency"])

        print("\n" + "-" * 70)
        print(f"  📊 STATS (Total: {total} requêtes)")
        print("-" * 70)
        print(f"  ✅ Success: {success} ({success / total * 100:.1f}%)")
        print(f"  ❌ Failed: {failed} ({failed / total * 100:.1f}%)")
        print(f"  ⏱️  Avg Latency: {sum(latencies) / len(latencies):.2f}s")
        print(f"  🐢 Min: {min(latencies):.2f}s | 🐇 Max: {max(latencies):.2f}s")
        print(f"  📦 Workers: {dict(workers)}")
        print(f"  🔢 Scenarios: {self.scenario_count}")
        print("-" * 70)

    async def run(self):
        self.print_header()

        async with aiohttp.ClientSession() as session:
            print("\n⏳ Waiting for orchestrator...")
            for _ in range(10):
                try:
                    async with session.get(
                        f"{self.base_url}/health",
                        timeout=aiohttp.ClientTimeout(total=2),
                    ) as resp:
                        if resp.status == 200:
                            print("✅ Orchestrator ready!\n")
                            break
                except:
                    await asyncio.sleep(1)

            iteration = 0
            while True:
                iteration += 1
                scenario_name, scenario_method = random.choice(self.SCENARIOS)

                print(f"\n{'=' * 70}")
                print(f"  🔄 ITERATION #{iteration} | Scenario: {scenario_name}")
                print(f"  ⏰ {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 70)

                self.scenario_count += 1

                try:
                    scenario_func = getattr(self, scenario_method)
                    await scenario_func(session)
                except Exception as e:
                    print(f"  ⚠️ Error in scenario: {e}")

                if iteration % 5 == 0:
                    self.print_stats()

                wait_time = random.uniform(2, 8)
                print(f"\n  💤 Pause: {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)


async def main():
    try:
        await ChaosSimulator().run()
    except KeyboardInterrupt:
        print("\n\n🛑 Simulation arrêtée par l'utilisateur")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
