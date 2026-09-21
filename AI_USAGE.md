# AI Usage Contract

This repository is a report compiler. The AI supplies semantic content; the engine owns presentation and verification.

## Absolute rules

- A generated PDF is always a finished deliverable for another human.
- Never include TODO, draft watermark, internal/manager/CEO note, debug text, placeholder text, prompt text, reasoning, generator commentary, or instructions to Nima.
- Do not provide coordinates, font sizes, margins, colors, table widths, per-card accents, header/footer overrides, or chart styling in report JSON. The strict schema rejects them.
- Select approved archetypes and provide content only.
- Never shorten content by slicing/truncating fields to make them fit. A `FIT_FAIL` means shorten without losing meaning, split content into another page, or choose another approved archetype.
- Missing evidence/screenshot assets are build failures. Never substitute decorative fake evidence.
- Evidence paths may be relative to the report JSON.
- Page 1 has no visible page number. Pages 2+ use deterministic engine-owned navigation/footer components.
- Use `--only <page-id>` for local corrections. The engine verifies whether surgery is actually safe and expands/invalidates it automatically when dependencies changed.
- Do not treat source generation as success. A successful default build must pass final merged-PDF rendered QA and produce the `qa/` artifacts.

## Approved archetypes

`cover`, `summary`, `text`, `cards`, `chart_text`, `comparison`, `table`, `image_text`, `timeline`, `sources`, `closing`.

## Visual identity

- A4 portrait, Modern Digital.
- Themes: blue, green, purple, orange, red, graphite.
- Latin: IBM Plex Sans when bootstrapped.
- Persian: Vazirmatn when bootstrapped.
- Mixed Persian/English/numbers/URLs must remain readable and atomic where appropriate.
- Normal-page footers do not show a resume control. On a closing page, the visible `nima-moheb.github.io/myCV/` URL itself is the clickable PDF URI annotation.

## Cover selection

All five cover variants are permanent production templates. Choose the variant from the report's content and audience; do not mechanically default to one design and do not ask Nima to choose unless the request itself makes visual direction a meaningful decision.

- `signal-orbit`: technical, analytical, performance, SEO, infrastructure, data-heavy, engineering.
- `glass-panel`: executive, client-facing, business review, proposal, management summary, polished corporate delivery.
- `aurora-strata`: innovation, AI, product, technology, future-facing, creative technical work.
- `constellation`: strategy, research, roadmap, multi-source evidence, systems and connected findings.
- `editorial-split`: formal research, finance, legal/policy-style material, evidence-heavy or document-centric reports.

Theme is selected independently from the approved palettes: blue for general/technical, green for growth/operations, purple for innovation/creative work, orange for strategy/opportunity, red for risk/critical findings, graphite for formal/neutral material. These are selection heuristics, not rigid category locks.

Every variant supports LTR and RTL. For Persian/RTL covers, Nima's displayed author identity is `نیما محب`; the renderer enforces this even if upstream metadata still contains `Nima Moheb`. `cover_showcase` mode exists only for engine-generated visual comparison PDFs. Ordinary reports contain exactly one cover.

## Default ChatGPT report workflow

When Nima asks for a report/PDF and provides the content or source material, this repository is the default production path:

1. Convert the content into the semantic report JSON; do not hand-design coordinates or bypass the engine.
2. Choose the cover variant and palette from the content, audience, seriousness, and visual tone using the guidance above.
3. Choose the interior archetypes that best express the content. Add pages when needed instead of shrinking or truncating content.
4. Use Persian/RTL mode when the report is Persian; keep mixed English, versions, percentages and URLs intact.
5. Build through `build.py` with QA enabled. Source generation alone is not completion.
6. Inspect the rendered QA pages when layout judgment matters and correct the report JSON/engine if necessary.
7. Deliver the final engine-generated PDF. Do not substitute a one-off PDF made through a different rendering pipeline unless Nima explicitly asks to abandon this repo.
