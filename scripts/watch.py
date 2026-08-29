#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jw.config import enabled_sources, load_filters, load_secrets, load_sources_config
from jw.pipeline import run_all


def main() -> int:
    parser = argparse.ArgumentParser(description="Local job watch")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--reset-state", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        mode = "dry-run"
    elif args.seed:
        mode = "seed"
    else:
        mode = "watch"

    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    cfg = load_sources_config()
    filters = load_filters()
    secrets = load_secrets()
    sources = enabled_sources(cfg, filters, only=only)
    return run_all(
        sources,
        filters,
        secrets,
        mode=mode,
        notify=args.notify,
        reset_state=args.reset_state,
    )


if __name__ == "__main__":
    raise SystemExit(main())
