# Architecture — 0.7

`JSON → semantic validation → dependency fingerprints → independent pages → merge → final-page QA → density/delivery checks → accepted PDF and bundle`

## Boundaries

- `contract.py`: strict JSON, readable errors, explicit language, required/protected content and source identity.
- `pricing.py`: exact decimal totals and the semantic pricing component.
- `fonts.py`: packaged licensed fonts, checksum/coverage validation and font-byte fingerprints.
- `presentation.py`: current language context, page chrome, closing page and glyph checks. Approved existing geometry lives in `engine.py` and the historical `visual_v05/v06/v062` component modules.
- `pipeline.py`: the single public build transaction. Historical build wrappers are not the public execution path.
- `qa.py`: final merged page text/size checks and verified PNG rendering/reuse.
- `delivery.py`: producer/version, source digest, production status, fonts, glyphs, exact page/current-total counters.
- `cli.py`: chat-facing commands and strict page replacement from the accepted source.

## Determinism and reuse

A global fingerprint includes metadata, page order/IDs, content requirements, Python and dependency versions, bidi backend/version, font bytes, renderer code, schema and themes. Each page has a semantic fingerprint and artifact hash. Evidence is copied into a portable bundle with a content-hashed name.

Default builds reuse unchanged artifacts automatically. An ordinary `--only ID` expands when another page changed and forces a full build for shared changes. `--strict-only` aborts instead. Changing a page's interior archetype can remain local; changing its position, page count, recipient, language or theme is global.

Final merged pages are reopened on every build. A prior PNG can be reused only when its own hash, single-page artifact hash, final merged page serialization (including resources), and QA/runtime contract match. Other pages are rendered again. This keeps validation at the final file boundary without repeatedly rasterizing unchanged pages.

## Transaction and concurrency

Each output has its own `<stem>.build` folder and OS advisory lock. Locks are released by the OS after a process exits; stable lock files are harmless. A process-wide lock serializes legacy component globals. Distinct processes can build distinct reports concurrently.

Builds write a temporary candidate next to the output. The final PDF is replaced only after all requested gates pass. Ordinary errors also restore the prior bundle. A process crash between bundle/PDF replacements is detected by digest mismatch; a strict edit then refuses reuse. This is not a cross-file, power-loss-atomic database transaction.

Page replacement starts from accepted `source.json`, requires the same stable ID, validates against the prior source digest to avoid lost updates, and confirms unchanged page hashes. A failed edit leaves both source and PDF unchanged. Report bundles carry images so source identity survives moving the folder.

Archive creation holds the same output lock while checking acceptance and copying the PDF/bundle into a temporary ZIP. It then atomically replaces the ZIP file. Resume from the PDF and bundle inside that archive; file-delivery services may append metadata to a standalone PDF, so its receipt must not be mixed with the original bundle.

## Delivery claims and limits

The standard CLI `verify` checks build/QA receipts and the final file. The Python file verifier checks source identity when supplied a source. These are integrity and rendering checks, not cryptographic authorship authentication, factual verification, accessibility certification, or a substitute for visual review.

Preview output is explicitly marked and cannot pass delivery. Internal-test environment variables no longer bypass production rules. Unsupported glyphs fail rather than silently becoming squares.

The engine supports English, Persian and Spanish chrome. The chat owns the content's language, relevance, factual accuracy and reader suitability. Every new report needs a human/assistant visual review of rendered pages; local edits need review of changed pages.

## Testing

Run `python -m unittest discover -s tests -v`. Meaningful regression boundaries include rollback after rendering/delivery failure, strict page isolation, corrupted caches, exact money, font changes, source mismatch, moved evidence and deterministic output. Build the cover showcases and affected real examples when changing geometry. No GitHub Actions dependency.
