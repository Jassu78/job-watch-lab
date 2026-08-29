from __future__ import annotations

import urllib.parse
from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class JSearchSource(Source):
    type_name = "jsearch"

    def prepare(self, filters: dict[str, Any]) -> None:
        if "query" in self.params:
            return
        keywords = filters.get("keywords_any") or []
        locations = filters.get("locations_any") or []
        kw = " ".join(keywords[:4]) if keywords else "software"
        loc = "India"
        for prefer in ("Hyderabad", "Bangalore", "Bengaluru", "Pune"):
            if any(prefer.lower() == x.lower() for x in locations):
                loc = prefer
                break
        self.params["query"] = f"{kw} jobs in {loc}"

    def fetch(self) -> list[dict[str, Any]]:
        key = self.secrets.get("JSEARCH_API_KEY", "")
        if not key:
            raise RuntimeError("JSearch needs JSEARCH_API_KEY in config/secrets.env")
        base = self.secrets.get("JSEARCH_BASE_URL", "https://jsearch.p.rapidapi.com").rstrip(
            "/"
        )
        query = str(self.params.get("query") or "software developer")
        q = {
            "query": query,
            "page": "1",
            "num_pages": str(self.params.get("num_pages", 1)),
            "country": self.params.get("country", "in"),
            "date_posted": self.params.get("date_posted", "week"),
        }
        if self.params.get("work_from_home"):
            q["work_from_home"] = "true"
        url = f"{base}/search?{urllib.parse.urlencode(q)}"
        headers = {
            "x-rapidapi-key": key,
            "x-rapidapi-host": "jsearch.p.rapidapi.com",
        }
        if "rapidapi" not in base:
            headers = {"x-api-key": key}
        data = http_get_json(url, headers=headers)
        rows: list[dict[str, Any] | None] = []
        for row in data.get("data") or []:
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=str(row.get("employer_name") or self.name),
                    job_id=str(row.get("job_id") or ""),
                    title=str(row.get("job_title") or ""),
                    url=str(row.get("job_apply_link") or row.get("job_google_link") or ""),
                    location=", ".join(
                        x
                        for x in [
                            str(row.get("job_city") or ""),
                            str(row.get("job_state") or ""),
                            str(row.get("job_country") or ""),
                        ]
                        if x
                    ),
                    posted_at=str(row.get("job_posted_at_datetime_utc") or ""),
                    description=str(row.get("job_description") or "")[:1500],
                    meta=str(row.get("job_employment_type") or ""),
                )
            )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        return {
            **super().probe(),
            "endpoint": "GET /search",
            "auth": "JSEARCH_API_KEY",
        }
