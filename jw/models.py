from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_dt(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def make_job(
    *,
    source_id: str,
    company: str,
    job_id: str,
    title: str,
    url: str,
    location: str = "",
    posted_at: str = "",
    description: str = "",
    meta: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    title = (title or "").strip()
    jid = str(job_id or "").strip()
    if not title or not jid:
        return None
    job: dict[str, Any] = {
        "id": f"{source_id}:{jid}",
        "source_id": source_id,
        "company": (company or "").strip(),
        "title": title,
        "url": (url or "").strip(),
        "location": (location or "").strip(),
        "posted_at": (posted_at or "").strip(),
        "description": (description or "").strip()[:2000],
        "meta": (meta or "").strip(),
    }
    if extra:
        job["extra"] = extra
    return job


def collect_jobs(rows: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    return [j for j in rows if j]
