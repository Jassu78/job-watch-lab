from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = "AlinJobWatchLab/1.0 (+local; respectful)"
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def _request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> bytes:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        h.update(headers)
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt + 1 < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
                last_err = HttpError(f"HTTP {e.code} for {url}", status=e.code, body=body)
                continue
            raise HttpError(f"HTTP {e.code} for {url}", status=e.code, body=body) from e
        except urllib.error.URLError as e:
            if attempt + 1 < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
                last_err = e
                continue
            raise HttpError(f"Network error for {url}: {e}") from e
    raise HttpError(f"Request failed for {url}: {last_err}")


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    return _request(url, headers=headers, timeout=timeout)


def http_get_json(
    url: str, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT
) -> Any:
    return json.loads(http_get(url, headers=headers, timeout=timeout).decode())


def http_post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        h.update(headers)
    raw = _request(
        url,
        data=json.dumps(body).encode(),
        headers=h,
        method="POST",
        timeout=timeout,
    )
    return json.loads(raw.decode())


def http_post_multipart(
    url: str,
    fields: dict[str, str],
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    boundary = "----AlinJobWatchLab"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())
    parts.append(f"--{boundary}--\r\n".encode())
    h = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    if headers:
        h.update(headers)
    raw = _request(url, data=b"".join(parts), headers=h, method="POST", timeout=timeout)
    return json.loads(raw.decode())
