# Nima Report Engine

A deterministic A4 report compiler for finished human-facing PDFs. The AI supplies semantic content; the engine owns composition, typography, themes, bidi behavior, charts/tables, fit rules and rendered QA.

## v0.5 guarantees

- Strict archetype-specific schema; no arbitrary layout coordinates.
- No silent truncation: content wraps or fails with `FIT_FAIL`.
- No visually empty normal pages: rendered QA measures actual content-body composition and fails with `SPARSE_PAGE_FAIL` when an archetype is materially underused.
- Decorative grids/backgrounds do not count as content density.
- Exact production fonts: IBM Plex Sans + Vazirmatn. Missing approved fonts fail with `FONT_SETUP_FAIL`; the engine no longer silently emits Persian reports with Noto/DejaVu fallbacks.
- Persian copied-text normalization removes control-character artifacts while preserving ZWNJ.
- RTL mirroring covers navigation/title markers, footer identity, card/column ordering, tables and timelines.
- English prose supports measured justification and wrap orphan control.
- Summary values cannot be empty; fake/blank metric cards are rejected.
- `cards.layout:auto` provides deterministic composition variation for long reports.
- Multi-row tables and timeline layouts use the A4 body more deliberately while preserving fit checks.
- Clean builds are byte-reproducible; safe `--only` rebuilds fingerprint global/page/evidence state.
- Final PDFs are reopened and rendered to PNG by PyMuPDF for output-boundary QA.
- Normal pages contain no resume button; closing pages make the visible resume URL itself clickable.
- No GitHub Actions are needed for routine generation/verification.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python scripts/bootstrap_fonts.py
```

Font bootstrap uses pinned upstream revisions and writes to `~/.cache/nima-report-engine/fonts` by default. `REPORTKIT_FONT_DIR` may point to an approved-font directory. Do not bypass `FONT_SETUP_FAIL` with an arbitrary Persian fallback.

## Build

```bash
python build.py examples/client_report.json output/report.pdf
```

Successful output includes `report.pdf`, independent `pages/*.pdf`, `manifest.json`, rendered `qa/page-*.png`, and `qa/qa_manifest.json`.

Surgical repair:

```bash
python build.py examples/client_report.json output/report.pdf --only trend
```

## Test

```bash
python -m unittest discover -s tests -v
```

Real-case layout regressions are kept in `examples/regression_crm_en.json` and `examples/regression_crm_fa.json`. Cover regressions remain in `examples/cover_showcase_en.json` and `examples/cover_showcase_fa.json`.

## Cover system

Five permanent production variants: `signal-orbit`, `glass-panel`, `aurora-strata`, `constellation`, `editorial-split`. All use the same production renderer in LTR/RTL. The report-generating chat chooses cover + palette from content/audience rather than defaulting mechanically.

For Persian covers, Nima's author identity is `نیما محب`. Mixed trailing acronyms such as `CRM` are rendered in a controlled Latin badge when necessary to protect the Persian title composition.

## Default ChatGPT workflow

This repo is Nima's default PDF-report pipeline. Structure the source material as semantic report JSON, choose varied archetypes appropriate to the content, build with QA enabled, resolve any `FIT_FAIL`/`SPARSE_PAGE_FAIL`/`FONT_SETUP_FAIL`, inspect rendered output, then deliver the engine-generated PDF. Do not replace the pipeline with an ad-hoc PDF renderer unless Nima explicitly requests that.
