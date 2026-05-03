"""TR1NITY ingestor service — Phase 1.

Entry point. Wires routers, configures logging, and exposes the FastAPI
``app`` instance that ``uvicorn`` boots.

Endpoints:

* ``GET  /``            — service banner
* ``GET  /healthz``     — liveness probe
* ``GET  /readyz``      — readiness probe (also probes the sink)
* ``POST /ingest/wazuh``  — Wazuh integrator/webhook payload
* ``POST /ingest/syslog`` — Firewall (iptables/pfSense/OPNsense) syslog batch
* ``POST /ingest/waf``    — ModSecurity / WAF audit JSON

Phase-2 deliverables (correlation, MITRE ATT&CK tagging, threat-intel
enrichment) consume the documents this service writes to OpenSearch.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from . import __version__
from .routers import firewall, health, waf, wazuh

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

app = FastAPI(
    title="TR1NITY · Ingestor",
    version=__version__,
    description=(
        "Receives Wazuh webhooks, firewall syslog, and ModSecurity / WAF "
        "audit logs; normalizes everything to ECS; writes to OpenSearch "
        "indices ``tr1nity-events-YYYY.MM.dd``."
    ),
)

app.include_router(health.router)
app.include_router(wazuh.router)
app.include_router(firewall.router)
app.include_router(waf.router)
