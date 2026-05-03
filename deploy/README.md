# `deploy/` — Docker Compose & Kubernetes manifests

Docker Compose is the primary deployment target for v1.0. Kubernetes manifests are a v2.0 stretch goal.

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Default: full SIEM core stack |
| `docker-compose.gpu.yml` | Override: enables Vulkan GPU passthrough for `ai-assist` (Phase 5) |
| `docker-compose.dev.yml` | Override: bind-mounts service source for hot reload |

Use:

```bash
docker compose -f deploy/docker-compose.yml up -d
# or, with GPU + dev overrides:
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.gpu.yml -f deploy/docker-compose.dev.yml up -d
```
