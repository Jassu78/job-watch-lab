from __future__ import annotations

from typing import Any

from jw.config import load_notifiers_config, load_secrets


def allowed_chat_id(secrets: dict[str, str] | None = None) -> str:
    secrets = secrets if secrets is not None else load_secrets()
    chats = [
        x.strip()
        for x in secrets.get("ALERT_TELEGRAM_CHAT_IDS", "").split(",")
        if x.strip()
    ]
    if chats:
        return chats[0]
    for ch in load_notifiers_config().get("channels") or []:
        if ch.get("type") == "telegram":
            ids = (ch.get("params") or {}).get("allow_only") or []
            if ids:
                return str(ids[0])
    return ""


def web_app_url(secrets: dict[str, str] | None = None) -> str:
    """Public HTTPS Mini App URL when set; empty means not configured."""
    secrets = secrets if secrets is not None else load_secrets()
    return (secrets.get("WEB_APP_URL") or secrets.get("TELEGRAM_WEBAPP_URL") or "").strip().rstrip(
        "/"
    )


def same_host_catalog_url(secrets: dict[str, str] | None = None) -> str:
    """Same-machine / tailnet browser URL (optional fallback)."""
    secrets = secrets if secrets is not None else load_secrets()
    explicit = (secrets.get("WEB_UI_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    host = (secrets.get("WEB_UI_HOST") or "").strip()
    port = (secrets.get("WEB_UI_PORT") or "3099").strip()
    if host:
        return f"http://{host}:{port}"
    return ""


def catalog_open_keyboard(*, prefer_webapp: bool = True) -> dict[str, Any] | None:
    secrets = load_secrets()
    app = web_app_url(secrets)
    if prefer_webapp and app:
        return {
            "inline_keyboard": [
                [{"text": "Open catalog", "web_app": {"url": app}}]
            ]
        }
    host_url = same_host_catalog_url(secrets)
    if host_url:
        # Caller may append ?k= ; bare URL still useful behind tailnet auth
        return {
            "inline_keyboard": [[{"text": "Open catalog", "url": host_url}]]
        }
    return None


def start_keyboard() -> dict[str, Any]:
    secrets = load_secrets()
    app = web_app_url(secrets)
    catalog_btn: dict[str, Any]
    if app:
        catalog_btn = {"text": "Open catalog", "web_app": {"url": app}}
    else:
        catalog_btn = {"text": "Open catalog", "callback_data": "cmd:desk"}
    return {
        "inline_keyboard": [
            [catalog_btn, {"text": "Latest jobs", "callback_data": "cmd:latest"}],
            [
                {"text": "Status", "callback_data": "cmd:status"},
                {"text": "Help", "callback_data": "cmd:help"},
            ],
        ]
    }


def menu_button_payload() -> dict[str, Any] | None:
    app = web_app_url()
    if not app:
        return None
    return {
        "menu_button": {
            "type": "web_app",
            "text": "Catalog",
            "web_app": {"url": app},
        }
    }
