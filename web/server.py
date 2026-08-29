#!/usr/bin/env python3
"""JobWatcher Phosphor Catalog — same-host web UI + Telegram Mini App plugin."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

# Same-system lab root (required). No machine-specific defaults in code.
LAB = Path(os.environ["JW_LAB_ROOT"]).resolve() if os.environ.get("JW_LAB_ROOT") else None
if LAB is None:
    sibling = ROOT.parent / "job-watch-lab"
    LAB = sibling if sibling.is_dir() else Path.cwd() / "job-watch-lab"
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))

CONFIG = LAB / "config"
STATE = LAB / "state"
FILTERS = CONFIG / "filters.json"
COMPANIES = CONFIG / "companies.json"
SECRETS = CONFIG / "secrets.env"
RECENT = STATE / "recent_alerts.json"
PREFS = STATE / "bot_prefs.json"
SEEN = STATE / "seen.json"

HOST = os.environ.get("JW_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("JW_WEB_PORT", "3099"))
_lock = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def secrets() -> dict[str, str]:
    env = load_env(SECRETS)
    for k in (
        "ALERT_TELEGRAM_BOT_TOKEN",
        "ALERT_TELEGRAM_CHAT_IDS",
        "WEB_UI_SECRET",
        "WEB_UI_TOKEN",
        "WEB_APP_URL",
    ):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def _import_webapp():
    from jw.webapp.auth import (  # noqa: WPS433
        issue_session_token,
        validate_webapp_init_data,
        verify_session_token,
    )
    from jw.webapp.link import allowed_chat_id  # noqa: WPS433

    return {
        "validate_webapp_init_data": validate_webapp_init_data,
        "issue_session_token": issue_session_token,
        "verify_session_token": verify_session_token,
        "allowed_chat_id": allowed_chat_id,
    }


def allowed_chat() -> str:
    try:
        return _import_webapp()["allowed_chat_id"](secrets())
    except Exception:
        s = secrets()
        chats = [
            x.strip()
            for x in s.get("ALERT_TELEGRAM_CHAT_IDS", "").split(",")
            if x.strip()
        ]
        return chats[0] if chats else ""


def web_secret() -> str:
    s = secrets()
    return (
        s.get("WEB_UI_SECRET")
        or s.get("WEB_UI_TOKEN")
        or s.get("ALERT_TELEGRAM_BOT_TOKEN")
        or ""
    )


def day_token(chat_id: str, day: str | None = None) -> str:
    day = day or utc_now().strftime("%Y%m%d")
    raw = hmac.new(
        web_secret().encode(), f"{chat_id}:{day}".encode(), hashlib.sha256
    ).hexdigest()
    return raw[:28]


def valid_desk_token(token: str) -> bool:
    token = (token or "").strip()
    if not token or not web_secret():
        return False
    s = secrets()
    if s.get("WEB_UI_TOKEN") and hmac.compare_digest(token, s["WEB_UI_TOKEN"]):
        return True
    chat = allowed_chat()
    if not chat:
        return False
    for delta in (0, -1):
        d = (utc_now() + timedelta(days=delta)).strftime("%Y%m%d")
        if hmac.compare_digest(token, day_token(chat, d)):
            return True
    return False


def auth_user_from_header(auth_header: str, qs_token: str) -> str | None:
    """Return allowlisted user/chat id if Bearer or ?k= is valid."""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = (qs_token or "").strip()
    if not token:
        return None

    wa = _import_webapp()
    secret = web_secret()
    uid = wa["verify_session_token"](token, secret)
    if uid and uid == allowed_chat():
        return uid
    if valid_desk_token(token):
        return allowed_chat()
    return None


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def normalize_filters(data: dict[str, Any]) -> dict[str, Any]:
    list_keys = (
        "keywords_any",
        "keywords_all",
        "keywords_exclude",
        "locations_any",
        "title_any",
        "title_exclude",
        "companies",
    )
    out: dict[str, Any] = {}
    for k in list_keys:
        raw = data.get(k, [])
        if isinstance(raw, str):
            items = [x.strip() for x in re.split(r"[\n,]", raw) if x.strip()]
        else:
            items = [str(x).strip() for x in (raw or []) if str(x).strip()]
        seen: set[str] = set()
        uniq = []
        for i in items:
            key = i.lower()
            if key in seen:
                continue
            seen.add(key)
            uniq.append(i)
        out[k] = uniq
    if data.get("max_days_old") is None or data.get("max_days_old") == "":
        out["max_days_old"] = None
    else:
        out["max_days_old"] = int(data["max_days_old"])
    out["max_per_source"] = int(data.get("max_per_source") or 5)
    sources = data.get("sources") or {}
    out["sources"] = {
        "companies": bool(sources.get("companies", True)),
        "aggregators": bool(sources.get("aggregators", True)),
    }
    for k, v in data.items():
        if k not in out:
            out[k] = v
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "JobWatcherCatalog/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-Telegram-Init-Data",
        )
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS")

    def _authed_user(self) -> str | None:
        qs = parse_qs(urlparse(self.path).query)
        return auth_user_from_header(
            self.headers.get("Authorization", ""),
            (qs.get("k") or [""])[0],
        )

    def _json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, ctype: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "/index.html":
            return self._file(STATIC / "index.html", "text/html; charset=utf-8")
        if path == "/app.css":
            return self._file(STATIC / "app.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._file(STATIC / "app.js", "application/javascript; charset=utf-8")

        if path.startswith("/api/"):
            if path == "/api/health":
                return self._json(
                    200,
                    {
                        "ok": True,
                        "service": "phosphor-catalog",
                        "lab_root": str(LAB),
                        "webapp_plugin": True,
                    },
                )
            if path == "/api/auth/mode":
                s = secrets()
                return self._json(
                    200,
                    {
                        "telegram_webapp": bool(s.get("WEB_APP_URL") or s.get("TELEGRAM_WEBAPP_URL")),
                        "desk_fallback": True,
                    },
                )
            if not self._authed_user():
                return self._json(401, {"error": "unauthorized"})
            return self._api_get(path, parse_qs(parsed.query))

        self._json(404, {"error": "not found"})

    def do_PUT(self) -> None:
        self._write_api("PUT")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/api/auth/telegram":
            return self._auth_telegram()
        self._write_api("POST")

    def _read_body(self) -> Any:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode() or "{}")

    def _auth_telegram(self) -> None:
        try:
            body = self._read_body()
        except Exception:
            return self._json(400, {"error": "invalid json"})
        init_data = (
            body.get("initData")
            or self.headers.get("X-Telegram-Init-Data")
            or ""
        )
        s = secrets()
        bot_token = s.get("ALERT_TELEGRAM_BOT_TOKEN") or ""
        try:
            wa = _import_webapp()
            parsed = wa["validate_webapp_init_data"](init_data, bot_token)
            user = parsed.get("user") or {}
            uid = str(user.get("id") or "")
            allow = allowed_chat()
            if not uid or uid != allow:
                return self._json(403, {"error": "user not allowlisted"})
            token = wa["issue_session_token"](
                secret=web_secret(), user_id=uid, ttl_sec=86400
            )
            return self._json(
                200,
                {
                    "ok": True,
                    "token": token,
                    "user": {
                        "id": uid,
                        "first_name": user.get("first_name"),
                        "last_name": user.get("last_name"),
                        "language_code": user.get("language_code"),
                    },
                },
            )
        except Exception as e:
            return self._json(401, {"error": str(e)})

    def _write_api(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if not path.startswith("/api/"):
            return self._json(404, {"error": "not found"})
        if not self._authed_user():
            return self._json(401, {"error": "unauthorized"})
        try:
            body = self._read_body()
        except Exception:
            return self._json(400, {"error": "invalid json"})
        with _lock:
            if path == "/api/filters" and method == "PUT":
                normalized = normalize_filters(body)
                write_json(FILTERS, normalized)
                return self._json(200, {"ok": True, "filters": normalized})
            if path == "/api/prefs" and method in ("PUT", "POST"):
                prefs = read_json(PREFS, {"muted": False})
                if "muted" in body:
                    prefs["muted"] = bool(body["muted"])
                prefs["updated_at"] = utc_now().isoformat()
                write_json(PREFS, prefs)
                return self._json(200, {"ok": True, "prefs": prefs})
            if path == "/api/sources" and method == "PUT":
                cfg = read_json(COMPANIES, {"companies": [], "aggregators": []})
                updates = {
                    str(x["id"]): bool(x.get("enabled", True))
                    for x in body.get("items") or []
                    if x.get("id")
                }
                for bucket in ("companies", "aggregators"):
                    for row in cfg.get(bucket) or []:
                        if row.get("id") in updates:
                            row["enabled"] = updates[row["id"]]
                write_json(COMPANIES, cfg)
                return self._json(200, {"ok": True, "sources": self._sources_payload(cfg)})
        self._json(404, {"error": "not found"})

    def _sources_payload(self, cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        cfg = cfg or read_json(COMPANIES, {"companies": [], "aggregators": []})
        rows = []
        for bucket in ("companies", "aggregators"):
            for row in cfg.get(bucket) or []:
                rows.append(
                    {
                        "id": row.get("id"),
                        "name": row.get("name") or row.get("id"),
                        "type": row.get("type"),
                        "bucket": bucket,
                        "enabled": bool(row.get("enabled", True)),
                    }
                )
        return rows

    def _api_get(self, path: str, qs: dict[str, list[str]]) -> None:
        if path == "/api/bootstrap":
            prefs = read_json(PREFS, {"muted": False})
            filters = read_json(FILTERS, {})
            seen = read_json(SEEN, {"sources": {}})
            sources_state = seen.get("sources") or {}
            last = None
            for _sid, entry in sources_state.items():
                lc = (entry or {}).get("last_check")
                if lc and (last is None or lc > last):
                    last = lc
            return self._json(
                200,
                {
                    "recipient": {"chat_id": allowed_chat()},
                    "prefs": prefs,
                    "filters": filters,
                    "sources": self._sources_payload(),
                    "status": {
                        "tracked_sources": len(sources_state),
                        "last_check": last,
                        "recent_count": len(
                            (read_json(RECENT, {"jobs": []}).get("jobs") or [])
                        ),
                        "schedule": ["11:00 IST", "19:30 IST"],
                    },
                },
            )

        if path == "/api/filters":
            return self._json(200, read_json(FILTERS, {}))

        if path == "/api/jobs":
            jobs = list((read_json(RECENT, {"jobs": []}).get("jobs") or []))
            q = (qs.get("q") or [""])[0].strip().lower()
            source = (qs.get("source") or [""])[0].strip().lower()
            if q:
                jobs = [
                    j
                    for j in jobs
                    if q
                    in " ".join(
                        str(j.get(k) or "")
                        for k in ("title", "company", "location", "source_id")
                    ).lower()
                ]
            if source:
                jobs = [
                    j for j in jobs if str(j.get("source_id") or "").lower() == source
                ]
            total = len(jobs)
            try:
                page = max(1, int((qs.get("page") or ["1"])[0]))
            except ValueError:
                page = 1
            try:
                page_size = int((qs.get("page_size") or ["10"])[0])
            except ValueError:
                page_size = 10
            page_size = min(50, max(5, page_size))
            pages = max(1, (total + page_size - 1) // page_size)
            if page > pages:
                page = pages
            start = (page - 1) * page_size
            slice_ = jobs[start : start + page_size]
            return self._json(
                200,
                {
                    "jobs": slice_,
                    "count": len(slice_),
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "pages": pages,
                    "from": start + 1 if total else 0,
                    "to": start + len(slice_),
                },
            )

        if path == "/api/status":
            seen = read_json(SEEN, {"sources": {}})
            rows = []
            for sid, entry in sorted((seen.get("sources") or {}).items()):
                entry = entry or {}
                rows.append(
                    {
                        "id": sid,
                        "last_check": entry.get("last_check"),
                        "last_fetch_count": entry.get("last_fetch_count"),
                        "last_match_count": entry.get("last_match_count"),
                        "initialized": bool(entry.get("initialized")),
                        "seen": len(entry.get("seen_ids") or []),
                    }
                )
            return self._json(200, {"sources": rows})

        self._json(404, {"error": "not found"})


def main() -> None:
    if not LAB.is_dir():
        raise SystemExit("JW_LAB_ROOT must point at job-watch-lab on this host")
    if not web_secret():
        raise SystemExit("Missing WEB_UI_SECRET / bot token for UI auth")
    # prove plugin import
    _import_webapp()
    STATIC.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"Phosphor Catalog on http://{HOST}:{PORT} lab={LAB}",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
