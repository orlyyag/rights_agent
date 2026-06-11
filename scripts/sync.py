"""Update automation entrypoint (Brick 5): manifest-diff → blue-green → flip.

Run (from repo root):
    PYTHONPATH=.:src python scripts/sync.py              # sync he (default)
    PYTHONPATH=.:src python scripts/sync.py he ru        # sync both langs
    PYTHONPATH=.:src python scripts/sync.py --no-flip    # build but don't flip

Scheduled run (PLAN banked default — demonstrate automation, not a daemon):
    crontab -e   # nightly at 03:30
    30 3 * * * cd /path/to/rights_agent && PYTHONPATH=.:src .venv/bin/python scripts/sync.py >> data/sync.log 2>&1

DoD (§2): change a page on the wiki → run sync → the bot's next answer reflects
it, no restart (per-request active pointer, R7).
"""
from __future__ import annotations

import argparse
import sys
import time

from ingest import sync as sync_mod


def cli() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("langs", nargs="*", default=["he"], choices=["he", "ru"],
                    help="languages to sync (default: he)")
    ap.add_argument("--no-flip", action="store_true",
                    help="build the new collection but don't flip the pointer")
    args = ap.parse_args()

    t0 = time.monotonic()
    res = sync_mod.sync(tuple(dict.fromkeys(args.langs)), flip=not args.no_flip)
    mins = (time.monotonic() - t0) / 60

    if res.noop:
        print(f"\nNo-op in {mins:.1f} min — nothing changed upstream.")
    else:
        print(f"\nDone in {mins:.1f} min: copied {res.copied}, "
              f"embedded {res.embedded} → '{res.new_collection}' "
              f"(flipped: {res.flipped}).")


if __name__ == "__main__":
    sys.exit(cli())
