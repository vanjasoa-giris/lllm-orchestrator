import pytest
import asyncio
import httpx
import subprocess
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


WORKERS_PORTS = [8001, 8002, 8003]
ORCHESTRATOR_PORT = 8000


@pytest.fixture(scope="module")
def start_services():
    processes = []

    for i, port in enumerate(WORKERS_PORTS):
        proc = subprocess.Popen(
            [
                sys.executable,
                "../worker/main.py",
                "--port",
                str(port),
                "--id",
                f"M{i + 1}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        processes.append(proc)

    time.sleep(3)

    orch_proc = subprocess.Popen(
        [sys.executable, "../orchestrator/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    processes.append(orch_proc)

    time.sleep(3)

    yield

    for proc in processes:
        proc.terminate()
        proc.wait()


def test_workers_health(start_services):
    for port in WORKERS_PORTS:
        response = httpx.get(f"http://localhost:{port}/health", timeout=5.0)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_orchestrator_health(start_services):
    response = httpx.get(f"http://localhost:{ORCHESTRATOR_PORT}/health", timeout=5.0)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_load_balancing_distribution(start_services):
    responses = []
    for _ in range(20):
        response = httpx.post(
            f"http://localhost:{ORCHESTRATOR_PORT}/infer",
            json={"prompt": "test", "max_tokens": 10},
            timeout=30.0,
        )
        if response.status_code == 200:
            responses.append(response.json().get("worker"))

    worker_counts = {f"M{i + 1}": responses.count(f"M{i + 1}") for i in range(3)}
    print(f"Worker distribution: {worker_counts}")

    assert len(responses) > 0


def test_worker_metrics(start_services):
    response = httpx.get(f"http://localhost:{WORKERS_PORTS[0]}/metrics", timeout=5.0)
    assert response.status_code == 200
    data = response.json()
    assert "requests_total" in data
    assert "avg_latency" in data


def test_orchestrator_stats(start_services):
    response = httpx.get(f"http://localhost:{ORCHESTRATOR_PORT}/stats", timeout=5.0)
    assert response.status_code == 200
    data = response.json()
    assert "workers" in data
    assert "queue_size" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
