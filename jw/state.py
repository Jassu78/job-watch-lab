from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from jw.config import STATE_PATH
from jw.models import utc_now

MAX_SEEN = 8000


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text())
    return {"sources": {}}


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")
    path.chmod(0o600)


def _as_ordered(ids: list[str]) -> OrderedDict[str, None]:
    od: OrderedDict[str, None] = OrderedDict()
    for jid in ids:
        if jid not in od:
            od[jid] = None
    return od


def update_seen(
    entry: dict[str, Any],
    *,
    fetched_ids: list[str],
    match_count: int,
    fetch_count: int,
    seed: bool,
) -> None:
    od = _as_ordered(list(entry.get("seen_ids") or []))
    if seed or not entry.get("initialized"):
        for jid in fetched_ids:
            od[jid] = None
            od.move_to_end(jid)
        entry["initialized"] = True
    else:
        for jid in fetched_ids:
            if jid in od:
                od.move_to_end(jid)
            else:
                od[jid] = None
    while len(od) > MAX_SEEN:
        od.popitem(last=False)
    entry["seen_ids"] = list(od.keys())
    entry["last_check"] = utc_now().isoformat()
    entry["last_fetch_count"] = fetch_count
    entry["last_match_count"] = match_count


def new_matches(
    entry: dict[str, Any], matched: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    seen = set(entry.get("seen_ids") or [])
    return [j for j in matched if j["id"] not in seen]
