# Phase-1 Project Report

**File:** [`tr1nity_report.pdf`](tr1nity_report.pdf)
**Authors:** Hamza, Irtaza, Hammad
**Course:** Network Security · Spring 2026 · Air University, Islamabad

This is the academic-style Phase-1 documentation for TR1NITY. It mirrors the structure of a typical project-defense report:

- Cover page + working clickable Table of Contents
- Abstract
- Introduction (background, importance, problem statement, proposed solution)
- Literature Review with comparative analysis table and critical gap analysis
- Methodology (component design + end-to-end workflow + architecture diagram)
- Use Case Diagram + 10 detailed use case descriptions
- Test Cases (12 planned cases mapped to the six modules)
- Market Value (target users, market relevance, economic positioning, competitor comparison)
- Gantt Chart (16-week / 6-phase timeline with milestone tags)
- Results & Conclusion
- IEEE-style References (15 academic + industry sources)
- Appendices (module listing, free-tier API summary, system requirements, GitHub storage strategy)

## Rebuilding the PDF

```bash
# Requires: TeX Live (xelatex / pdflatex), biber, graphviz, python3 + matplotlib
cd docs/report

# (re)generate the diagrams
( cd figures && dot -Tpdf architecture.dot -o architecture.pdf )
( cd figures && dot -Tpdf usecase.dot -o usecase.pdf )
( cd figures && python3 gantt.py )

# compile the LaTeX
pdflatex -interaction=nonstopmode tr1nity_report.tex
biber tr1nity_report
pdflatex -interaction=nonstopmode tr1nity_report.tex
pdflatex -interaction=nonstopmode tr1nity_report.tex
```

## Source files

| File | Purpose |
|------|---------|
| `tr1nity_report.tex` | Main LaTeX source (~1200 lines) |
| `references.bib` | IEEE bibliography, 15 entries |
| `figures/architecture.dot` | Graphviz source for the system architecture diagram |
| `figures/usecase.dot` | Graphviz source for the use case diagram |
| `figures/gantt.py` | matplotlib script for the 16-week Gantt chart |
| `figures/*.pdf`, `*.png` | Pre-rendered diagrams (in case you don't have graphviz / matplotlib locally) |

The compiled `tr1nity_report.pdf` is the authoritative deliverable for Phase 1 of the course.
