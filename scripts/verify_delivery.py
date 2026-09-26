from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportkit.delivery import verify_delivery


def main():
    ap = argparse.ArgumentParser(
        description="Verify that a PDF is a valid Nima Report Engine deliverable."
    )
    ap.add_argument("pdf")
    ap.add_argument("--config", help="Optional source report JSON used for language detection.")
    args = ap.parse_args()

    try:
        result = verify_delivery(
            args.pdf,
            args.config,
            expected_engine_version=None,
            allow_test_font_fallback=False,
        )
    except Exception as exc:
        print(str(exc))
        raise SystemExit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
