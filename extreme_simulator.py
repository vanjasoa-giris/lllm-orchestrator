#!/usr/bin/env python3
"""
Extreme Load Simulator - 200+ req/s with RabbitMQ
Uses RabbitMQ for queuing and publishes metrics to track performance.
"""

import asyncio
import aiohttp
import random
import time
import sys
import os
import json
from datetime import datetime
from collections import defaultdict
import aio_pika


class ExtremeLoadSimulator:
    def __init__(self):
        self.base_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8000")
        self.rabbitmq_url = os.environ.get(
            "RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/"
        )
        self.results = []
        self.stats = defaultdict(int)
        self.scenario_count = 0
        self.start_time = time.time()
        self.connection = None
        self.channel = None
        self.queue = None

    PROMPTS = [
        "Qu'est-ce que l'IA?",
        "Explique ML",
        "Langages de prog",
        "Serveur?",
        "Blockchain?",
        "Deep learning?",
        "Cloud computing?",
        "Docker?",
        "REST API?",
        "Database?",
        "CPU vs GPU?",
        "API REST vs GraphQL?",
        "Microservices?",
        "Kubernetes?",
        "CI/CD?",
        "DevOps?",
        "Agile?",
        "Scrum?",
    ]

    async def setup_rabbitmq(self):
        try:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            self.queue = await self.channel.declare_queue("llm_requests", durable=True)
            print("  🐰 RabbitMQ connected!")
        except Exception as e:
            print(f"  ⚠️ RabbitMQ not available: {e}")
            self.queue = None

    async def publish_to_queue(self, message: dict):
        if self.queue:
            try:
                await self.channel.default_exchange.publish(
                    aio_pika.Message(body=json.dumps(message).encode()),
                    routing_key="llm_requests",
                )
            except:
                pass

    async def send_request(self, session, prompt, max_tokens=100):
        start = time.time()
        req_id = f"req_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

        try:
            async with session.post(
                f"{self.base_url}/infer",
                json={
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": random.uniform(0.5, 0.9),
                },
                headers={"X-Request-ID": req_id},
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

                result = {
                    "req_id": req_id,
                    "status": status,
                    "latency": latency,
                    "worker": data.get("worker", "?"),
                    "success": status == 200,
                    "timestamp": datetime.now().isoformat(),
                }

                await self.publish_to_queue(result)
                return result

        except asyncio.TimeoutError:
            self.stats["timeout"] += 1
            return {
                "req_id": req_id,
                "status": 0,
                "latency": time.time() - start,
                "worker": "timeout",
                "success": False,
            }
        except Exception as e:
            self.stats["error"] += 1
            return {
                "req_id": req_id,
                "status": 0,
                "latency": time.time() - start,
                "worker": "error",
                "success": False,
            }

    async def scenario_sustained_high_load(self, session, duration=10, rps=200):
        print(f"  🚀 SUSTAINED HIGH LOAD: ~{rps} req/s for {duration}s")
        start = time.time()
        batch_size = 50
        batches = rps // batch_size
        interval = 1.0 / (rps / batch_size)

        total_sent = 0
        while time.time() - start < duration:
            batch_start = time.time()
            tasks = [
                self.send_request(
                    session, random.choice(self.PROMPTS), random.randint(50, 150)
                )
                for _ in range(batch_size)
            ]
            results = await asyncio.gather(*tasks)
            for r in results:
                self.results.append(r)
            total_sent += len(results)

            elapsed = time.time() - batch_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

            current_rps = (
                total_sent / (time.time() - start) if time.time() - start > 0 else 0
            )
            success_rate = sum(1 for r in results if r["success"]) / len(results) * 100
            print(
                f"    📊 {total_sent} req | {current_rps:.1f} req/s | Success: {success_rate:.1f}%"
            )

    async def scenario_spike(self, session, count=500):
        print(f"  ⚡⚡ MEGA SPIKE: {count} simultaneous requests!")
        tasks = [
            self.send_request(session, random.choice(self.PROMPTS), 100)
            for _ in range(count)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            self.results.append(r)

        success = sum(1 for r in results if r["success"])
        avg_latency = sum(r["latency"] for r in results) / len(results)
        print(f"    ✅ {success}/{len(results)} success | Avg: {avg_latency:.2f}s")

    async def scenario_variable_load(self, session, phases=5):
        print(f"  📈 VARIABLE LOAD: {phases} phases with different intensities")
        phases_config = [
            (50, 3),  # (rps, duration)
            (100, 3),
            (200, 5),
            (150, 3),
            (250, 5),
        ]

        for i, (rps, duration) in enumerate(phases_config[:phases]):
            print(f"    Phase {i + 1}: {rps} req/s for {duration}s")
            await self.scenario_sustained_high_load(session, duration, rps)

    async def scenario_burst_chaos(self, session, bursts=10):
        print(f"  💥 BURST CHAOS: {bursts} random bursts")
        for b in range(bursts):
            count = random.randint(100, 400)
            print(f"    Burst {b + 1}: {count} requests")
            tasks = [
                self.send_request(session, random.choice(self.PROMPTS), 100)
                for _ in range(count)
            ]
            results = await asyncio.gather(*tasks)
            for r in results:
                self.results.append(r)
            await asyncio.sleep(random.uniform(1, 3))

    async def scenario_continuous_flood(self, session, duration=30):
        print(f"  🌊 CONTINUOUS FLOOD: {duration}s max throughput")
        print("    Using aggressive parallel requests...")

        start = time.time()
        batch_size = 100
        total_sent = 0

        while time.time() - start < duration:
            tasks = [
                self.send_request(session, random.choice(self.PROMPTS), 80)
                for _ in range(batch_size)
            ]
            results = await asyncio.gather(*tasks)
            for r in results:
                self.results.append(r)
            total_sent += len(results)

            elapsed = time.time() - start
            current_rps = total_sent / elapsed if elapsed > 0 else 0
            print(
                f"\r    ⏱️ {elapsed:.0f}s | {total_sent} req | {current_rps:.1f} req/s     ",
                end="",
                flush=True,
            )

        print()

    async def scenario_mixed_tokens(self, session):
        print("  🎲 MIXED TOKENS: Various token sizes")
        configs = [
            (10, 50, 100),  # (count, min_tokens, max_tokens)
            (50, 100, 200),
            (100, 50, 150),
            (30, 200, 300),
            (20, 300, 500),
        ]

        total = 0
        for count, min_t, max_t in configs:
            print(f"    {count} requests, tokens {min_t}-{max_t}")
            tasks = [
                self.send_request(
                    session, random.choice(self.PROMPTS), random.randint(min_t, max_t)
                )
                for _ in range(count)
            ]
            results = await asyncio.gather(*tasks)
            for r in results:
                self.results.append(r)
            total += len(results)
            await asyncio.sleep(0.5)

        print(f"    Total: {total} requests")

    def print_header(self):
        elapsed = time.time() - self.start_time
        print("\n" + "=" * 70)
        print("  🔥 EXTREME LOAD SIMULATOR - 200+ req/s")
        print("=" * 70)
        print(
            f"  Started: {datetime.fromtimestamp(self.start_time).strftime('%H:%M:%S')}"
        )
        print(f"  Running: {elapsed:.0f}s")
        print("  Press Ctrl+C to stop")
        print("=" * 70)

    def print_stats(self):
        total = len(self.results)
        if total == 0:
            return

        elapsed = time.time() - self.start_time
        success = sum(1 for r in self.results if r["success"])
        failed = total - success

        workers = defaultdict(int)
        latencies = []
        for r in self.results:
            workers[r["worker"]] += 1
            latencies.append(r["latency"])

        print("\n" + "-" * 70)
        print(f"  📊 STATS (Total: {total} req | {total / elapsed:.1f} req/s)")
        print("-" * 70)
        print(f"  ✅ Success: {success} ({success / total * 100:.1f}%)")
        print(f"  ❌ Failed: {failed} ({failed / total * 100:.1f}%)")
        print(
            f"  ⏱️  Avg: {sum(latencies) / len(latencies):.2f}s | Min: {min(latencies):.2f}s | Max: {max(latencies):.2f}s"
        )
        print(f"  📦 Workers: {dict(sorted(workers.items(), key=lambda x: -x[1])[:5])}")
        print(f"  🔢 Scenarios: {self.scenario_count}")
        print("-" * 70)

    async def run(self):
        self.print_header()

        async with aiohttp.ClientSession() as session:
            print("\n⏳ Connecting to RabbitMQ...")
            await self.setup_rabbitmq()

            print("⏳ Waiting for orchestrator...")
            for _ in range(15):
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
            else:
                print("⚠️ Orchestrator not ready, continuing anyway...")

            scenarios = [
                (
                    "SUSTAINED_200",
                    lambda s: self.scenario_sustained_high_load(s, 15, 200),
                ),
                ("SPIKE_500", lambda s: self.scenario_spike(s, 500)),
                ("VARIABLE", lambda s: self.scenario_variable_load(s, 4)),
                ("FLOOD_30s", lambda s: self.scenario_continuous_flood(s, 30)),
                ("BURST_CHAOS", lambda s: self.scenario_burst_chaos(s, 8)),
                (
                    "SUSTAINED_150",
                    lambda s: self.scenario_sustained_high_load(s, 20, 150),
                ),
                ("MIXED_TOKENS", lambda s: self.scenario_mixed_tokens(s)),
                ("SPIKE_300", lambda s: self.scenario_spike(s, 300)),
            ]

            iteration = 0
            while True:
                iteration += 1
                scenario_name, scenario_func = random.choice(scenarios)

                print(f"\n{'=' * 70}")
                print(f"  🔄 ITERATION #{iteration} | Scenario: {scenario_name}")
                print(f"  ⏰ {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 70)

                self.scenario_count += 1

                try:
                    await scenario_func(session)
                except Exception as e:
                    print(f"  ⚠️ Error: {e}")

                if iteration % 3 == 0:
                    self.print_stats()

                wait_time = random.uniform(2, 5)
                print(f"\n  💤 Pause: {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

    async def cleanup(self):
        if self.connection:
            await self.connection.close()


async def main():
    simulator = ExtremeLoadSimulator()
    try:
        await simulator.run()
    except KeyboardInterrupt:
        print("\n\n🛑 Simulation arrêtée")
        simulator.print_stats()
    finally:
        await simulator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
