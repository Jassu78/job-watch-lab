from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


def validate_webapp_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_sec: int = 86400,
) -> dict[str, Any]:
    """Validate Telegram Mini App initData. Returns parsed fields incl. user."""
    if not init_data or not bot_token:
        raise ValueError("missing initData or bot token")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise ValueError("missing hash")

    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise ValueError("bad initData signature")

    auth_date = int(pairs.get("auth_date") or 0)
    if auth_date and max_age_sec > 0:
        if abs(int(time.time()) - auth_date) > max_age_sec:
            raise ValueError("initData expired")

    user = {}
    if pairs.get("user"):
        user = json.loads(pairs["user"])
    return {
        "user": user,
        "auth_date": auth_date,
        "query_id": pairs.get("query_id"),
        "raw": pairs,
    }


def issue_session_token(
    *,
    secret: str,
    user_id: str | int,
    ttl_sec: int = 86400,
) -> str:
    exp = int(time.time()) + ttl_sec
    body = f"tg:{user_id}:{exp}"
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{body}:{sig}"


def verify_session_token(token: str, secret: str) -> str | None:
    """Return user_id if session token is valid."""
    try:
        prefix, sig = token.rsplit(":", 1)
        kind, user_id, exp_s = prefix.split(":", 2)
        if kind != "tg":
            return None
        exp = int(exp_s)
        if exp < int(time.time()):
            return None
        expect = hmac.new(secret.encode(), prefix.encode(), hashlib.sha256).hexdigest()[
            :24
        ]
        if not hmac.compare_digest(expect, sig):
            return None
        return str(user_id)
    except Exception:
        return None
