# Font Sources

`python scripts/bootstrap_fonts.py` fetches pinned upstream font revisions into `~/.cache/nima-report-engine/fonts` by default (or `REPORTKIT_FONT_DIR`). Font binaries are intentionally not committed.

- Vazirmatn: pinned repository commit in `scripts/bootstrap_fonts.py`.
- IBM Plex Sans: pinned repository commit in `scripts/bootstrap_fonts.py`.

## Offline production source

As of v0.6.2, the package vendors a Vazirmatn variable WOFF2 asset for offline Persian generation under the SIL Open Font License. The license is stored at `reportkit/data/OFL-Vazirmatn.txt`.

Static Regular/Medium/Bold TTFs are generated into the runtime cache from this bundled asset; they are not committed as generated cache artifacts. The original pinned upstream TTF URLs remain historical/reference sources only, not a required runtime dependency.
