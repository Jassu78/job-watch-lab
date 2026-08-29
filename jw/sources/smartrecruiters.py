from __future__ import annotations

from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class SmartRecruitersSource(Source):
    type_name = "smartrecruiters"

    def fetch(self) -> list[dict[str, Any]]:
        slug = self.params["company"]
        limit = int(self.params.get("limit", 100))
        max_pages = int(self.params.get("maxPages", 2))
        rows: list[dict[str, Any] | None] = []
        for page in range(max_pages):
            offset = page * limit
            data = http_get_json(
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
                f"?limit={limit}&offset={offset}"
            )
            batch = data.get("content") or []
            if not batch:
                break
            for row in batch:
                loc_obj = row.get("location") or {}
                city = str(loc_obj.get("city") or "")
                country = str(loc_obj.get("country") or "")
                location = ", ".join(x for x in [city, country] if x)
                ref = str(row.get("refNumber") or row.get("id") or "")
                apply = str(row.get("applyUrl") or "")
                url = apply if apply.startswith("http") else (
                    f"https://jobs.smartrecruiters.com/{slug}/{row.get('id')}"
                    if row.get("id")
                    else ""
                )
                rows.append(
                    make_job(
                        source_id=self.source_id,
                        company=self.name,
                        job_id=ref or str(row.get("id") or ""),
                        title=str(row.get("name") or ""),
                        url=url,
                        location=location,
                        posted_at=str(row.get("releasedDate") or ""),
                        meta=" · ".join(
                            x
                            for x in [
                                location,
                                str((row.get("department") or {}).get("label") or ""),
                                str((row.get("experienceLevel") or {}).get("label") or ""),
                            ]
                            if x
                        ),
                    )
                )
            total = int(data.get("totalFound") or 0)
            if offset + limit >= total:
                break
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        slug = self.params["company"]
        url = (
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=5&offset=0"
        )
        data = http_get_json(url)
        batch = data.get("content") or []
        return {
            **super().probe(),
            "endpoint": url,
            "totalFound": data.get("totalFound"),
            "job_keys": sorted(batch[0].keys()) if batch else [],
        }
