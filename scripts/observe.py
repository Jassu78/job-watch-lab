#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jw.config import NOTES_DIR, enabled_sources, load_filters, load_secrets, load_sources_config
from jw.registry import get_source, list_types


def summarize(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return "…"
    if isinstance(value, dict):
        return {k: summarize(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        if not value:
            return []
        return [summarize(value[0], depth + 1), f"…(+{len(value) - 1} more)"]
    if isinstance(value, str) and len(value) > 120:
        return value[:120] + "…"
    return value


def write_note(source: dict[str, Any], observed: dict[str, Any], fetch_count: int | None, err: str | None) -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"{source['id']}.md"
    lines = [
        f"# {source.get('name', source['id'])}",
        "",
        f"- **id:** `{source['id']}`",
        f"- **type:** `{source.get('type')}`",
        "",
        "## Probe",
        "",
        "```json",
        json.dumps(observed, indent=2, default=str)[:8000],
        "```",
        "",
    ]
    if fetch_count is not None:
        lines += ["## Fetch", "", f"Normalized jobs: **{fetch_count}**", ""]
    if err:
        lines += ["## Error", "", f"```\n{err}\n```", ""]
    path.write_text("\n".join(lines))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe job sources → notes/")
    parser.add_argument("--only", default="")
    parser.add_argument("--list-types", action="store_true")
    args = parser.parse_args()

    if args.list_types:
        print("\n".join(list_types()))
        return 0

    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    cfg = load_sources_config()
    filters = load_filters()
    secrets = load_secrets()
    # observe all configured rows (enabled or not) when --only set; else enabled only
    if only:
        all_rows = list(cfg.get("companies") or []) + list(cfg.get("aggregators") or [])
        sources = [s for s in all_rows if s["id"] in only]
    else:
        sources = enabled_sources(cfg, filters)

    print(f"Observing {len(sources)} sources → {NOTES_DIR}")
    for source in sources:
        sid = source["id"]
        print(f"\n=== {sid} ({source.get('type')}) ===")
        err = None
        observed: dict[str, Any] = {}
        fetch_count = None
        try:
            src = get_source(source, secrets)
            src.prepare(filters)
            observed = src.probe()
            observed = {k: summarize(v) for k, v in observed.items()}
            print(f"  probe keys: {list(observed.keys())}")
        except Exception as e:
            err = traceback.format_exc()
            observed = {"error": str(e)}
            print(f"  PROBE FAIL: {e}")

        try:
            src = get_source(source, secrets)
            src.prepare(filters)
            jobs = src.fetch()
            fetch_count = len(jobs)
            print(f"  fetch: {fetch_count}")
            if jobs:
                print(f"  sample: {jobs[0].get('title')}")
        except Exception as e:
            err = (err or "") + "\n" + traceback.format_exc()
            print(f"  FETCH FAIL: {e}")

        path = write_note(source, observed, fetch_count, err)
        print(f"  wrote {path.name}")

    print(f"\nTypes: {', '.join(list_types())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
