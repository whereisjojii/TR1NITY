# `correlator` service — Phase 2 (The Brain)

Reads ECS events produced by the ingestor, groups them into incidents
by source IP within a sliding time window, runs a small bundled SIGMA
rule pack to promote MITRE ATT&CK techniques and severity, enriches
with file-based threat-intel, and writes incidents to
`tr1nity-incidents-YYYY.MM.dd` in OpenSearch.

See [`docs/modules/correlation.md`](../../docs/modules/correlation.md)
for the full design.

## Run

```bash
# from the repo root
docker compose -f deploy/docker-compose.yml up correlator
```

## Test

```bash
cd services/correlator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

## HTTP API

| Method | Path           | Purpose                                                     |
| ------ | -------------- | ----------------------------------------------------------- |
| GET    | `/`            | Service banner                                              |
| GET    | `/healthz`     | Liveness probe                                              |
| GET    | `/readyz`      | Readiness probe                                             |
| POST   | `/correlate`   | Run one pipeline tick; returns incidents and per-sink stats |
| GET    | `/incidents`   | List incidents from the most recent tick                    |
| POST   | `/ingest-test` | Push events into the in-memory consumer (DRY_RUN only)      |
