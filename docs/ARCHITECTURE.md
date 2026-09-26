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


## v0.5 visual acceptance stage

The public package installs `reportkit.visual_v05` over the stable v0.4 semantic renderer. The layer owns text normalization, production Persian font gating, adaptive density composition, RTL chrome mirroring, paragraph justification, and post-build density QA.

After ordinary merged-PDF render QA succeeds, v0.5 performs a semantic density pass using the known page archetypes. Pages that are technically valid but visually abandon the lower sheet fail with `QA_DENSITY_FAIL`. This turns the real-world "two-thirds empty" failure into a reproducible build error rather than a subjective review note.

## v0.6 final-glyph layer

`reportkit.visual_v06` is installed after v0.5. Its most important boundary is between bidi shaping and ReportLab glyph drawing: semantic controls such as ZWNJ are allowed to influence shaping, then Unicode format controls are stripped from the final visual runs before width calculation and drawing. This prevents viewer-specific control-glyph artifacts without destroying Persian word joining semantics.

The same layer localizes RTL decorative chrome and owns the v0.6 summary/comparison visual components. Tests inspect the generated PDFs with PyMuPDF to assert that ZWNJ is absent from final extracted glyph text, Persian cover chrome contains no English engine labels, page chrome is localized, and summary metrics render at dominant size.

## v0.6.1 delivery provenance boundary

Rendered QA is followed by a second file-level delivery gate. It reopens the emitted PDF and verifies provenance metadata, glyph-stream cleanliness, Persian production fonts, and footer counters. The public `build` entry point cannot return a QA-enabled deliverable that fails this boundary.

The runtime-contract fingerprint now includes `visual_v05.py`, `visual_v06.py`, `delivery.py`, and the v0.6.1 delivery wrapper, so surgical page reuse is invalidated when any of these visual/delivery rules change.

This layer exists because a visually plausible PDF can still be the wrong artifact: an ad-hoc generator can omit engine metadata, use fallback fonts, leak ZWNJ as a visible dash, or lose numeric glyphs. Such a file must fail independently of its source JSON.
