# Visual System - Modern Digital

## Intent

One variable human-facing report system. The AI chooses semantics; the renderer owns geometry, typography, responsive A4 composition, RTL mirroring and final-output verification.

## Fixed visual language

- A4 portrait.
- Modern Digital: restrained technical grid, asymmetric accents, rounded depth, strong hierarchy.
- Approved covers: `signal-orbit`, `glass-panel`, `aurora-strata`, `constellation`, `editorial-split`; all support RTL.
- Pages 2+ use engine-owned navigation/footer chrome.
- Interior components should occupy the page deliberately. Large dead lower areas are a composition defect, not harmless whitespace.
- Source/citation pages are the exception: citations remain compact instead of being artificially stretched.

## Typography

- Latin: IBM Plex Sans Regular/Bold.
- Persian: Vazirmatn Regular/Medium/Bold.
- No production Persian fallback. Missing Vazirmatn is a hard setup failure.
- English editorial paragraphs may use measured justification; the last line remains ragged naturally and over-wide word gaps fall back to left alignment.
- Persian copy is normalized before shaping and must be supplied in logical Unicode order without manual bidi controls.
- ZWNJ is preserved; BOM, soft-hyphen, LRM/RLM and bidi override/isolate artifacts are stripped.
- Paragraph wrapping includes last-line orphan control so a single stranded word is avoided when a safe rebalance exists.

## RTL system

Persian is not a translated LTR layout. Page-title markers/navigation accents, footer identity, card order, comparison columns, table columns and timeline rails mirror automatically. Mixed Latin acronyms are isolated where needed; Persian cover titles ending in short acronyms such as `CRM` render the acronym as a separate controlled badge.

## Interior composition v0.5

- Summary pages use a full-width editorial lead and proportionate value cards; genuine numeric metrics are large and centered.
- Text-group cards share the available content body rather than stopping after a small fixed height.
- `cards` supports deterministic `auto`, `grid`, `bands`, and `feature` compositions so long reports do not look like one repeated template.
- Comparisons mirror in RTL and use the vertical body intentionally.
- Multi-row tables distribute moderate spare height across rows; tiny tables remain compact and should be combined with related content instead of stretched absurdly.
- Timelines calculate card height from available body height and verify each item stays inside its card.
- Chart pages anchor the chart directly below the title and keep analysis attached to it.
- Source cards stay compact.

## Cover selection

- `signal-orbit`: technical/data/engineering
- `glass-panel`: executive/business/client
- `aurora-strata`: innovation/AI/product
- `constellation`: strategy/research/connected evidence
- `editorial-split`: formal/document-heavy/legal/finance

Persian/RTL cover identity renders `نیما محب`.
