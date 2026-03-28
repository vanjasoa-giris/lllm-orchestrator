#!/usr/bin/env python3
import os
import sys
import argparse
from worker.main_llm import LLMWorker

if __name__ == "__main__":
    worker_id = os.environ.get("WORKER_ID", "M1")
    worker_port = int(os.environ.get("WORKER_PORT", 8001))
    backend = os.environ.get("BACKEND", "simulated")
    model_name = os.environ.get("MODEL_NAME", None)
    
    worker = LLMWorker(worker_id, worker_port, backend, model_name)
    worker.run()
