# Nima Report Engine

A deterministic A4 report compiler for finished, human-facing PDFs. The AI supplies validated structured content; the engine owns layout, typography, themes, charts, tables, headers/footers, fit rules, rendering, and final-output QA.

## Guarantees

- Strict archetype-specific JSON schema. Unknown layout/style controls are rejected.
- No silent content truncation. Content either fits/wraps inside its approved component or the build fails with `FIT_FAIL`.
- Reproducible clean builds: page PDFs and the merged PDF are byte-identical for identical inputs/runtime contract.
- Safe surgical rebuilds: `--only page-id` fingerprints global state, page inputs, page artifacts, and evidence bytes. Global/structural changes automatically force a full rebuild; unexpected changed pages are included automatically.
- Every final PDF is rendered to PNG at the output boundary and preflighted for A4 size, page count, renderability, non-blank output, and out-of-media-box text.
- Persian RTL uses system FriBidi when available, with complete LTR token protection for versions, percentages, URLs, emails, and English phrases; deterministic fallback remains available.
- Evidence image paths are resolved relative to the report JSON, not the shell working directory.
- Schema/theme assets are packaged inside `reportkit`; editable-repository layout is not required after installation.
- Final-output safety rejects TODO/draft/internal/debug/placeholder language.
- Missing evidence assets are hard failures.
- Normal-page footers contain no resume button. The closing page shows the real resume URL and that visible URL is a clickable PDF URI annotation.
- No GitHub Actions are required for routine generation or verification.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python scripts/bootstrap_fonts.py  # recommended exact typography
```

Font bootstrap defaults to `~/.cache/nima-report-engine/fonts`; override with `REPORTKIT_FONT_DIR`.

## Build

```bash
python build.py examples/client_report.json output/report.pdf
```

A successful build produces:

- `output/report.pdf`
- `output/pages/*.pdf` independent deterministic page artifacts
- `output/manifest.json` fingerprints + artifact hashes + build mode
- `output/qa/page-*.png` rendered final pages
- `output/qa/qa_manifest.json` final PDF/render hashes and preflight measurements

Surgical repair:

```bash
python build.py examples/client_report.json output/report.pdf --only trend
```

The engine decides whether reuse is safe. The caller does not need to know which global or local dependencies changed.

## Test

```bash
python -m unittest discover -s tests -v
```

See `AI_USAGE.md`, `docs/DESIGN_SYSTEM.md`, `docs/COMPONENTS.md`, and `docs/ARCHITECTURE.md` before generating reports.

## Cover system

Five permanent production variants are included: `signal-orbit`, `glass-panel`, `aurora-strata`, `constellation`, and `editorial-split`. All five render through the same production engine and all five mirror for Persian/RTL. The Persian showcase is not a separate fake template set; it is the RTL rendering of the same five engine variants.

The report-generating chat chooses a cover from content and audience rather than always using one default:

- `signal-orbit` — technical / analytics / performance / engineering
- `glass-panel` — executive / client / business / proposals
- `aurora-strata` — innovation / AI / product / future-facing technology
- `constellation` — strategy / research / roadmaps / connected evidence
- `editorial-split` — formal research / finance / legal-policy / document-heavy work

For Persian/RTL covers, Nima's displayed author name is always **نیما محب**. Theme selection remains independent from cover geometry. `meta.mode: "cover_showcase"` exists only for engine-generated comparison PDFs.

## Default ChatGPT workflow

This repository is the default PDF-report pipeline for Nima. When a chat has the report content, it should structure the content as report JSON, choose an appropriate cover and palette, build with the repo, pass rendered QA, inspect output where visual judgment matters, and deliver the resulting PDF. It should not bypass the repo with an ad-hoc PDF implementation unless Nima explicitly asks for a different pipeline. The operational contract is in `AI_USAGE.md`.


## v0.5 real-report hardening

Real Nika CRM production reports exposed failure modes that synthetic samples did not. v0.5 makes those cases part of the engine contract:

- adaptive page-density composition for summary/text/cards/comparison/timeline pages;
- `QA_DENSITY_FAIL` for pages whose meaningful content stops too high on the sheet;
- justified English explanatory paragraphs;
- mirrored RTL navigation/header/footer geometry;
- Persian input-control normalization while preserving ZWNJ;
- production Persian font gate: Vazirmatn must be bootstrapped instead of silently using Naskh;
- balanced final-line wrapping to avoid one-word cover/subtitle widows;
- real English/Persian regression fixtures in `examples/real_case_regression_*.json`.

For a Persian report, run `python scripts/bootstrap_fonts.py` before the build. Automated tests may set `REPORTKIT_ALLOW_PERSIAN_FALLBACK=1`; finished deliverables must not.

- Executive summaries must be substantive when the source is substantive: synthesize the important findings in supported prose, then reinforce them with metrics. Density is not permission to inflate empty components around weak content.
