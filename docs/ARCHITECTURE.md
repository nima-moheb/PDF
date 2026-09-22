# Architecture

`report.json -> strict schema -> text normalization -> semantic validation -> public scrub -> dependency fingerprints -> independent page render -> deterministic page hashes -> merge -> link checks -> render/preflight QA`

## Determinism

ReportLab pages are generated in invariant mode and the merged writer receives fixed metadata. Identical input/runtime state is regression-tested for byte-identical page artifacts and final PDFs.

## Text normalization

Before validation/rendering, strings are NFC-normalized. Unsafe copied-text controls (BOM, soft hyphen, zero-width space, direction overrides/isolates, word joiner) are removed, Arabic Yeh/Kaf variants are normalized to Persian forms, and ZWNJ is retained. This prevents invisible control characters from producing the hairline/joining artifacts observed in real Persian reports.

## Font contract

IBM Plex Sans and Vazirmatn are production dependencies, not preferences. The engine refuses unapproved Persian fallback fonts with `FONT_SETUP_FAIL`; a visually wrong fallback PDF must never be emitted as a successful report.

## Page composition QA

PyMuPDF reopens and renders every final page. In addition to A4 size, renderability, page count, text bounds and non-blank checks, v0.5 measures the vertical span/reach of actual text blocks inside the information body. Decorative grids/backgrounds are excluded from that measurement. Content archetypes have minimum composition thresholds and fail with `SPARSE_PAGE_FAIL` when a page is materially underused.

The response to `SPARSE_PAGE_FAIL` is semantic recomposition: consolidate related content, add source-supported explanation, or choose another archetype. Decorative stretching/filler is not an acceptable fix. `sources` intentionally has a lower threshold because citations are designed to stay compact.

## Surgical rebuilds

`manifest.json` fingerprints global runtime/layout state, every page input, evidence bytes and artifacts. `--only PAGE_ID` automatically expands for changed pages and becomes a full rebuild when global/structural state changed. Unaffected pages remain byte-identical.

## Failure over fakery

Build failure is preferable to a deliverable with wrong fonts, malformed bidi text, empty summary metrics, clipped content, dead links, fake evidence, or visibly sparse composition.

## Regression workflow

- `examples/cover_showcase_en.json` and `examples/cover_showcase_fa.json` exercise all five production cover variants.
- `examples/regression_crm_en.json` and `examples/regression_crm_fa.json` are permanent real-case regressions derived from the CRM reports that exposed sparse composition, Persian control-character artifacts, RTL mirroring and timeline/table problems.
- Every engine change must run the full unittest suite and build/render these fixtures before merge.
