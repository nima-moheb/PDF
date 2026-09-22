# Approved Page Archetypes

- `cover`: title, subtitle, eyebrow, one of five production cover variants, direction, and showcase-only palette override.
- `summary`: substantive editorial intro + 1-4 genuine value cards. Values cannot be blank.
- `text`: structured heading/text/bullet groups; groups expand across the available body.
- `cards`: 1-6 semantic cards with optional `layout: auto|grid|bands|feature`; `auto` is preferred.
- `chart_text`: validated line/bar data + analysis + optional source.
- `comparison`: up to three comparable semantic items; ordering mirrors automatically in RTL.
- `table`: 2-6 columns; cells wrap, RTL columns mirror, and substantial multi-row tables use balanced row expansion.
- `image_text`: required real evidence image + explanation; relative paths resolve from report JSON.
- `timeline`: up to six steps with body-aware card sizing and RTL rail mirroring.
- `sources`: compact source cards/list; intentionally not stretched to fill the page.
- `closing`: final statement + Nima identity and clickable visible resume URL.

The schema rejects arbitrary geometry/style controls. The renderer rejects empty summary values, clipped/overflowing content, sparse compositions, missing approved fonts and malformed runtime assets.
