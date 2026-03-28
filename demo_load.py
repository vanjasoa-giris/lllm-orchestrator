#!/usr/bin/env python3
"""
Demo script to showcase the LLM Load Balancer visualization.
Generates realistic traffic patterns to showcase different scenarios.
"""
import asyncio
import httpx
import random
import time
from typing import List

ORCHESTRATOR_URL = "http://localhost:8000"

class LoadGenerator:
    def __init__(self, num_workers: int = 5):
        self.num_workers = num_workers
        self.total_requests = 0
        self.successful = 0
        self.queued = 0

    async def generate_request(self, prompt: str = "test prompt", tokens: int = 50):
        """Generate a single inference request"""
        payload = {
            "prompt": prompt,
            "max_tokens": tokens,
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                start = time.time()
                response = await client.post(
                    f"{ORCHESTRATOR_URL}/infer",
                    json=payload
                )
                duration = time.time() - start
                
                self.total_requests += 1
                data = response.json()
                
                if data.get("status") == "queued":
                    self.queued += 1
                    status = "📦 QUEUED"
                else:
                    self.successful += 1
                    status = f"✓ {data.get('worker')} ({duration*1000:.0f}ms)"
                
                return status, duration
        except Exception as e:
            self.total_requests += 1
            return f"✗ ERROR: {str(e)[:30]}", 0

    async def spike_load(self, num_requests: int = 10, concurrent: bool = True):
        """Send a spike of requests"""
        print(f"\n⚡ Generating {num_requests} requests ({'concurrent' if concurrent else 'sequential'})...")
        
        if concurrent:
            tasks = [self.generate_request() for _ in range(num_requests)]
            results = await asyncio.gather(*tasks)
        else:
            results = []
            for _ in range(num_requests):
                result = await self.generate_request()
                results.append(result)
                await asyncio.sleep(0.1)
        
        for i, (status, _) in enumerate(results, 1):
            print(f"  [{i:2d}] {status}")

    async def steady_load(self, duration_seconds: int = 30, rate_per_sec: int = 2):
        """Send steady load for given duration"""
        print(f"\n📊 Steady load for {duration_seconds}s ({rate_per_sec} req/s)...")
        interval = 1.0 / rate_per_sec
        start = time.time()
        
        while time.time() - start < duration_seconds:
            result = await self.generate_request()
            elapsed = time.time() - start
            print(f"  [{elapsed:5.1f}s] {result[0]}")
            await asyncio.sleep(interval)

    async def variable_load(self, duration_seconds: int = 30):
        """Send variable load (spikes and quiet periods)"""
        print(f"\n🌊 Variable load for {duration_seconds}s...")
        start = time.time()
        
        while time.time() - start < duration_seconds:
            elapsed = time.time() - start
            
            # Pattern: quiet -> spike -> quiet -> spike
            phase = int(elapsed / 5) % 2
            
            if phase == 0:
                # Quiet period
                await asyncio.sleep(random.uniform(0.5, 2))
            else:
                # Spike period - send 5-10 concurrent requests
                num_spike = random.randint(5, 10)
                tasks = [self.generate_request() for _ in range(num_spike)]
                results = await asyncio.gather(*tasks)
                for i, (status, _) in enumerate(results):
                    print(f"  [{elapsed:5.1f}s] {status}")
                await asyncio.sleep(0.5)

    def print_stats(self):
        """Print final statistics"""
        print("\n" + "="*70)
        print("📊 LOAD TEST STATISTICS")
        print("="*70)
        print(f"Total Requests:     {self.total_requests}")
        print(f"Successful:         {self.successful} ({self.successful*100//max(1,self.total_requests)}%)")
        print(f"Queued:             {self.queued}")
        print(f"Success Rate:       {self.successful*100//max(1,self.total_requests)}%")
        print("="*70)


async def main():
    print("\n" + "="*70)
    print("🚀 LLM LOAD BALANCER - DEMO")
    print("="*70)
    print("\nAccess the dashboard at: http://localhost:8000")
    print("Grafana at:             http://localhost:3000 (admin/admin)")
    print("\n" + "="*70)

    gen = LoadGenerator()

    try:
        # Scenario 1: Simple requests
        print("\n[SCENARIO 1] Simple Sequential Requests")
        await gen.spike_load(num_requests=3, concurrent=False)
        await asyncio.sleep(2)

        # Scenario 2: Concurrent spike
        print("\n[SCENARIO 2] Concurrent Spike (test load balancing)")
        await gen.spike_load(num_requests=15, concurrent=True)
        await asyncio.sleep(3)

        # Scenario 3: Steady load
        print("\n[SCENARIO 3] Steady Load (monitor distribution)")
        await gen.steady_load(duration_seconds=20, rate_per_sec=3)
        await asyncio.sleep(2)

        # Scenario 4: Variable load
        print("\n[SCENARIO 4] Variable Load (realistic traffic)")
        await gen.variable_load(duration_seconds=30)

    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        gen.print_stats()
        print("\n✅ Demo complete! Check the dashboard for visualization.")
        print("\nPrometheus scrape config: config/prometheus.yml")
        print("Grafana dashboards: config/grafana/provisioning/dashboards/")


if __name__ == "__main__":
    asyncio.run(main())
