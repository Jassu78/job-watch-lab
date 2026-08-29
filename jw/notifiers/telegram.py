from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from jw.notifiers.base import Notifier
from jw.notifiers.registry import register

TELEGRAM_LIMIT = 4000
API = "https://api.telegram.org"


@register
class TelegramNotifier(Notifier):
    type_name = "telegram"

    def _token(self) -> str:
        return (
            self.secrets.get("ALERT_TELEGRAM_BOT_TOKEN")
            or self.secrets.get("TELEGRAM_BOT_TOKEN")
            or str(self.params.get("token") or "")
        ).strip()

    def _allowed_chats(self) -> list[str]:
        raw = self.params.get("allow_only") or self.params.get("chat_ids") or []
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.split(",") if x.strip()]
        allowed = [str(x).strip() for x in raw if str(x).strip()]
        secret_chats = [
            x.strip()
            for x in self.secrets.get("ALERT_TELEGRAM_CHAT_IDS", "").split(",")
            if x.strip()
        ]
        if secret_chats and allowed:
            allow = set(allowed)
            return [c for c in secret_chats if c in allow]
        if secret_chats:
            return secret_chats
        return allowed

    def ready(self) -> tuple[bool, str]:
        if not self._token():
            return False, "missing bot token"
        if not self._allowed_chats():
            return False, "no allowlisted chat ids"
        return True, "ok"

    def _api(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = self._token()
        data = urllib.parse.urlencode(payload).encode()
        req = urllib.request.Request(
            f"{API}/bot{token}/{method}",
            data=data,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Telegram HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Telegram network error: {e}") from e

    def send(self, text: str) -> bool:
        ok_ready, reason = self.ready()
        if not ok_ready:
            raise RuntimeError(reason)
        chunk = text[:TELEGRAM_LIMIT]
        ok = True
        for chat_id in self._allowed_chats():
            result = self._api(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": "true",
                },
            )
            if not result.get("ok"):
                ok = False
        return ok

    def ping(self, note: str = "Job watch notifier ready.") -> dict[str, Any]:
        recipient = self.params.get("recipient") or {}
        name = " ".join(
            str(recipient.get(k) or "").strip()
            for k in ("first_name", "last_name")
            if recipient.get(k)
        ).strip() or "there"
        lang = str(recipient.get("language_code") or "en")
        text = f"✅ {note}\nHi {name} ({lang}). This chat is linked for job alerts only."
        self.send(text)
        return {
            "chats": self._allowed_chats(),
            "recipient": recipient,
        }
