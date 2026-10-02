# Bundled font sources

Version 0.7 ships static TTF files in `reportkit/data/fonts/`; they are also included in the wheel. Generation requires no font downloads. The directory contains the upstream licenses and a byte/hash manifest.

- Vazirmatn Regular, Medium, Bold: [rastikerdar/vazirmatn](https://github.com/rastikerdar/vazirmatn/tree/6e553e33489a8f9dfaccc76860a2e3f3c1e66de7), `fonts/ttf/`; SIL OFL 1.1, `Vazirmatn-OFL.txt`.
- IBM Plex Sans Regular, Bold: [IBM/plex](https://github.com/IBM/plex/tree/78cd4223d8de9fcb78cba84eadecb269c56093c5), `packages/plex-sans/fonts/complete/ttf/`; SIL OFL 1.1, `IBMPlex-OFL.txt`.

`REPORTKIT_FONT_DIR` is an explicit maintainer override for these filenames. Missing override files fall back to the package; invalid fonts fail. Persian faces must identify as Vazirmatn and provide the required glyph coverage. A changed font fingerprint invalidates page reuse, including within a long-lived Python process.

`scripts/bootstrap_fonts.py` remains as a compatibility check; it does not fetch anything. Update bundled fonts deliberately, retain licenses, update their SHA-256 manifest, and run rendered regressions.
