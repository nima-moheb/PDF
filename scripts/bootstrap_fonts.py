"""Prepare approved font assets for Nima Report Engine.

Persian production is offline-first: Vazirmatn is vendored under the SIL OFL and
materialized from the package without network access. IBM Plex remains an optional
best-effort enhancement because the renderer has approved local/system fallbacks.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from reportkit.visual_v05 import _ensure_bundled_vazirmatn, _font_has_required_persian

OUT = Path(
    os.environ.get(
        "REPORTKIT_FONT_DIR",
        Path.home() / ".cache" / "nima-report-engine" / "fonts",
    )
).expanduser()
OUT.mkdir(parents=True, exist_ok=True)

# Required Persian faces: never depend on DNS/network.
vazir = _ensure_bundled_vazirmatn()
for weight, path in sorted(vazir.items()):
    if not _font_has_required_persian(path):
        raise RuntimeError(f"Bundled Vazirmatn {weight} failed glyph validation: {path}")
    print("OK", path.name, "(bundled/offline)")

# Optional Latin faces. Failure here is non-fatal because the engine can use
# approved installed/system Latin fallbacks.
PLEX_COMMIT = "78cd4223d8de9fcb78cba84eadecb269c56093c5"
PLEX = {
    "IBMPlexSans-Regular.ttf": (
        f"https://raw.githubusercontent.com/IBM/plex/{PLEX_COMMIT}/"
        "packages/plex-sans/fonts/complete/ttf/IBMPlexSans-Regular.ttf"
    ),
    "IBMPlexSans-Bold.ttf": (
        f"https://raw.githubusercontent.com/IBM/plex/{PLEX_COMMIT}/"
        "packages/plex-sans/fonts/complete/ttf/IBMPlexSans-Bold.ttf"
    ),
}
for name, url in PLEX.items():
    dst = OUT / name
    if dst.exists() and dst.stat().st_size > 50000:
        print("OK", name)
        continue
    try:
        print("OPTIONAL GET", name)
        with urlopen(url, timeout=12) as r:
            data = r.read()
        if len(data) < 50000:
            raise RuntimeError(f"Downloaded font too small: {name}")
        dst.write_bytes(data)
        print("OK", name)
    except (URLError, OSError, RuntimeError) as exc:
        print(f"WARN {name}: network unavailable; approved Latin fallback will be used ({exc})")

print("Required Persian fonts ready offline:", OUT)
