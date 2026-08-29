from __future__ import annotations

from typing import Any

from jw.bot.menu import COMMAND_MENU
from jw.bot.prefs import is_muted, load_recent, set_muted
from jw.config import enabled_sources, load_filters, load_sources_config
from jw.state import load_state


def _clip(items: list[str], n: int = 8) -> str:
    if not items:
        return "—"
    head = items[:n]
    more = len(items) - len(head)
    text = ", ".join(head)
    if more > 0:
        text += f" (+{more})"
    return text


def handle_start(ctx: dict[str, Any]) -> dict[str, Any]:
    from jw.webapp.link import start_keyboard

    name = ctx.get("first_name") or "there"
    muted = "paused" if is_muted() else "on"
    text = (
        f"Hi {name} — I'm your job watcher.\n\n"
        "I scan careers pages and boards, then message you only when "
        "something new matches your filters.\n\n"
        f"Alerts are currently: {muted}\n"
        "Open Catalog for filters & history, or use the menu (/)."
    )
    return {"text": text, "reply_markup": start_keyboard()}


def handle_help(_ctx: dict[str, Any]) -> dict[str, Any]:
    lines = ["Here's what I can do:", ""]
    for row in COMMAND_MENU:
        lines.append(f"/{row['command']} — {row['description']}")
    lines += [
        "",
        "Tips:",
        "• Alerts only go to your linked chat",
        "• /desk opens the Catalog Web App (or tailnet fallback)",
        "• /mute if you're busy; /unmute when ready",
    ]
    return {"text": "\n".join(lines)}


def handle_status(_ctx: dict[str, Any]) -> dict[str, Any]:
    state = load_state()
    sources = state.get("sources") or {}
    muted = is_muted()
    lines = [
        "Watcher status",
        f"Alerts: {'paused 🔇' if muted else 'active 🔔'}",
        f"Tracked sources: {len(sources)}",
        "",
    ]
    if not sources:
        lines.append("No runs yet. Seed or watch once to populate status.")
        return {"text": "\n".join(lines)}

    rows = sorted(
        sources.items(),
        key=lambda kv: str((kv[1] or {}).get("last_check") or ""),
        reverse=True,
    )
    for sid, entry in rows[:12]:
        entry = entry or {}
        check = str(entry.get("last_check") or "—")[:19].replace("T", " ")
        fetch_n = entry.get("last_fetch_count", "—")
        match_n = entry.get("last_match_count", "—")
        init = "yes" if entry.get("initialized") else "no"
        lines.append(
            f"• {sid}: check {check} UTC | fetch {fetch_n} | match {match_n} | seeded {init}"
        )
    if len(rows) > 12:
        lines.append(f"…and {len(rows) - 12} more")
    return {"text": "\n".join(lines)}


def handle_filters(_ctx: dict[str, Any]) -> dict[str, Any]:
    f = load_filters()
    lines = [
        "Your match rules",
        "",
        f"Title any: {_clip(f.get('title_any') or [], 6)}",
        f"Keywords: {_clip(f.get('keywords_any') or [], 8)}",
        f"Locations: {_clip(f.get('locations_any') or [], 8)}",
        f"Title exclude: {_clip(f.get('title_exclude') or [], 5)}",
        f"Keyword exclude: {_clip(f.get('keywords_exclude') or [], 5)}",
        f"Max age (days): {f.get('max_days_old', '—')}",
        f"Max per source: {f.get('max_per_source', '—')}",
    ]
    return {"text": "\n".join(lines)}


def handle_sources(_ctx: dict[str, Any]) -> dict[str, Any]:
    cfg = load_sources_config()
    filters = load_filters()
    rows = enabled_sources(cfg, filters)
    lines = [f"Watching {len(rows)} sources", ""]
    by_type: dict[str, list[str]] = {}
    for s in rows:
        by_type.setdefault(str(s.get("type") or "?"), []).append(str(s.get("id")))
    for t, ids in sorted(by_type.items()):
        lines.append(f"{t}: {_clip(ids, 10)}")
    return {"text": "\n".join(lines)}


def handle_latest(_ctx: dict[str, Any]) -> dict[str, Any]:
    jobs = load_recent()
    if not jobs:
        return {
            "text": (
                "No jobs in history yet.\n"
                "I'll fill this after the next scheduled scan "
                "(11:00 & 19:30 IST), or when something new matches."
            )
        }
    lines = [f"Latest matches ({min(8, len(jobs))} of {len(jobs)})", ""]
    for i, j in enumerate(jobs[:8], start=1):
        lines.append(f"{i}. [{j.get('company')}] {j.get('title')}")
        loc = j.get("location") or ""
        if loc:
            lines.append(f"  {loc}")
        if j.get("url"):
            lines.append(f"  {j['url']}")
        lines.append("")
    return {"text": "\n".join(lines).strip()}


def handle_mute(_ctx: dict[str, Any]) -> dict[str, Any]:
    set_muted(True)
    return {
        "text": "Alerts paused. I won't ping you until you /unmute.\nWatcher can still run in the background."
    }


def handle_unmute(_ctx: dict[str, Any]) -> dict[str, Any]:
    set_muted(False)
    return {"text": "Alerts are on again. New matches will ping this chat."}


def handle_desk(_ctx: dict[str, Any]) -> dict[str, Any]:
    import hashlib
    import hmac
    from datetime import datetime, timezone

    from jw.config import load_secrets
    from jw.webapp.link import (
        allowed_chat_id,
        catalog_open_keyboard,
        same_host_catalog_url,
        web_app_url,
    )

    secrets = load_secrets()
    app = web_app_url(secrets)
    if app:
        return {
            "text": (
                "Phosphor Catalog Web App\n"
                "Opens inside Telegram — signed in as you automatically."
            ),
            "reply_markup": catalog_open_keyboard(prefer_webapp=True),
        }

    # Same-host / tailnet fallback until WEB_APP_URL (HTTPS) is set
    secret = (
        secrets.get("WEB_UI_SECRET")
        or secrets.get("WEB_UI_TOKEN")
        or secrets.get("ALERT_TELEGRAM_BOT_TOKEN")
        or ""
    )
    chat = allowed_chat_id(secrets)
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    token = hmac.new(
        secret.encode(), f"{chat}:{day}".encode(), hashlib.sha256
    ).hexdigest()[:28]
    base = same_host_catalog_url(secrets)
    if not base:
        return {
            "text": (
                "Catalog is not linked yet.\n"
                "Set WEB_APP_URL (HTTPS Mini App) or WEB_UI_HOST for same-host access."
            )
        }
    url = f"{base}/?k={token}"
    return {
        "text": (
            "Catalog (same-host / tailnet fallback)\n"
            "Set WEB_APP_URL to an HTTPS address to use the real Telegram Web App.\n\n"
            f"{url}"
        ),
        "reply_markup": {
            "inline_keyboard": [[{"text": "Open catalog", "url": url}]]
        },
    }


HANDLERS = {
    "start": handle_start,
    "help": handle_help,
    "desk": handle_desk,
    "status": handle_status,
    "filters": handle_filters,
    "sources": handle_sources,
    "latest": handle_latest,
    "mute": handle_mute,
    "unmute": handle_unmute,
}


def dispatch_command(name: str, ctx: dict[str, Any]) -> dict[str, Any]:
    key = (name or "").lower().strip()
    fn = HANDLERS.get(key)
    if not fn:
        return {
            "text": (
                "I don't know that command.\n"
                "Try /help or open the menu for the full list."
            )
        }
    return fn(ctx)
