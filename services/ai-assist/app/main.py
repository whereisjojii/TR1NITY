"""TR1NITY ai-assist service — Phase 0 hello-world.

Module 3 (AI Assist, HITL). Phase-5 deliverables (Foundation-Sec-8B Q4
via llama.cpp + Vulkan, ChromaDB-grounded RAG, async drafting endpoints
for post-incident reports / runbooks / CVE explanations / weekly
compliance summaries) land in a later session under tag ``v0.6.0-ai``.

The service starts in **mock mode** (``MOCK_LLM=true`` in .env). In mock
mode the drafting endpoints return deterministic templated responses,
which is the supported configuration for users without a Vulkan-capable
GPU.
"""

from __future__ import annotations

import os
import platform
import socket
import time
from datetime import UTC, datetime

from fastapi import FastAPI

from . import __version__

SERVICE_NAME = "ai-assist"
START_TIME = time.monotonic()

MOCK_LLM = os.environ.get("MOCK_LLM", "true").lower() in {"1", "true", "yes"}

app = FastAPI(
    title="TR1NITY · AI Assist",
    version=__version__,
    description=(
        "Async drafting service for post-incident reports, runbooks, and "
        "compliance summaries. Foundation-Sec-8B Q4 via llama.cpp + "
        "Vulkan in production; deterministic templated responses in "
        "MOCK_LLM mode (default). Phase 0 hello-world only."
    ),
)


@app.get("/", summary="Service banner", tags=["meta"])
def root() -> dict[str, object]:
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "phase": "0 — Foundation",
        "mock_llm": MOCK_LLM,
        "docs": "/docs",
        "healthz": "/healthz",
    }


@app.get("/healthz", summary="Liveness probe", tags=["health"])
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": __version__,
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "uptime_seconds": round(time.monotonic() - START_TIME, 3),
        "now": datetime.now(UTC).isoformat(),
        "env": os.environ.get("TR1NITY_ENV", "dev"),
        "mock_llm": MOCK_LLM,
    }


@app.get("/readyz", summary="Readiness probe", tags=["health"])
def readyz() -> dict[str, str]:
    return {"status": "ready", "service": SERVICE_NAME}


@app.get("/llm/info", summary="LLM backend info", tags=["llm"])
def llm_info() -> dict[str, object]:
    """Phase-0 stub. Real LLM info arrives in Phase 5."""
    if MOCK_LLM:
        return {
            "mode": "mock",
            "backend": "deterministic-template",
            "model": None,
            "context_size": None,
            "note": (
                "MOCK_LLM=true. No GPU/CPU LLM is loaded; drafting "
                "endpoints will return templated responses in Phase 5."
            ),
        }
    return {
        "mode": "live",
        "backend": os.environ.get("LLM_BACKEND", "vulkan"),
        "model": os.environ.get(
            "LLM_MODEL_PATH",
            "/models/foundation-sec-8b-instruct.Q4_K_M.gguf",
        ),
        "context_size": int(os.environ.get("LLM_CTX_SIZE", "8192")),
        "note": "Real backend wiring lands in Phase 5 (v0.6.0-ai).",
    }
