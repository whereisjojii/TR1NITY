# M3 · AI Assist (HITL)

**Phase:** 5 · **Tag:** `v0.6.0-ai` · **Service:** [`services/ai-assist/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/ai-assist)

## Goal

Generate the **boring documents an analyst doesn't want to write** — post-incident reports, runbook drafts, CVE explanations, weekly compliance summaries — without ever putting an LLM in the real-time triage path.

## Why HITL, not autonomous

Real analyst feedback (and the empirical findings cited in the [Phase-1 report](../report.md)) is consistent: AI is *useful* on async drafting tasks and *unreliable* on real-time triage. TR1NITY hard-codes that boundary:

- The LLM **never** decides whether something is a true positive.
- The LLM **never** auto-closes a case.
- The LLM **always** drafts; the analyst always reviews and edits.

## Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Model | Foundation-Sec-8B-Instruct (Apache 2.0) | Security-specialized, ≈70B-class quality, 8B params |
| Quantization | Q4_K_M GGUF (~5 GB) | Fits in 8 GB VRAM with headroom |
| Runtime | `llama.cpp` | Mature, fast, CPU/GPU/Vulkan flexibility |
| Backend on RX 590 | Vulkan | ROCm dropped Polaris; Vulkan works fine |
| RAG | ChromaDB (in-process) | No extra server, persistent on disk |

## Drafting endpoints (Phase 5)

| Endpoint | Drafts |
|----------|--------|
| `POST /draft/incident-report` | Markdown post-mortem grounded by the closed case |
| `POST /draft/runbook` | Runbook for a specific ATT&CK technique |
| `POST /draft/cve-explanation` | Plain-English CVE summary using NVD context |
| `POST /draft/weekly-compliance` | Weekly compliance summary (PCI-DSS / ISO 27001 / NIST CSF) |

All drafts are queued asynchronously; the UI shows a "Draft ready" badge when complete.

## Mock LLM mode

For users without a Vulkan-capable GPU (or who don't want to wait on `ollama pull`), the service supports `MOCK_LLM=true`. In that mode every drafting endpoint returns a deterministic templated response. The full UI flow is identical so the platform is fully demoable without a GPU.

## Phase 0 status

The `ai-assist` service is currently a hello-world. It exposes `/healthz`, `/readyz`, `/llm/info`, and a Swagger UI. `MOCK_LLM` defaults to `true`. Real LLM wiring (Vulkan build of `llama.cpp`, GGUF loader, ChromaDB ingestion, four drafting endpoints) arrives in Phase 5.
