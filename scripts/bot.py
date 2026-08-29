#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jw.bot.menu import COMMAND_MENU
from jw.bot.runtime import TelegramBot
from jw.config import enabled_notifiers, load_notifiers_config, load_secrets


def _telegram_channel() -> dict:
    for ch in enabled_notifiers(load_notifiers_config()):
        if ch.get("type") == "telegram":
            return ch
    raise SystemExit("No enabled telegram channel in config/notifiers.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="JobWatcher Telegram bot")
    parser.add_argument(
        "--install-menu",
        action="store_true",
        help="Register / commands + bot descriptions, then exit",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Long-poll and answer commands",
    )
    parser.add_argument("--list-commands", action="store_true")
    args = parser.parse_args()

    if args.list_commands:
        for row in COMMAND_MENU:
            print(f"/{row['command']}\t{row['description']}")
        return 0

    if not args.install_menu and not args.poll:
        parser.print_help()
        return 2

    secrets = load_secrets()
    bot = TelegramBot(
        _telegram_channel()["id"],
        _telegram_channel().get("params") or {},
        secrets,
    )
    lang = str((bot.params.get("recipient") or {}).get("language_code") or "en")

    if args.install_menu:
        info = bot.install_menu(language_code=lang)
        print("Menu installed:")
        for k, v in info.items():
            print(f"  {k}: ok={v.get('ok')}")
        link = bot.params.get("deep_link")
        if link:
            print(f"Open: {link}")

    if args.poll:
        print("Polling… Ctrl+C to stop", flush=True)
        bot.poll_forever(on_error=lambda e: print(f"! {e}", flush=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
