from __future__ import annotations

from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class AshbySource(Source):
    type_name = "ashby"

    def fetch(self) -> list[dict[str, Any]]:
        board = self.params["board"]
        data = http_get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
        )
        rows: list[dict[str, Any] | None] = []
        for row in data.get("jobs") or []:
            loc = str(row.get("location") or "")
            secondary = row.get("secondaryLocations") or []
            if secondary:
                extras = [
                    str(s.get("location") or "")
                    for s in secondary
                    if isinstance(s, dict)
                ]
                loc = ", ".join(x for x in [loc, *extras] if x)
            job_id = str(row.get("id") or "")
            url = str(row.get("jobUrl") or row.get("applyUrl") or "")
            if not url and job_id:
                url = f"https://jobs.ashbyhq.com/{board}/{job_id}"
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=self.name,
                    job_id=job_id,
                    title=str(row.get("title") or ""),
                    url=url,
                    location=loc,
                    posted_at=str(row.get("publishedAt") or ""),
                    description=str(
                        row.get("descriptionPlain") or row.get("descriptionHtml") or ""
                    )[:1500],
                    meta=" · ".join(
                        x
                        for x in [
                            loc,
                            str(row.get("department") or ""),
                            str(row.get("employmentType") or ""),
                        ]
                        if x
                    ),
                )
            )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        board = self.params["board"]
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
        data = http_get_json(url)
        jobs = data.get("jobs") or []
        return {
            **super().probe(),
            "endpoint": url,
            "count": len(jobs),
            "job_keys": sorted(jobs[0].keys()) if jobs else [],
        }
