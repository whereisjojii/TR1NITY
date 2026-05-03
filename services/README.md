# TR1NITY services

Each subfolder is an independently-deployable FastAPI service:

| Service | Port | Phase | Purpose |
|---------|------|-------|---------|
| [`ingestor`](ingestor/) | 8001 | 1 | Webhook + syslog + ModSecurity → ECS → OpenSearch |
| [`correlator`](correlator/) | 8002 | 2 | Temporal grouping, ATT&CK tagging, threat-intel, SIGMA |
| [`ai-assist`](ai-assist/) | 8003 | 5 | Foundation-Sec-8B + RAG; async drafting |
| [`api`](api/) | 8000 | 3 | REST + WebSocket; serves the static React build |

All four services are scaffolded as FastAPI hello-worlds in Phase 0 (`v0.1.0-foundation`). The actual implementation arrives phase by phase per [`../ROADMAP.md`](../ROADMAP.md).
