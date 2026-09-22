# Font Sources

Production font binaries are intentionally not committed.

Run `python scripts/bootstrap_fonts.py` to fetch the approved pinned revisions into `~/.cache/nima-report-engine/fonts` by default, or point `REPORTKIT_FONT_DIR` at an approved-font directory.

- Vazirmatn: pinned `rastikerdar/vazirmatn` revision in `scripts/bootstrap_fonts.py`.
- IBM Plex Sans: pinned `IBM/plex` revision in `scripts/bootstrap_fonts.py`.

v0.5 treats these as required production dependencies. The renderer no longer falls back to Noto/DejaVu for a client-facing PDF; missing approved fonts raise `FONT_SETUP_FAIL` so typography problems are caught before delivery.
