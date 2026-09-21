from __future__ import annotations
import argparse
from reportkit import build


def main():
    ap=argparse.ArgumentParser(description='Compile structured report JSON into deterministic A4 PDF page artifacts.')
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--only', action='append', default=[], help='Re-render only this page id (repeatable); other page artifacts are reused.')
    args=ap.parse_args()
    build(args.input,args.output,only_ids=set(args.only) if args.only else None)

if __name__=='__main__':
    main()
