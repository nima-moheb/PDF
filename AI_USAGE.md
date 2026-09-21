# AI Usage Contract

This repository is a report compiler. The AI supplies structured content; the engine owns layout.

## Absolute rules
- A generated PDF is always a finished deliverable for another human.
- Never include TODO, draft watermark, internal note, manager/CEO note, debug text, placeholder text, prompt text, reasoning, generator commentary, or instructions to Nima.
- Do not invent coordinates, font sizes, margins, colors, header/footer geometry, or chart styling in report JSON.
- Select approved archetypes and provide content only.
- If content does not fit, treat the build error as feedback: shorten without losing meaning, split/expand into another page, or select another approved archetype. Never silently shrink normal text into unreadability.
- A missing evidence/screenshot asset is a build failure. Never substitute decorative fake evidence.
- Page 1 has no visible page number. Pages 2+ use deterministic header/footer components.
- When revising one page, use `--only <page-id>` and verify unaffected page hashes are unchanged.

## Visual identity
- A4 portrait, Modern Digital.
- Technical grid, controlled gradients/glow, rounded depth, strong hierarchy.
- Theme variants: blue, green, purple, orange, red, graphite. Default: blue.
- Latin: IBM Plex Sans. Persian: Vazirmatn where bootstrapped.
- Mixed Persian/English/numbers/URLs must render correctly.
- Personal identity: Nima Moheb. Resume: https://nima-moheb.github.io/myCV/

## Approved archetypes
`cover`, `summary`, `text`, `cards`, `chart_text`, `comparison`, `table`, `image_text`, `timeline`, `sources`, `closing`.
