# Nima Report Engine

A deterministic A4 report compiler for finished, human-facing PDFs. The AI supplies structured content. The engine owns layout, typography, themes, charts, tables, headers/footers, fit rules, and page-level rendering.

## Core contract
- One variable report system, not separate SEO/proposal/server templates.
- Modern Digital visual system with blue/green/purple/orange/red/graphite themes.
- True page artifacts: every page is rendered independently and SHA-256 hashed before merge.
- Surgical corrections: rebuild one page with `--only page-id`; unrelated page artifacts remain byte-identical.
- Persian RTL with mixed English/numbers/URLs.
- Final-output-only safety: no TODO/draft/internal/debug/placeholder content.
- Missing evidence assets and overflow are hard build failures.
- Nima Moheb identity and clickable resume support.
- No GitHub Actions required for routine report generation.

## Setup
```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python scripts/bootstrap_fonts.py   # recommended for exact typography
```

## Build
```bash
python build.py examples/client_report.json output/report.pdf
```

Surgical repair:
```bash
python build.py examples/client_report.json output/report.pdf --only trend
```

## Test
```bash
python -m unittest discover -s tests -v
```

See `AI_USAGE.md`, `docs/DESIGN_SYSTEM.md`, `docs/COMPONENTS.md`, and `docs/ARCHITECTURE.md` before generating reports.
