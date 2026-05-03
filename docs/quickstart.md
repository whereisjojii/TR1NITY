# Quickstart

## Prerequisites

- **OS:** Ubuntu 22.04 LTS / Debian 12 / Fedora 40+ (or any Linux with Docker)
- **Docker Engine** 24+ and **Docker Compose** plugin v2.20+
- **RAM:** 16 GB recommended (8 GB works in `MOCK_LLM=true` mode)
- **Disk:** 100 GB SSD minimum

## Boot the stack (Phase 0)

```bash
git clone https://github.com/whereisjojii/TR1NITY.git
cd TR1NITY

cp .env.example .env       # tweak values; defaults work for local dev
make pull                  # warm-cache upstream images
make up                    # boot the full Docker Compose stack
make ps                    # see what's running
```

Once everything is healthy:

```bash
curl http://localhost:8000/healthz   # api gateway
curl http://localhost:8001/healthz   # ingestor
curl http://localhost:8002/healthz   # correlator
curl http://localhost:8003/healthz   # ai-assist
```

You should see four `{"status":"ok",...}` responses.

## Run the synthetic demo (Phase 1)

```bash
make demo                  # generates Wazuh + firewall + WAF events for the same source IP
```

This will be wired up in Phase 1. Until then, it is a placeholder.

## Stop the stack

```bash
make down                  # stop containers (volumes preserved)
make clean                 # ALSO delete volumes (destructive)
```

## What's where

| Path                        | Purpose                                               |
| --------------------------- | ----------------------------------------------------- |
| `services/<name>/`          | One FastAPI service per module                        |
| `deploy/docker-compose.yml` | The Phase-0 stack definition                          |
| `Makefile`                  | All operator commands (`make help` for the full list) |
| `docs/`                     | This documentation site (MkDocs Material)             |

## Next steps

- Read the [Architecture overview](architecture.md).
- Browse the [Roadmap](roadmap.md).
- Pick a [module](modules/index.md) and contribute.
