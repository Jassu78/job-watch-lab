from __future__ import annotations

from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class GreenhouseSource(Source):
    type_name = "greenhouse"

    def fetch(self) -> list[dict[str, Any]]:
        board = self.params["board"]
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        if self.params.get("include_content"):
            url += "?content=true"
        data = http_get_json(url)
        rows: list[dict[str, Any] | None] = []
        for row in data.get("jobs") or []:
            loc_bits: list[str] = []
            loc = row.get("location")
            if isinstance(loc, dict) and loc.get("name"):
                loc_bits.append(str(loc["name"]))
            for office in row.get("offices") or []:
                if isinstance(office, dict) and office.get("name"):
                    loc_bits.append(str(office["name"]))
            location = ", ".join(dict.fromkeys(x for x in loc_bits if x))
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=self.name,
                    job_id=str(row.get("id") or ""),
                    title=str(row.get("title") or ""),
                    url=str(row.get("absolute_url") or ""),
                    location=location,
                    posted_at=str(row.get("updated_at") or row.get("first_published") or ""),
                    description=str(row.get("content") or "")[:1500],
                    meta=location,
                )
            )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        board = self.params["board"]
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        data = http_get_json(url)
        jobs = data.get("jobs") or []
        return {
            **super().probe(),
            "endpoint": url,
            "count": len(jobs),
            "job_keys": sorted(jobs[0].keys()) if jobs else [],
        }
