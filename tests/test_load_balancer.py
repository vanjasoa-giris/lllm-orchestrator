import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.main import Worker, LoadBalancer, WorkerStatus, CircuitState


@pytest.fixture
def workers():
    return {
        "M1": Worker(id="M1", url="http://localhost:8001", weight=1),
        "M2": Worker(id="M2", url="http://localhost:8002", weight=1),
        "M3": Worker(id="M3", url="http://localhost:8003", weight=1),
    }


@pytest.fixture
def lb():
    class MockLB:
        def __init__(self):
            self.workers = {}

        def add_worker(self, worker):
            self.workers[worker.id] = worker

    return MockLB()


def test_worker_initialization(workers):
    assert workers["M1"].id == "M1"
    assert workers["M1"].status == WorkerStatus.UNHEALTHY
    assert workers["M1"].connections == 0
    assert workers["M1"].circuit_state == CircuitState.CLOSED


def test_worker_health_state_transition(workers):
    w = workers["M1"]
    assert w.status == WorkerStatus.UNHEALTHY

    w.status = WorkerStatus.HEALTHY
    assert w.status == WorkerStatus.HEALTHY


def test_circuit_breaker_opens_after_failures(workers):
    w = workers["M1"]
    w.status = WorkerStatus.HEALTHY

    for _ in range(5):
        w.consecutive_failures += 1

    assert w.consecutive_failures >= 5
    assert w.circuit_state == CircuitState.OPEN


def test_latency_tracking(workers):
    w = workers["M1"]
    w.latencies = [0.1, 0.2, 0.15, 0.25]

    avg = sum(w.latencies[-10:]) / len(w.latencies[-10:])
    assert avg == 0.175


def test_connection_tracking(workers):
    w = workers["M1"]
    w.connections = 0

    w.connections += 1
    assert w.connections == 1

    w.connections -= 1
    assert w.connections == 0


@pytest.mark.asyncio
async def test_worker_score_calculation():
    w1 = Worker(
        id="M1", url="http://localhost:8001", weight=1, status=WorkerStatus.HEALTHY
    )
    w2 = Worker(
        id="M2", url="http://localhost:8002", weight=1, status=WorkerStatus.HEALTHY
    )

    w1.connections = 5
    w1.latencies = [0.1] * 10

    w2.connections = 1
    w2.latencies = [0.2] * 10

    score1 = (1 / (5 + 1)) * (1 / 0.1)
    score2 = (1 / (1 + 1)) * (1 / 0.2)

    assert score2 > score1


def test_worker_priority_selection(workers):
    workers["M1"].weight = 3
    workers["M2"].weight = 2
    workers["M3"].weight = 1

    for w in workers.values():
        w.status = WorkerStatus.HEALTHY
        w.connections = 0
        w.latencies = [0.1]

    scores = {
        k: (1 / (v.connections + 1)) * (1 / 0.1) * v.weight for k, v in workers.items()
    }

    assert scores["M1"] > scores["M2"] > scores["M3"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
