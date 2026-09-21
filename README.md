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

Five engine-owned variants: `signal-orbit`, `glass-panel`, `aurora-strata`, `constellation`, `editorial-split`. `signal-orbit` is the default. `meta.mode: "cover_showcase"` exists only for engine-generated comparison PDFs.
