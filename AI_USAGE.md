# Chat entry point — Nima Report Engine 0.7

Use this file and one matching example. Routine report generation does **not** require reading renderer source, all design documents, old reports, or the test suite.

## From a conversation to a report

1. Use the current conversation's approved content and facts. Identify the recipient, purpose, language, required sections/patterns, prices/currency, and any exact wording. Ask only for a missing fact that would materially change the report. Never invent a price, result, date, or commitment.
2. Start from `examples/quick_report_fa.json`, `quick_report_en.json`, or `quick_report_es.json`. Replace the demonstration content completely. Use `client_report.json` only for additional archetype examples.
3. Set `meta.language` to `fa`, `en`, or `es`. The chat writes/translates the content; the engine localizes the chrome. Other languages require renderer/font verification before delivery. Set `meta.recipient` to the intended reader. Omit an unknown date instead of leaving a visible empty field.
4. Keep content in semantic JSON. Choose page archetypes below and stable descriptive IDs. The engine owns coordinates, typography, colors, margins and fit. Preserve approved amounts, qualifiers, names and claims.
5. Put non-negotiable page IDs and wording in `requirements`. Use `protected_values` for exact **whole field** values such as a price string or approved phrase. They prevent later edits from silently changing these values. Deliberate user changes to protected content require updating the relevant requirement in a full build.
6. Run the build command. It validates content, renders, preflights and verifies the final PDF. Inspect the PNGs in the returned `qa` directory. For a local edit, inspect the changed pages; unchanged accepted pages are verified by hashes.
7. Deliver the PDF through the chat's file-delivery mechanism. Persist the editable `.build` folder (or a packed ZIP) with it so another chat can perform a real page correction. An exported PDF alone does not contain the semantic source. Do not commit private client reports to this public repository.

## Commands

From a checkout of current `main`, with Python 3.11+ and the declared dependencies installed:

```bash
python -m pip install -e .
python -m reportkit build examples/quick_report_fa.json output/example-fa.pdf
```

Fonts ship with the package. There is no font bootstrap, browser, API key, font-download step, or GitHub Actions run in routine generation. Reuse a working environment; install only if needed. `python -m reportkit doctor` checks versions and fonts when the environment is uncertain.

Replace the example path with the actual authored report JSON. A successful command prints the PDF, editable source, PNG directory, changed/reused pages and measured build time. This duration excludes the chat's research and content-writing time. All fields in supplied examples are real, buildable demonstration data, **not** client facts.

```bash
python -m reportkit validate report.json
python -m reportkit build report.json output/report.pdf
python -m reportkit verify output/report.pdf --config report.json
python -m reportkit inspect output/report.pdf
python -m reportkit pack output/report.pdf output/report-editable.zip
```

## “Change page two”

Read `output/report.build/source.json` or run `inspect` to find page two's stable ID. Write a complete replacement **page object** to `replacement-page.json`, retaining that ID and the approved content not being changed. Then:

```bash
python -m reportkit edit output/report.pdf --page 2 --replacement replacement-page.json
```

Page numbers mean PDF viewer numbers, including the cover. A stable ID also works with `--page`. This command changes the saved semantic source only after the new PDF passes every gate. It rejects stale edits, changed shared dependencies, and any unrequested changed page. Untouched page PDFs and their verified PNGs remain byte-identical. There is no manual PDF patching or layout surgery.

For intentional changes to recipient, theme, language, requirements, page count/order, or the engine version, edit the whole source and run `build`. It reports which pages it rebuilt. `build --only page-id` preserves the older automatic-expansion behavior; `--strict-only` makes this restriction a hard boundary.

## Select content by purpose

| Archetype | Use and content |
|---|---|
| `cover` | One title/subtitle and approved `variant`; first page, no number. |
| `summary` | Supported narrative plus 1–4 meaningful metrics. |
| `text` | Heading/text/bullets grouped into an explanation. |
| `cards` | Up to six distinct ideas. |
| `chart_text` | Real line/bar data with labels, analysis and source. |
| `comparison` | Up to three comparable choices with values/bullets. |
| `table` | 2–6 columns and up to 14 rows; never shorten cells to fit. |
| `pricing` | Explicit currency, item descriptions, quantities, unit prices, optional discount/expected total/note. |
| `image_text` | A real local image and explanation; asset paths are relative to the input JSON. |
| `timeline` | Up to six ordered steps. |
| `sources` | Up to twelve real source descriptions. |
| `closing` | A useful next step and a clickable resume link. |

Use the archetypes relevant to the request. Avoid repetitive cards/text across long reports. A concise report need not be stretched into many pages. A substantive source needs a substantive summary. Do not add unsupported prose merely to fill a page.

Covers: `signal-orbit` for technical/data work; `glass-panel` for executive/client/proposal work; `aurora-strata` for product/innovation; `constellation` for research/strategy; `editorial-split` for formal/document-heavy work. All five support RTL. Choose a palette from blue, green, purple, orange, red, graphite without asking the user to make a routine design choice.

## Pricing and preservation

`pricing` requires decimal **strings**, e.g. `"quantity": "2"`, `"unit_price": "1250.00"`. Currency is explicit: `IRT` means toman, `IRR` means rial, plus `USD`, `EUR`, `GBP`. No implicit rial/toman or exchange conversion. Totals use decimal arithmetic; line totals round half up to the currency's minor unit. Toman/rial use whole units. An `expected_total` mismatch fails. No tax or fee is invented; agreed terms belong in the note, and complex tax calculations require an explicit supported model rather than silently assuming one.

```json
"requirements": {
  "required_page_ids": ["pricing"],
  "required_text": ["API فروشگاه"],
  "forbidden_text": ["unapproved claim"],
  "protected_values": [{"page_id": "pricing", "value": "25000000"}]
}
```

Requirements validate the authored source and the final PDF is bound to that source's digest. They cannot prove that a factual claim is true or that a summary is relevant. The chat must still verify facts and review the content.

## Failure handling

- `FIT_FAIL`: names the page and component. Recompose or split while preserving meaning. Do not slice strings, delete qualifiers, shrink the whole PDF, or edit exported PDF bytes.
- `PRICE_FAIL` / `REQUIREMENT_FAIL`: correct the source against approved facts; never remove a guard merely to make a build pass.
- `GLYPH_FAIL`: use supported typography/text or extend and verify the font pipeline; never ship missing squares.
- `SURGERY_FAIL` / `EDIT_CONFLICT`: the accepted baseline has changed. Inspect the precise change and use a full build only when that broader change is intended.
- Failed builds preserve the previous accepted PDF and bundle. Debug `--preview` output is marked as such and fails delivery verification. Never deliver it.

Persian uses bundled Vazirmatn, RTL chrome/column order and Persian page counters. ZWNJ participates in shaping and is removed from final glyph runs. Nima's Persian author name is «نیما محب». Intentional Latin terms, URLs, versions and exact values remain intact. No Naskh or system-font substitution.
