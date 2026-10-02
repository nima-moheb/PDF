# PDF engine working brief

Status: LIVE v2, 2026-10-02. Engine: 0.7.0. Audit baseline: `f27877ee5e6576202faf20cf841907b4dbd0d68a` (0.6.2). Git history and the associated pull request record publication state.

## Goal

Make an unrelated chat able to produce a relevant, polished report from its existing context: recipient, language, requested sections/patterns, and exact prices. Make later page-specific corrections safe and fast.

## Binding decisions

- Keep `nima-moheb/PDF` as the canonical engine; preserve all five approved covers and semantic page archetypes.
- Content stays in structured JSON; the engine owns geometry. Never patch the exported PDF or silently truncate approved content.
- Embed a proper Persian sans, prefer Vazirmatn, preserve mixed English/Persian values and ZWNJ shaping; localize the author as «نیما محب».
- Validate final rendered output and delivery; no GitHub Actions dependency.
- A page correction must preserve untouched pages. Global changes must be explicit when strict page isolation is requested.

## Verified audit findings

- Baseline tests cannot import: a literal backslash-n in `tests/test_engine.py` creates a SyntaxError.
- Preferred fonts are not shipped. Font download is optional, so normal offline output falls back to DejaVu Sans.
- Cache fingerprints omit font bytes, Python/library versions, and the bidi implementation.
- All reports in one directory share `pages/`, `qa/`, and `manifest.json`.
- Builds overwrite the destination before final QA, density, and delivery acceptance.
- Delivery checks only count footer digits; they do not check exact counters or source identity.
- Preview/test output has no strong delivery distinction. Cover showcases are incorrectly treated as numbered reports.
- Every edit re-renders all final PNGs and scans pixels in Python.
- No concise task entry point, explicit language field, pricing component, or machine-checked content requirements.
- Persian tables retain LTR column order and English DATA TABLE chrome. Bar charts use a nonzero baseline even for positive values.

## Implemented and verified

0.7.0 ships licensed Vazirmatn/IBM Plex fonts, a single validated build transaction, portable per-report bundles, dependency-aware incremental QA, strict page replacement, exact decimal pricing, content requirements and English/Persian/Spanish chrome. The chat entry point is `AI_USAGE.md`; ordinary generation needs only that file and one relevant example.

All 52 tests pass. Nine example reports (44 pages) pass final gates, and affected layouts have been visually reviewed. The wheel installs and builds Persian output outside the checkout. A six-page Persian run took 0.531 s for a full build, 0.108 s unchanged, and 0.209 s for a page-two edit; the five untouched page artifacts remained identical. These timings exclude chat work and cold environment setup. Details: `AUDIT_0.7.md`.

## Continuing work

For a report request, use the user's current conversation as the content brief, preserve approved values, build, inspect rendered pages and actually deliver the file. Keep its editable bundle for later chats. Do not repeat the engine audit during routine generation.

For a future engine change, preserve the same rendering boundaries and rerun relevant tests/visual fixtures. Additional languages, complex tax models and new layout patterns need explicit implementation and verification. Facts, relevance and unsupported scripts are not inferred by the compiler. A PDF alone cannot provide a safe semantic page revision.
