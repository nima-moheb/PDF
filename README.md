# Nima Report Engine

A fast, deterministic A4 report compiler for Nima's chats. The chat provides relevant content; the engine owns typography, layout, exact pricing, safe page edits and final PDF verification.

**Chat: start with [AI_USAGE.md](AI_USAGE.md) and one matching example.** No full-repository audit is needed to generate a report.

## Quick start

```bash
python -m pip install -e .
python -m reportkit build examples/quick_report_fa.json output/report.pdf
```

English and Spanish examples are `examples/quick_report_en.json` and `examples/quick_report_es.json`. Python 3.11+ is required. Vazirmatn and IBM Plex Sans are bundled with their licenses; generation works offline once the Python dependencies are installed.

The command returns paths to the accepted PDF, editable source and rendered PNGs. The chat must inspect the result before delivering it. The repo cannot automatically make a file available in a chat: the chat's file-delivery tools must actually save/attach it.

## What 0.7 adds

- A short chat entry point and one CLI: `doctor`, `validate`, `build`, `inspect`, `edit`, `verify`, `pack`.
- Consistent bundled Persian/Latin fonts; language-aware English, Persian and Spanish chrome.
- Exact decimal pricing with explicit toman/rial/USD/EUR/GBP, checked totals and protected content.
- Independent `report.build/` bundles, including source and copied evidence assets.
- Transactional acceptance: a failed build leaves the last good PDF and its source intact.
- Automatic unchanged-page reuse; verified final-page PNG reuse, font/runtime-aware invalidation and strict page-edit boundaries.
- Exact footer-counter checks, source identity, missing-glyph rejection and preview-delivery rejection.
- Mirrored Persian tables/cards, corrected bar-chart baselines, and cleaner cover/closing/pricing composition.

## Revise one page

```bash
python -m reportkit inspect output/report.pdf
python -m reportkit edit output/report.pdf --page 2 --replacement replacement-page.json
```

The replacement is a complete semantic page object with the same stable ID. Page two means the second PDF page, including the cover. Strict edits abort if anything outside the requested page or any shared rendering dependency has changed. Other page PDFs and accepted PNGs remain byte-identical.

For intentional global changes, rebuild the complete source. The engine detects affected pages automatically. The older `python build.py input.json output.pdf --only page-id` interface remains available.

## Output and handoff

For `output/report.pdf`, the independent bundle is:

```text
output/report.build/
  source.json
  assets/
  pages/
  qa/
  manifest.json
```

`source.json` is the accepted semantic input. Assets are copied into the bundle so it can be moved. The manifest records page IDs, titles, order, hashes, font/runtime dependencies, changed pages and timings. The PDF includes the matching source digest and production/preview status.

```bash
python -m reportkit verify output/report.pdf
python -m reportkit pack output/report.pdf output/report-editable.zip
```

Keep the editable ZIP for another chat. A PDF alone is not enough for a safe semantic revision. **Do not commit private client reports into this public repository.**

## Design and compatibility

All five approved covers remain: `signal-orbit`, `glass-panel`, `aurora-strata`, `constellation`, `editorial-split`. The twelve semantic archetypes include summary, text, cards, charts, comparison, table, pricing, evidence, timeline, sources and closing. No per-report coordinates or arbitrary styling overrides.

Version 0.6 JSON remains accepted. Missing `meta.language` is inferred as Persian/English for compatibility; new reports should set it explicitly. Version 0.7 uses a new per-output bundle location and requires a full initial rebuild from legacy artifacts. Unsupported languages, missing glyphs, impossible page composition and unverified facts cannot be solved by renaming an old PDF.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests cover deterministic output, real English/Persian fixtures, all ten cover variants, pricing, font changes, rollback, source identity, exact counters, cache corruption, moved evidence, strict edits and concurrent-output protection. No GitHub Actions are needed for generation or verification.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md), and [AUDIT_0.7.md](docs/AUDIT_0.7.md) for maintenance details.
