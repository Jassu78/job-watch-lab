from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from jw.bot.handlers import dispatch_command
from jw.bot.menu import (
    BOT_DESCRIPTION,
    BOT_SHORT_DESCRIPTION,
    COMMAND_MENU,
)
from jw.notifiers.telegram import API, TelegramNotifier


class TelegramBot(TelegramNotifier):
    """Interactive side of the Telegram channel (commands + polling)."""

    def _api_form(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._api(method, payload)

    def _api_json(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = self._token()
        req = urllib.request.Request(
            f"{API}/bot{token}/{method}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"Telegram HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Telegram network error: {e}") from e

    def install_menu(self, *, language_code: str | None = "en") -> dict[str, Any]:
        ok_ready, reason = self.ready()
        if not ok_ready:
            raise RuntimeError(reason)
        results: dict[str, Any] = {}
        # Default scope (all private chats)
        results["commands_default"] = self._api_json(
            "setMyCommands", {"commands": COMMAND_MENU}
        )
        # English-specific (recipient lang)
        if language_code:
            results["commands_en"] = self._api_json(
                "setMyCommands",
                {"commands": COMMAND_MENU, "language_code": language_code},
            )
        # Pin menu to the allowlisted chat only as extra clarity
        for chat_id in self._allowed_chats():
            results[f"commands_chat_{chat_id}"] = self._api_json(
                "setMyCommands",
                {
                    "commands": COMMAND_MENU,
                    "scope": {"type": "chat", "chat_id": int(chat_id)},
                },
            )
        results["description"] = self._api_json(
            "setMyDescription", {"description": BOT_DESCRIPTION}
        )
        results["short_description"] = self._api_json(
            "setMyShortDescription",
            {"short_description": BOT_SHORT_DESCRIPTION},
        )
        from jw.webapp.link import menu_button_payload

        mb = menu_button_payload()
        if mb:
            results["menu_button_default"] = self._api_json("setChatMenuButton", mb)
            for chat_id in self._allowed_chats():
                payload = {
                    "chat_id": int(chat_id),
                    **mb,
                }
                results[f"menu_button_{chat_id}"] = self._api_json(
                    "setChatMenuButton", payload
                )
        else:
            results["menu_button"] = {
                "ok": False,
                "description": "WEB_APP_URL not set — skip Mini App menu button",
            }
        return results

    def reply(
        self,
        chat_id: str | int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if str(chat_id) not in set(self._allowed_chats()):
            raise RuntimeError("chat not allowlisted")
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._api_json("sendMessage", payload)

    def answer_callback(self, callback_id: str, text: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text[:200]
        return self._api_json("answerCallbackQuery", payload)

    def is_allowed_update(self, chat_id: str | int, user: dict[str, Any] | None) -> bool:
        if str(chat_id) not in set(self._allowed_chats()):
            return False
        recipient = self.params.get("recipient") or {}
        want = recipient.get("id")
        if want is None or not user:
            return True
        return int(user.get("id") or 0) == int(want)

    def handle_update(self, update: dict[str, Any]) -> None:
        if "callback_query" in update:
            cq = update["callback_query"]
            msg = cq.get("message") or {}
            chat = msg.get("chat") or {}
            user = cq.get("from") or {}
            chat_id = chat.get("id")
            data = str(cq.get("data") or "")
            self.answer_callback(str(cq.get("id") or ""))
            if not self.is_allowed_update(chat_id, user):
                return
            cmd = data.split("cmd:", 1)[-1] if data.startswith("cmd:") else ""
            ctx = {
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "language_code": user.get("language_code"),
                "chat_id": chat_id,
            }
            out = dispatch_command(cmd, ctx)
            self.reply(chat_id, out["text"], reply_markup=out.get("reply_markup"))
            return

        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        chat = msg.get("chat") or {}
        user = msg.get("from") or {}
        chat_id = chat.get("id")
        text = str(msg.get("text") or "").strip()
        if not text.startswith("/"):
            if self.is_allowed_update(chat_id, user):
                self.reply(
                    chat_id,
                    "Use the menu (/) or /help — I respond to commands, not free text yet.",
                )
            return
        if not self.is_allowed_update(chat_id, user):
            # Soft deny — don't leak that the bot exists for others
            return
        cmd = text[1:].split()[0].split("@", 1)[0].lower()
        ctx = {
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "language_code": user.get("language_code"),
            "chat_id": chat_id,
        }
        out = dispatch_command(cmd, ctx)
        self.reply(chat_id, out["text"], reply_markup=out.get("reply_markup"))

    def poll_forever(
        self,
        *,
        offset: int = 0,
        idle_sleep: float = 0.4,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        ok_ready, reason = self.ready()
        if not ok_ready:
            raise RuntimeError(reason)
        # Drop webhook so getUpdates works
        self._api_json("deleteWebhook", {"drop_pending_updates": False})
        while True:
            try:
                data = self._api_json(
                    "getUpdates",
                    {"timeout": 25, "offset": offset, "allowed_updates": ["message", "callback_query"]},
                )
                for upd in data.get("result") or []:
                    offset = int(upd["update_id"]) + 1
                    try:
                        self.handle_update(upd)
                    except Exception as e:
                        if on_error:
                            on_error(e)
                        else:
                            print(f"update error: {e}")
            except Exception as e:
                if on_error:
                    on_error(e)
                else:
                    print(f"poll error: {e}")
                time.sleep(idle_sleep)
