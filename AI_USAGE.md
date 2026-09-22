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


## Real-report acceptance rules (v0.5)

The 22 September 2026 Nika CRM English/Persian reports are regression evidence for the following non-negotiable rules:

- A page is not successful merely because nothing overflows. For `summary`, `text`, `cards`, `comparison`, `timeline`, and `chart_text`, final QA enforces a minimum meaningful vertical content reach. Mostly-empty pages fail with `QA_DENSITY_FAIL` and must be recomposed.
- Summary pages use a designed intro panel plus compact metric cards with dominant centered values. Do not place four small metrics at the top and leave the lower page blank.
- Text/card pages distribute their components through the usable page field. Do not cap card expansion in a way that leaves the lower third or half unused.
- English multi-line explanatory paragraphs are justified when appropriate. Short labels, card titles, notes, and Persian text are not force-justified.
- Persian/RTL page chrome is mirrored: navigation marker/accent on the right, report identity on the right, page chip on the left. Interior titles are right-anchored with proper separation from eyebrows/navigation.
- Persian source text is normalized before measurement/rendering. BOM/FEFF, directional marks, soft hyphens, and pasted bidi-isolate controls are stripped; semantic ZWNJ is preserved.
- Persian production output requires bootstrapped Vazirmatn. If it is not available, the build fails with `FONT_SETUP_FAIL` instead of silently shipping an unapproved Naskh-style fallback. Run `python scripts/bootstrap_fonts.py`, then rebuild. `REPORTKIT_ALLOW_PERSIAN_FALLBACK=1` is for automated portability tests only, not client deliverables.
- Cover and paragraph wrapping includes widow control so a single short word is not stranded on a final line when a balanced reflow is possible.
- Timeline geometry mirrors for RTL and uses the full page field; comparison cards also mirror bullets/badges and occupy the available content height.

When a real report exposes a visual defect, fix the reusable renderer/archetype first and add a regression case. Do not patch the exported PDF by hand.

- Long reports must not repeat one cards/text template page after page. v0.5 rejects more than two consecutive `cards` or `text` pages, and rejects those archetypes when either dominates more than 55% of an interior report. Re-architect the information using comparison, timeline, table, summary, chart, sources, or other appropriate approved archetypes.

- For a substantial source report, an executive summary must synthesize the actual material rather than restating a generic product description. Use enough supported prose to explain the important findings (multiple short paragraphs when warranted), then use metrics/cards as reinforcement. Do not create a visually full page by inflating empty boxes around thin content.

## Persian rendering acceptance rules (v0.6)

- Semantic ZWNJ is preserved through shaping/wrapping, but all zero-width/control characters are removed from the final visual glyph runs. They must never appear as visible dashes/hairlines in the PDF.
- Persian/RTL reports use Persian-only decorative chrome. Engine labels such as REPORT, DATA / INSIGHT / IMPACT, NIMA REPORT ENGINE, STRUCTURED / FINAL, PAGE, REPORT COMPLETE, and PORTFOLIO / RESUME are localized in RTL output. Intentional English terms that are part of the report content (for example CRM, Laravel, Applitent, URLs, product names) are preserved.
- RTL page counters use Persian language and digits (`صفحه ۲ از ۶` style).
- Summary metrics are primary visual anchors: large 36pt+ values, graphic metric medallions, and compact supporting labels/notes. Tiny numbers floating in oversized cards are not acceptable.
- Three-way comparison/access-model pages use large Persian step numbers, a distinct value medallion, and bullets distributed through the card body rather than leaving the lower card empty.
- Persian timeline step indices use Persian digits.
