#!/usr/bin/env python3
"""
Test API Client - Sans dépendances externes
Utilise uniquement la bibliothèque standard Python
"""

import json
import urllib.request
import urllib.error
import time


BASE_URL = "http://localhost:8000"


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode()), response.status
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}, e.code
    except Exception as e:
        return {"error": str(e)}, 500


def post(url, data):
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode()), response.status
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}, e.code
    except Exception as e:
        return {"error": str(e)}, 500


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_health():
    print_header("TEST: Health Check")
    result, status = get(f"{BASE_URL}/health")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return status == 200


def test_stats():
    print_header("TEST: Statistics")
    result, status = get(f"{BASE_URL}/stats")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return status == 200


def test_inference():
    print_header("TEST: Inference")
    payload = {
        "prompt": "Explique moi ce qu'est un load balancer en 2 phrases.",
        "max_tokens": 100,
        "temperature": 0.7,
    }
    print(f"Payload: {json.dumps(payload, indent=2)}")
    result, status = post(f"{BASE_URL}/infer", payload)
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return status == 200


def test_queue():
    print_header("TEST: Queue (simuler surcharge)")
    print("Envoi de 5 requetes simultanees...")
    results = []
    for i in range(5):
        payload = {
            "prompt": f"Requete {i + 1}: Quel est le capital de la France?",
            "max_tokens": 50,
            "priority": 1,
        }
        result, status = post(f"{BASE_URL}/infer", payload)
        results.append((status, result))
        print(f"  Requete {i + 1}: Status={status}")
        time.sleep(0.5)
    return True


def test_dead_letter():
    print_header("TEST: Dead Letter Queue")
    result, status = get(f"{BASE_URL}/dead-letter")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return status == 200


def test_metrics():
    print_header("TEST: Prometheus Metrics")
    result, status = get(f"{BASE_URL}/metrics")
    print(f"Status: {status}")
    if isinstance(result, dict) and "error" not in result:
        lines = str(result).split("\n")[:20]
        print("\n".join(lines))
    else:
        print(f"Response: {result}")
    return status == 200


def test_worker_health():
    print_header("TEST: Worker Health Checks")
    for port in [8001, 8002, 8003]:
        result, status = get(f"http://localhost:{port}/health")
        worker_id = result.get("worker_id", f"M{port - 8000}")
        print(f"  Worker {worker_id} (port {port}): {result.get('status', 'unknown')}")
    return True


def run_all_tests():
    print("\n" + "=" * 60)
    print("  LLM LOAD BALANCER - API TESTS")
    print("=" * 60)

    tests = [
        ("Health Check", test_health),
        ("Worker Health", test_worker_health),
        ("Stats", test_stats),
        ("Inference", test_inference),
        ("Queue Stress", test_queue),
        ("Dead Letter", test_dead_letter),
        ("Metrics", test_metrics),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, False))

    print_header("SUMMARY")
    all_passed = True
    for name, success in results:
        status = "PASS" if success else "FAIL"
        symbol = "[OK]" if success else "[X]"
        print(f"  {symbol} {name}: {status}")
        if not success:
            all_passed = False

    print("\n" + "-" * 60)
    if all_passed:
        print("  Tous les tests ont PASSES!")
    else:
        print("  Certains tests ont ECHOUE.")
    print("-" * 60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
        if test_name == "health":
            test_health()
        elif test_name == "stats":
            test_stats()
        elif test_name == "infer":
            test_inference()
        elif test_name == "queue":
            test_queue()
        elif test_name == "deadletter":
            test_dead_letter()
        elif test_name == "metrics":
            test_metrics()
        elif test_name == "workers":
            test_worker_health()
        else:
            print(f"Test inconnu: {test_name}")
            print(
                "Tests disponibles: health, stats, infer, queue, deadletter, metrics, workers"
            )
    else:
        run_all_tests()
