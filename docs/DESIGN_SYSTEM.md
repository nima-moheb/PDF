# Visual System - Modern Digital

## Intent

One variable human-facing report system. The AI chooses semantic page archetypes; the renderer owns geometry, appearance, fit behavior, and final-output verification.

## Fixed visual language

- A4 portrait.
- Modern Digital: technical grid, asymmetric composition, controlled gradients/glow, rounded depth, strong hierarchy.
- Page 1 uses one approved cover variant and no visible page number. Approved variants: `signal-orbit`, `glass-panel`, `aurora-strata`, `constellation`, `editorial-split`; all mirror for RTL.
- Cover variants are selected semantically: signal-orbit for technical/data work; glass-panel for executive/business delivery; aurora-strata for innovation/technology; constellation for strategy/research/connected evidence; editorial-split for formal/document-heavy work. The mapping is guidance, not a hard restriction.
- Persian/RTL cover metadata displays Nima's name as `نیما محب`; this localization is enforced by the renderer.
- Pages 2+ use the same engine-owned navigation header and identity footer.
- Same geometry across coordinated blue, green, purple, orange, red, and graphite palettes.

## Typography and bidi

- Latin: IBM Plex Sans regular/bold when bootstrapped.
- Persian: Vazirmatn regular/medium/bold when bootstrapped.
- Runtime survival may use suitable system fallbacks.
- FriBidi is used when available for native bidirectional ordering and Arabic shaping. Complete LTR tokens are protected through the bidi pass so URLs, percentages, emails, versions, and multi-word English phrases stay intact.
- Normal body target remains ~10.5-11 pt; tables ~8.2+ pt; source/caption text ~7+ pt. Content that cannot fit at the component's permitted size fails instead of being microscopically shrunk or sliced.

## Chart integrity

- Line charts require labels matching every data point and show point values.
- Bar charts use one clean rounded body per value with value labels.
- Unsupported chart types fail schema validation.

## Interior layout v0.4

- Section titles sit lower than the navigation rail to preserve breathing room.
- Metric values are centered within summary cards.
- Content and timeline cards use one consistent top accent rail; no first-card-only exception.
- Chart pages anchor the chart immediately below the section title rather than leaving a large dead band.
- Comparison cards use soft header fields, index pills and consistent color hierarchy.
- Tables use a restrained light header, subtle separators and no full-width accent bar.
- Source cards use content-sized compact rows instead of stretching to fill the page.
- Normal footers never show `VIEW RESUME`; the closing identity card exposes the actual clickable resume URL.


## Real-report density and RTL rules (v0.5)

- Usable-page composition is a design requirement, not a side effect of content length. Summary, text, cards, comparison, timeline, and chart pages must carry meaningful content through the main vertical field. A large blank lower region is a failed composition.
- The renderer may enlarge/reflow approved components and redistribute whitespace, but may not invent semantic content merely to fill space.
- Summary metrics are visually dominant and centered. Introductory narrative is treated as a designed panel, not loose text above oversized empty cards.
- English explanatory prose can use full-width justification. Persian remains right-aligned rather than using crude synthetic justification.
- RTL mirrors navigation chrome, title markers, footer identity, page chips, timelines, and direction-sensitive card details.
- Persian typography is Vazirmatn in production. Sans/UI fallback exists only for explicit test mode.
- U+FEFF/BOM, LRM/RLM, ALM, soft hyphen, and stray bidi-isolate controls are removed before layout. Persian ZWNJ is retained.
- Wrap balancing prevents avoidable one-word final lines in prominent cover/subtitle text.

- Layout diversity is enforced for long reports: no more than two consecutive `cards` or `text` pages, and neither may dominate more than 55% of interior pages. Repetition is a failed information architecture, not a valid way to fill a report.

## Persian polish v0.6

- Zero-width join controls belong to shaping, never to visible glyph output. After bidi shaping, Unicode format controls are removed from the visual run before font measurement/drawing.
- RTL engine chrome is Persian-only. English is allowed only when it is intentional source content, such as a product/acronym, version, URL, or proper name.
- Persian page counters read naturally (`صفحه N از M`) and use Persian digits.
- Metric pages use visual medallions/halos and dominant 36pt+ values rather than small centered numerals in empty rectangles.
- Comparison/access-model cards use large Persian step numbers plus a separate semantic-value medallion, with bullet content distributed through the lower field.
