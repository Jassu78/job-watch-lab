from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = LAB_ROOT / "config"
NOTES_DIR = LAB_ROOT / "notes"
STATE_DIR = LAB_ROOT / "state"
COMPANIES_PATH = CONFIG_DIR / "companies.json"
FILTERS_PATH = CONFIG_DIR / "filters.json"
NOTIFIERS_PATH = CONFIG_DIR / "notifiers.json"
SECRETS_PATH = CONFIG_DIR / "secrets.env"
STATE_PATH = STATE_DIR / "seen.json"

SECRET_KEYS = (
    "ADZUNA_APP_ID",
    "ADZUNA_APP_KEY",
    "JSEARCH_API_KEY",
    "JSEARCH_BASE_URL",
    "ALERT_TELEGRAM_BOT_TOKEN",
    "ALERT_TELEGRAM_CHAT_IDS",
    "WEB_UI_SECRET",
    "WEB_UI_TOKEN",
    "WEB_UI_HOST",
    "WEB_UI_PORT",
    "WEB_UI_URL",
    "WEB_APP_URL",
    "TELEGRAM_WEBAPP_URL",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_secrets(path: Path = SECRETS_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in SECRET_KEYS:
        if os.environ.get(key):
            env[key] = os.environ[key]
    if not path.is_file():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


def load_sources_config(path: Path = COMPANIES_PATH) -> dict[str, Any]:
    return load_json(path)


def load_filters(path: Path = FILTERS_PATH) -> dict[str, Any]:
    return load_json(path)


def load_notifiers_config(path: Path = NOTIFIERS_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {"channels": []}
    return load_json(path)


def enabled_notifiers(
    cfg: dict[str, Any] | None = None,
    *,
    only: set[str] | None = None,
) -> list[dict[str, Any]]:
    cfg = cfg if cfg is not None else load_notifiers_config()
    out = [c for c in (cfg.get("channels") or []) if c.get("enabled", True)]
    if only:
        out = [c for c in out if c.get("id") in only or c.get("type") in only]
    return out


def enabled_sources(
    cfg: dict[str, Any],
    filters: dict[str, Any],
    *,
    only: set[str] | None = None,
) -> list[dict[str, Any]]:
    flags = filters.get("sources") or {}
    out: list[dict[str, Any]] = []
    if flags.get("companies", True):
        out.extend(s for s in (cfg.get("companies") or []) if s.get("enabled", True))
    if flags.get("aggregators", True):
        out.extend(s for s in (cfg.get("aggregators") or []) if s.get("enabled", True))
    if only:
        out = [s for s in out if s["id"] in only]
    return out
