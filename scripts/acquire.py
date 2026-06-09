"""Run the pipeline acquire step from the shell.

Usage (from repo root):
    PYTHONPATH=.:src python scripts/acquire.py he              # full HE crawl (~2h)
    PYTHONPATH=.:src python scripts/acquire.py he --limit 50   # small validation run
    PYTHONPATH=.:src python scripts/acquire.py ru              # Russian (brick 2)

Resumable — Ctrl-C is safe; rerun continues from where it stopped.
"""
from __future__ import annotations

import argparse
import sys

from ingest import acquire, mediawiki


def main() -> None:
    ap = argparse.ArgumentParser(description="Acquire KZ pages to the raw layer.")
    ap.add_argument("lang", choices=["he", "ru"], help="language wiki to crawl")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap manifest enumeration (None = full)")
    ap.add_argument("--interval", type=float, default=1.0,
                    help="seconds between API calls (WAF-safe default 1.0)")
    args = ap.parse_args()

    client = mediawiki.MediaWikiClient(args.lang, request_interval_s=args.interval)
    print(f"Acquiring {args.lang} — limit={args.limit or 'full'}, "
          f"interval={args.interval}s/req", flush=True)
    diff = acquire.acquire(args.lang, client=client, manifest_limit=args.limit)
    print(f"\nDone. added={len(diff.added)} changed={len(diff.changed)} "
          f"deleted={len(diff.deleted)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
