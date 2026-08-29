from __future__ import annotations

import urllib.parse
from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class RemotiveSource(Source):
    type_name = "remotive"

    def prepare(self, filters: dict[str, Any]) -> None:
        keywords = filters.get("keywords_any") or []
        if keywords and "search" not in self.params:
            self.params["search"] = keywords[0]

    def fetch(self) -> list[dict[str, Any]]:
        q: dict[str, str] = {}
        if self.params.get("category"):
            q["category"] = str(self.params["category"])
        if self.params.get("search"):
            q["search"] = str(self.params["search"])
        qs = f"?{urllib.parse.urlencode(q)}" if q else ""
        data = http_get_json(f"https://remotive.com/api/remote-jobs{qs}")
        rows: list[dict[str, Any] | None] = []
        for row in data.get("jobs") or []:
            loc = str(row.get("candidate_required_location") or "Remote")
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=str(row.get("company_name") or self.name),
                    job_id=str(row.get("id") or ""),
                    title=str(row.get("title") or ""),
                    url=str(row.get("url") or ""),
                    location=loc,
                    posted_at=str(row.get("publication_date") or ""),
                    description=str(row.get("description") or "")[:1500],
                    meta=" · ".join(
                        x
                        for x in [
                            loc,
                            str(row.get("job_type") or ""),
                            str(row.get("category") or ""),
                        ]
                        if x
                    ),
                )
            )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        jobs = self.fetch()
        return {**super().probe(), "count": len(jobs)}
