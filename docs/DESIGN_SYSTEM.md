# Visual System - Modern Digital

## Intent

One variable human-facing report system. The AI chooses semantic page archetypes; the renderer owns geometry, appearance, fit behavior, and final-output verification.

## Fixed visual language

- A4 portrait.
- Modern Digital: technical grid, asymmetric composition, controlled gradients/glow, rounded depth, strong hierarchy.
- Page 1 uses the approved `digital-wave` cover and no visible page number.
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
