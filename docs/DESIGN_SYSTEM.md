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
