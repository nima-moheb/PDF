from __future__ import annotations

import argparse
from reportkit import build


def main():
    ap = argparse.ArgumentParser(description="Compile structured report JSON into deterministic A4 PDF page artifacts.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--only", action="append", default=[], help="Re-render this page id; unsafe/global changes automatically invalidate surgical reuse.")
    ap.add_argument("--no-qa", action="store_true", help="Skip rendered-page QA (intended only for debugging).")
    args = ap.parse_args()
    build(args.input, args.output, only_ids=set(args.only) if args.only else None, run_qa=not args.no_qa)


if __name__ == "__main__":
    main()
