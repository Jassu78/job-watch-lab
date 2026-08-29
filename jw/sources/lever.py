from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class LeverSource(Source):
    type_name = "lever"

    def fetch(self) -> list[dict[str, Any]]:
        slug = self.params["company"]
        data = http_get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        if not isinstance(data, list):
            return []
        rows: list[dict[str, Any] | None] = []
        for row in data:
            cats = row.get("categories") or {}
            location = str(cats.get("location") or row.get("workplaceType") or "")
            created = row.get("createdAt")
            posted = ""
            if isinstance(created, (int, float)):
                posted = datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat()
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=self.name,
                    job_id=str(row.get("id") or ""),
                    title=str(row.get("text") or ""),
                    url=str(row.get("hostedUrl") or row.get("applyUrl") or ""),
                    location=location,
                    posted_at=posted,
                    description=str(row.get("descriptionPlain") or "")[:1500],
                    meta=" · ".join(
                        x
                        for x in [
                            location,
                            str(cats.get("team") or ""),
                            str(row.get("workplaceType") or ""),
                        ]
                        if x
                    ),
                )
            )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        slug = self.params["company"]
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        data = http_get_json(url)
        n = len(data) if isinstance(data, list) else 0
        keys = sorted(data[0].keys()) if isinstance(data, list) and data else []
        return {**super().probe(), "endpoint": url, "count": n, "job_keys": keys}
