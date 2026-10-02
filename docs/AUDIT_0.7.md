# Audit and fixes — 0.7.0

Verified 2026-10-02 against baseline `f27877ee5e6576202faf20cf841907b4dbd0d68a` (0.6.2). The goal was faster use from ordinary chats, better Persian typography, trustworthy pricing/content, and safe page-specific corrections.

## Findings and changes

| Finding | Change in 0.7.0 |
|---|---|
| Baseline test module had a syntax error; after repairing it, 12 of 32 tests failed or errored in the audit environment. | Repaired tests, removed production reliance on test-only font bypasses, normalized Persian extraction assertions, and added workflow regressions. |
| Preferred fonts were optional downloads; offline output could silently use DejaVu. | Bundled licensed Vazirmatn Regular/Medium/Bold and IBM Plex Sans Regular/Bold with pinned hashes and glyph checks. |
| Long, scattered instructions made chats rediscover the renderer and installation steps. | One short `AI_USAGE.md`, three buildable starter examples, and a consistent CLI; no font download on the generation path. |
| Reports in the same directory shared page and QA state. | An independent `<report>.build` bundle per PDF, with semantic source, evidence assets and receipts. |
| A failed build could replace a good PDF before acceptance. | Stage all output, run final gates, then replace it; failures preserve the accepted PDF and source. Preview cannot overwrite accepted production output. |
| Page reuse did not account for fonts, runtime libraries or bidi backend. | Fingerprint font bytes, renderer code, schema, themes, Python, libraries and bidi. Strict edits reject shared/unrequested changes and stale source. |
| Every edit rasterized every page and scanned pixels in Python. | Reuse verified unchanged page artifacts and PNGs; use Pillow for pixel counting. Reopen and check the final merged PDF on every build. |
| Footer checks counted digits without verifying their values or source. | Check exact current/total counters, source identity, production status, embedded fonts and final delivery receipts. Cover showcases have explicit rules. |
| No explicit language, checked pricing or content guard contract. | English/Persian/Spanish chrome; decimal pricing with explicit currencies and expected totals; required/protected/forbidden source values. |
| Persian tables/cards were partly LTR; covers could show empty date fields; table panels ended before their rows. | Mirrored RTL layouts, localized chrome, conditional metadata fields and corrected table bounds. |
| Bar baselines misrepresented values; fractional ticks were rounded to integers. | Correct zero baseline for positive/negative bars and meaningful fractional ticks without negative zero. |
| Invalid schema input could emit a traceback. | Concise JSON errors with the precise field path. |

## Verification

- **52 tests pass** using `python -m unittest discover -s tests -v`.
- **9 example reports / 44 pages** pass build, final rendering, density and delivery gates: both five-cover showcases, the original client report, Persian cover, two real-case regressions, and English/Persian/Spanish quick reports.
- Visually reviewed cover variants, Persian typography, mixed-language values, tables, signed charts, summary and pricing pages. All five approved cover designs remain available.
- Built a wheel, installed it in an isolated target, then imported and built a Persian report from outside the checkout. Package data contains the fonts, licenses, schema and themes.
- Regression checks cover failed-edit rollback, exact page counters, page-two isolation, font changes in a running process, moved image bundles, source mismatches, lost updates, output locks, corrupted caches, preview rejection, decimal prices and missing glyphs.
- No GitHub Actions are needed or added.

## Measured generation work

One local run of the six-page Persian real-case fixture, using an already loaded Python process and fonts:

| Operation | Wall time | Pages generated | Pages rasterized |
|---|---:|---:|---:|
| Full forced build | 0.531 s | 6 | 6 |
| Unchanged build | 0.108 s | 0 | 0 |
| Strict page-two correction | 0.209 s | 1 | 1 |

The correction preserved all five untouched page PDFs byte-for-byte. Tests also verify unchanged PNG bytes. These are measurements of local engine work, not an end-to-end chat latency promise; environment startup, installation, research, writing, visual review and delivery add time.

## Practical boundaries

The chat still chooses relevant content, checks facts and supplies approved prices. Requirements guard authored source values; they cannot establish truth or relevance. English, Persian and Spanish are the verified language set. Unsupported glyphs and overfull composition fail explicitly instead of truncating content.

Safe revision in a new chat needs the PDF **and** its editable bundle, available through `pack`. Old 0.6 inputs remain supported, but legacy shared caches require a full rebuild. Recipient, theme, language, page order/count, requirements or engine changes are global and cannot masquerade as a strict one-page edit.

Ordinary failures restore the previous bundle. A crash between bundle/PDF replacement is detected by mismatching receipts; this is not a power-loss-atomic database. The remaining historical visual modules are retained behind a single public pipeline to preserve approved designs; their temporary globals are serialized within a process.

## Handoff follow-up — 0.7.1

A real saved-file round trip appended platform metadata to the standalone PDF while leaving its page content unchanged. The editable ZIP retained the exact accepted PDF and receipts. The instructions now require resuming from the archived pair and explicitly reject changing receipt hashes to accommodate a processed standalone file.

The follow-up also found a pack/edit race: packing previously verified the report before copying files without holding the report lock. Archive creation now holds that lock throughout acceptance, copying and ZIP replacement, and rejects directory/non-ZIP destinations. Two regression tests cover locking and archive restoration followed by a strict page-two edit. All 54 tests pass.

The refreshed Persian sample was saved and downloaded again. Its standalone PDF passed delivery checks and all four rendered pages were pixel-identical to the accepted source. The downloaded editable ZIP was byte-identical; restoring it and editing page two preserved the other three page artifacts exactly. The separately processed PDF is suitable for viewing, while the archived pair is the accepted editing baseline.
