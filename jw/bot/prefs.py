from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jw.config import STATE_DIR
from jw.models import utc_now

PREFS_PATH = STATE_DIR / "bot_prefs.json"
RECENT_PATH = STATE_DIR / "recent_alerts.json"
MAX_RECENT = 40


def load_prefs(path: Path = PREFS_PATH) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text())
    return {"muted": False}


def save_prefs(prefs: dict[str, Any], path: Path = PREFS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prefs["updated_at"] = utc_now().isoformat()
    path.write_text(json.dumps(prefs, indent=2) + "\n")
    path.chmod(0o600)


def is_muted() -> bool:
    return bool(load_prefs().get("muted"))


def set_muted(muted: bool) -> dict[str, Any]:
    prefs = load_prefs()
    prefs["muted"] = bool(muted)
    save_prefs(prefs)
    return prefs


def load_recent(path: Path = RECENT_PATH) -> list[dict[str, Any]]:
    if path.is_file():
        data = json.loads(path.read_text())
        return list(data.get("jobs") or [])
    return []


def push_recent(
    jobs: list[dict[str, Any]],
    *,
    source_id: str,
    path: Path = RECENT_PATH,
) -> None:
    if not jobs:
        return
    existing = load_recent(path)
    stamp = utc_now().isoformat()
    incoming = []
    for j in jobs:
        row = {
            "id": j.get("id"),
            "source_id": source_id,
            "company": j.get("company"),
            "title": j.get("title"),
            "url": j.get("url"),
            "location": j.get("location") or j.get("meta") or "",
            "saved_at": stamp,
        }
        incoming.append(row)
    merged = incoming + [
        x for x in existing if x.get("id") not in {r["id"] for r in incoming}
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"jobs": merged[:MAX_RECENT], "updated_at": stamp}, indent=2) + "\n"
    )
    path.chmod(0o600)
