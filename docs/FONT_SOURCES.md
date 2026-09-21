# Font Sources

Font binaries are not committed. Run `python scripts/bootstrap_fonts.py` once in a networked environment.

- Vazirmatn: `rastikerdar/vazirmatn`, pinned to commit `6e553e33489a8f9dfaccc76860a2e3f3c1e66de7` (SIL Open Font License).
- IBM Plex Sans: `IBM/plex`, pinned to commit `78cd4223d8de9fcb78cba84eadecb269c56093c5` (SIL Open Font License).

The engine first checks `assets/fonts/`, then known runtime/system fallbacks.
