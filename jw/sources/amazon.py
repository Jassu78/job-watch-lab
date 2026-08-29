from __future__ import annotations

import urllib.parse
from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class AmazonJobsSource(Source):
    type_name = "amazon_jobs"

    def prepare(self, filters: dict[str, Any]) -> None:
        keywords = filters.get("keywords_any") or []
        if keywords and not self.params.get("base_query") and not self.params.get(
            "base_query_locked"
        ):
            self.params["base_query"] = " ".join(keywords[:3])

    def fetch(self) -> list[dict[str, Any]]:
        base_query = str(self.params.get("base_query") or "software engineer")
        loc_query = str(self.params.get("loc_query") or "India")
        country = str(self.params.get("country") or "IND")
        result_limit = int(self.params.get("result_limit") or 20)
        max_pages = int(self.params.get("max_pages") or 3)
        rows: list[dict[str, Any] | None] = []
        for page in range(max_pages):
            offset = page * result_limit
            q = urllib.parse.urlencode(
                {
                    "offset": offset,
                    "result_limit": result_limit,
                    "base_query": base_query,
                    "loc_query": loc_query,
                    "country": country,
                }
            )
            url = f"https://www.amazon.jobs/en/search.json?{q}"
            data = http_get_json(url)
            batch = data.get("jobs") or []
            if not batch:
                break
            for row in batch:
                job_id = str(row.get("id_icims") or row.get("id") or "")
                path = str(row.get("job_path") or "")
                job_url = (
                    f"https://www.amazon.jobs{path}"
                    if path.startswith("/")
                    else str(row.get("url_next_step") or "")
                )
                loc = str(
                    row.get("normalized_location")
                    or row.get("location")
                    or row.get("city")
                    or ""
                )
                rows.append(
                    make_job(
                        source_id=self.source_id,
                        company=str(row.get("company_name") or self.name),
                        job_id=job_id,
                        title=str(row.get("title") or ""),
                        url=job_url,
                        location=loc,
                        posted_at=str(
                            row.get("posted_date") or row.get("updated_time") or ""
                        ),
                        description=str(
                            row.get("description_short")
                            or row.get("basic_qualifications")
                            or ""
                        )[:1500],
                        meta=" · ".join(
                            x
                            for x in [
                                loc,
                                str(row.get("job_category") or ""),
                                str(row.get("job_schedule_type") or ""),
                            ]
                            if x
                        ),
                    )
                )
            hits = int(data.get("hits") or 0)
            if offset + result_limit >= hits:
                break
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        jobs = self.fetch()
        return {
            **super().probe(),
            "endpoint": "https://www.amazon.jobs/en/search.json",
            "count": len(jobs),
            "server_filters": "base_query, loc_query, country, offset, result_limit",
        }
