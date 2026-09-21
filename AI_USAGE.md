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
- Resume: https://nima-moheb.github.io/myCV/ and must be a real PDF URI annotation whenever visibly presented.
