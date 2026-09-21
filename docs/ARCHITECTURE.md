# Architecture

`report.json -> strict schema -> semantic validation -> public scrub -> dependency fingerprints -> independent page render -> deterministic page hashes -> merge -> link checks -> render/preflight QA`

## Determinism

ReportLab pages are generated in invariant mode. The final writer receives fixed metadata. Two clean builds from the same input and runtime contract are regression-tested for byte-identical page artifacts and merged PDFs.

## Surgical rebuilds

Each page is an independent artifact under `pages/`. `manifest.json` stores:

- global fingerprint: metadata + ordered page structure + renderer/schema/theme/runtime contract
- per-page input fingerprint
- evidence image SHA-256 where applicable
- artifact SHA-256

With `--only PAGE_ID`:

1. A changed global/runtime/structural fingerprint invalidates reuse and causes a full rebuild.
2. A changed non-requested page or evidence file is automatically added to the render set.
3. A missing/tampered artifact is automatically rebuilt.
4. Unaffected artifacts remain byte-identical.

## Final boundary QA

After merge, PyMuPDF opens and renders every final page at 2x resolution. The preflight validates page count, A4 dimensions, renderability, non-blank raster output, extractable text, and text boxes staying inside the media box. PNGs and hashes are retained under `qa/` for human or future visual-regression inspection.

## Failure over fakery

The build fails on malformed archetype content, banned internal text, missing evidence, overflow/fit violations, dead visible resume links, malformed table/chart data, or failed rendered QA. Normal content is never silently sliced to fit.

## Visual regression workflow

Cover comparison fixtures live in `examples/cover_showcase_en.json` and `examples/cover_showcase_fa.json`. They are rendered by the same production cover renderer and are not mockups or exported images. Visual changes must be verified by building these fixtures plus `examples/client_report.json` and rendering the resulting PDFs.
The five cover variants are production code paths, not temporary experiments. The Persian fixture must also verify localized author identity (`نیما محب`) while exercising the exact same variant implementations in RTL mode.
