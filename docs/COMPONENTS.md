# Approved Page Archetypes

- `cover`: title, subtitle, eyebrow, one of five approved cover variants, direction, and (showcase mode only) an approved palette override.
- `summary`: intro + 1-4 metric cards.
- `text`: structured heading/text/bullet blocks with measured group height.
- `cards`: up to six semantic information cards.
- `chart_text`: validated line/bar data plus bounded analysis and optional source.
- `comparison`: up to three comparable semantic items.
- `table`: 2-6 engine-sized columns; rows wrap and grow deterministically rather than truncate.
- `image_text`: required real image + explanation; relative asset paths resolve from report JSON.
- `timeline`: up to six ordered steps.
- `sources`: designed source cards/list.
- `closing`: final statement + Nima identity and clickable resume.

The strict schema rejects x/y coordinates, font sizes, margins, colors, per-card accents, table widths, custom footer/header geometry, unsupported chart types, and arbitrary extra fields.
