# `ui/` — TR1NITY Cockpit

The analyst workstation. **Phase 3 deliverable** — see [`../ROADMAP.md`](../ROADMAP.md).

Tech: React 18 + Vite + TypeScript + Tailwind + shadcn/ui + TanStack Query + WebSocket.

The static build is served by the `api` service in production. In dev:

```bash
cd ui
pnpm install
pnpm dev   # http://localhost:5173 with HMR
```
