<!-- Thanks for contributing to TR1NITY. Keep this short, honest, and informative. -->

## What

<!-- One-paragraph description of the change. -->

## Why

<!-- The user-visible / analyst-visible problem this solves. Link the related issue / phase / module. -->

Closes #

## How

<!-- Bullet list of the technical approach (the *delta*, not the entire architecture). -->

-
-
-

## How tested

<!-- Required. Describe the manual or automated test you actually ran. "Looks good locally" is not enough. -->

- [ ] `make test` passes
- [ ] `make lint` passes
- [ ] `docker compose up` boots cleanly
- [ ] (UI changes) Tested in Chrome and Firefox at 1920×1080 and 1366×768

## Risk / rollback

<!-- What breaks if this PR is buggy? How does an operator roll back? -->

## Phase / Module

<!-- Tick the boxes that apply. -->

- [ ] Phase 0 — Foundation
- [ ] Phase 1 — Multi-source Ingestion (M1)
- [ ] Phase 2 — The Brain (M2)
- [ ] Phase 3 — The Cockpit (M5)
- [ ] Phase 4 — FP Loop & Runbooks (M4)
- [ ] Phase 5 — AI Assist (M3)
- [ ] Phase 6 — Polish, Reporting (M6)
- [ ] Cross-cutting / docs only

## Checklist

- [ ] No paid APIs introduced
- [ ] No file > 10 MB committed
- [ ] No datasets / model weights / Docker volumes committed
- [ ] Pre-commit hooks pass locally
- [ ] CI is green
