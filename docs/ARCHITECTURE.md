# Architecture

`report.json -> validate/scrub -> render independent page PDFs -> hash manifest -> merge -> preflight/render QA`

Each page is an independent artifact under `pages/`. `--only PAGE_ID` re-renders only that page and reuses all other artifacts. This enables surgical corrections without collateral layout changes.

A structural change can legitimately invalidate dependent pages. Examples: inserting/removing a page changes page numbers; changing a section title may change a TOC. Ordinary page-local edits do not.

## Failure over fakery
Build fails on missing required images, banned internal text, overflow, or fit violations. The renderer does not silently shrink normal content below its design contract and does not draw fake evidence placeholders.
