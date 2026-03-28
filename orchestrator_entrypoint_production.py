#!/usr/bin/env python3
"""
LLM Load Balancer - Production Entry Point
==========================================
Orchestrateur production-ready avec :
- Load balancing token-aware
- Health checks périodiques
- Circuit breaker 3 états
- Priority queue avec heap
- Auto-retry avec exponential backoff
- Dead letter queue
- Rate limiting
- Graceful shutdown
- Distributed tracing (request IDs)
"""

import os
import sys

if os.path.dirname(__file__):
    sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from orchestrator.main_production_final import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
    )
