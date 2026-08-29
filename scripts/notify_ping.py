#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jw.config import enabled_notifiers, load_notifiers_config, load_secrets
from jw.notifiers.registry import get_notifier, list_types


def main() -> int:
    parser = argparse.ArgumentParser(description="Ping configured notifiers")
    parser.add_argument("--only", default="", help="channel id or type")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--message", default="Job watch notifier ready.")
    args = parser.parse_args()

    if args.list:
        print("types:", ", ".join(list_types()))
        for ch in enabled_notifiers(load_notifiers_config()):
            print(f"- {ch.get('id')} type={ch.get('type')} enabled={ch.get('enabled', True)}")
            params = ch.get("params") or {}
            if params.get("deep_link"):
                print(f"  link: {params['deep_link']}")
            rec = params.get("recipient") or {}
            if rec:
                print(
                    f"  recipient: {rec.get('first_name')} {rec.get('last_name')} "
                    f"id={rec.get('id')} lang={rec.get('language_code')}"
                )
        return 0

    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    secrets = load_secrets()
    channels = enabled_notifiers(load_notifiers_config(), only=only)
    if not channels:
        print("No notifier channels configured.")
        return 1

    failed = 0
    for ch in channels:
        n = get_notifier(ch, secrets)
        ready, reason = n.ready()
        if not ready:
            print(f"{ch.get('id')}: not ready ({reason})")
            failed += 1
            continue
        try:
            if hasattr(n, "ping"):
                info = n.ping(args.message)
            else:
                n.send(args.message)
                info = {}
            link = (ch.get("params") or {}).get("deep_link")
            print(f"{ch.get('id')}: ok {info}")
            if link:
                print(f"  bot: {link}")
        except Exception as e:
            print(f"{ch.get('id')}: FAIL {e}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
