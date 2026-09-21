# Visual System - Modern Digital

## Intent
One variable human-facing report system. It is not tied to SEO, sales, technical work, proposals, or one company. The AI chooses approved page archetypes; the renderer owns geometry and appearance.

## Fixed visual language
- A4 portrait.
- Modern Digital: technical grid, asymmetric composition, controlled gradients/glow, rounded depth, strong hierarchy.
- Calm information density: meaningful content fills normal pages without decorative filler or microscopic text.
- Page 1 is the selected **Digital Wave** cover and has no visible page number. It uses a diagonal light plane, technical grid, layered vector wave, compact metadata cards, and no fake KPI/data claims. Persian titles mirror the composition: title/meta on the right, visual wave/plane on the left.
- Pages 2+ use the same digital navigation header and identity footer.
- Page numbers use a compact page chip, never a floating circle.

## Typography
- Latin: IBM Plex Sans regular/bold.
- Persian: Vazirmatn regular/medium/bold when bootstrapped; Noto Arabic fallback is allowed for runtime survival only.
- Mixed Persian + Latin tokens, versions, URLs, percentages, and email addresses are mandatory regression cases.
- Normal body target: 10.5-11 pt. Tables: 8.5-9 pt minimum. Captions/sources: 8 pt minimum.

## Themes
Same geometry, different palette: blue, green, purple, orange, red, graphite. A theme is a coordinated palette, not a single hex color.

## Identity
Author identity is Nima Moheb. Default client/CEO documents use subtle or normal identity. Prominent identity is reserved for sales/freelance contexts.
Resume: https://nima-moheb.github.io/myCV/ (must be a clickable PDF annotation when shown).

## Content rules
The engine never invents report semantics. Labels such as Recommendation, Risk, Status, Price, Deadline, etc. come from report content, not the renderer.


## Cover direction
The only approved v1 cover is `digital-wave`.
- English/default: `"direction": "auto"` or `"ltr"`.
- Persian: `"direction": "auto"` detects Persian and mirrors automatically; `"rtl"` may be explicit.
- Cover text, date, recipient and author remain live vector/text content. Never flatten dynamic report text into a generated image.

## Chart integrity
Charts are data components, not visual decoration.
- Line charts: x-axis labels and point values are mandatory.
- Bar charts: one clean rounded body per value, subtle shadow only; no segmented caps, horns, split bars, or decorative fake values.
- Unsupported chart types fail the build.
