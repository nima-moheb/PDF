# AI Usage Contract

This repository is Nima's default PDF-report compiler. The AI supplies semantic content; the engine owns presentation, page composition, typography, bidi behavior, and verification.

## Absolute rules

- A generated PDF is always a finished deliverable for another human.
- Never include TODO, draft watermark, internal/manager/CEO note, debug text, placeholder text, prompt text, reasoning, generator commentary, or instructions to Nima.
- Do not provide coordinates, font sizes, margins, colors, table widths, per-card accents, header/footer overrides, or chart styling in report JSON. The schema rejects them.
- Never silently truncate. `FIT_FAIL` means recompose, split, or shorten without losing meaning.
- Never ship a page merely because everything technically fits. Default QA rejects materially sparse compositions with `SPARSE_PAGE_FAIL`.
- Do not stretch decorative elements or invent filler to satisfy density. Consolidate related content, add substantive explanation supported by the source, or choose a more appropriate archetype.
- Missing evidence/screenshot assets are build failures. Never substitute fake evidence.
- Use `--only <page-id>` only for local corrections; the engine expands or invalidates surgery when dependencies changed.
- Source generation is not completion. Build with QA enabled and inspect rendered pages before delivery when visual judgment matters.

## Typography and Persian text

- Production Latin typography is IBM Plex Sans.
- Production Persian typography is Vazirmatn Regular/Medium/Bold. These fonts are mandatory: the renderer must fail with `FONT_SETUP_FAIL` rather than silently fall back to Noto/DejaVu or another Persian face.
- If fonts are missing, run `python scripts/bootstrap_fonts.py` or provision the pinned files through `REPORTKIT_FONT_DIR`, then rebuild.
- The engine normalizes copied Persian text before layout: Unicode NFC, Arabic Yeh/Kaf normalization, and removal of BOM/soft-hyphen/zero-width/bidi-control artifacts. ZWNJ is preserved.
- Do not insert invisible bidi/control characters to force Persian layout. Supply normal logical-order Unicode text.
- Mixed English, versions, percentages, URLs and product names remain atomic through the bidi pass.

## Approved archetypes

`cover`, `summary`, `text`, `cards`, `chart_text`, `comparison`, `table`, `image_text`, `timeline`, `sources`, `closing`.

### Composition rules

- Choose archetypes by meaning, not by habit. Long reports must not repeat the same card grid for every section when another archetype represents the content better.
- `summary` is for a substantive editorial lead plus 1-4 genuine values. Summary-card `value` cannot be empty. If there is no meaningful metric/value, use `cards` or `text` instead of creating fake/blank metrics.
- English editorial/body prose is justified where the component supports it; the final line stays natural.
- `cards.layout` may be `auto`, `grid`, `bands`, or `feature`. Prefer `auto`; it varies composition deterministically from content/page identity while preserving semantics.
- RTL page chrome, card ordering, comparison ordering, table columns and timeline rails mirror automatically. Do not manually reverse arrays for Persian.
- Source pages intentionally remain compact; do not stretch citations just to fill A4.

## Cover selection

All five cover variants are permanent production templates. Choose from content and audience; do not mechanically default to one and do not ask Nima unless visual direction is itself a real decision.

- `signal-orbit`: technical, analytical, performance, SEO, infrastructure, engineering.
- `glass-panel`: executive, client-facing, business review, proposal, management summary.
- `aurora-strata`: innovation, AI, product, future-facing technology.
- `constellation`: strategy, research, roadmap, multi-source evidence, connected systems.
- `editorial-split`: formal research, finance, legal/policy-style, evidence-heavy/document-centric.

Theme is independent: blue general/technical, green growth/operations, purple innovation/creative, orange strategy/opportunity, red risk/critical, graphite formal/neutral.

Every cover supports LTR and RTL. Persian/RTL covers display Nima as `نیما محب`, even if upstream metadata contains `Nima Moheb`. Mixed trailing acronyms such as `CRM` are separated into a controlled Latin badge instead of being allowed to destabilize the Persian title line.

## Default ChatGPT report workflow

When Nima asks for a PDF report and provides content/sources:

1. Use this repository unless Nima explicitly requests a different pipeline.
2. Convert content into semantic report JSON; do not hand-design coordinates.
3. Choose cover, palette, and varied interior archetypes from content/audience.
4. Prefer substantive page composition over maximizing page count. Consolidate thin sections before creating sparse pages.
5. Build with `build.py` and QA enabled.
6. If the build raises `FIT_FAIL`, `FONT_SETUP_FAIL`, or `SPARSE_PAGE_FAIL`, fix the cause; do not bypass the check with another renderer.
7. Inspect the rendered QA PNGs for typography, RTL behavior, orphan lines, hierarchy, balance, and clipping.
8. Deliver the repo-generated PDF only after the actual rendered boundary passes.
