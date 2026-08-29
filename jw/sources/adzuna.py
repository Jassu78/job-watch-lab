from __future__ import annotations

import urllib.parse
from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class AdzunaSource(Source):
    type_name = "adzuna"

    def prepare(self, filters: dict[str, Any]) -> None:
        keywords = filters.get("keywords_any") or []
        exclude = filters.get("keywords_exclude") or []
        locations = filters.get("locations_any") or []
        max_days = filters.get("max_days_old")
        params = self.params

        if "what" not in params and "company" not in params:
            params["what"] = "software engineer" if not keywords else "software engineer"
        if locations and "where" not in params and "company" not in params:
            for prefer in ("Hyderabad", "Bangalore", "Bengaluru", "Pune", "Chennai"):
                if any(prefer.lower() == loc.lower() for loc in locations):
                    params["where"] = prefer
                    break
            else:
                if any("india" in loc.lower() for loc in locations):
                    params["where"] = "India"
        if max_days is not None and "max_days_old" not in params:
            params["max_days_old"] = max_days
        if exclude and "what_exclude" not in params and "company" not in params:
            params["what_exclude"] = " ".join(exclude[:3])

    def fetch(self) -> list[dict[str, Any]]:
        app_id = self.secrets.get("ADZUNA_APP_ID", "")
        app_key = self.secrets.get("ADZUNA_APP_KEY", "")
        if not app_id or not app_key:
            raise RuntimeError(
                "Adzuna needs ADZUNA_APP_ID and ADZUNA_APP_KEY in config/secrets.env"
            )

        country = self.params.get("country", "in")
        results = int(self.params.get("results_per_page", 20))
        max_pages = int(self.params.get("max_pages", 1))
        what = str(self.params.get("what") or "")
        where = str(self.params.get("where") or "")
        max_days = self.params.get("max_days_old")
        what_exclude = str(self.params.get("what_exclude") or "")
        company_filter = str(self.params.get("company") or "")

        rows: list[dict[str, Any] | None] = []
        for page in range(1, max_pages + 1):
            q: dict[str, Any] = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": results,
                "content-type": "application/json",
            }
            if what:
                q["what"] = what
            if where:
                q["where"] = where
            if max_days is not None:
                q["max_days_old"] = int(max_days)
            if what_exclude:
                q["what_exclude"] = what_exclude
            if company_filter:
                q["company"] = company_filter
            if self.params.get("full_time"):
                q["full_time"] = 1
            url = (
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
                f"?{urllib.parse.urlencode(q)}"
            )
            data = http_get_json(url)
            batch = data.get("results") or []
            if not batch:
                break
            for row in batch:
                loc = row.get("location") or {}
                display = str(loc.get("display_name") or "")
                co = row.get("company") or {}
                rows.append(
                    make_job(
                        source_id=self.source_id,
                        company=str(co.get("display_name") or self.name),
                        job_id=str(row.get("id") or ""),
                        title=str(row.get("title") or ""),
                        url=str(row.get("redirect_url") or ""),
                        location=display,
                        posted_at=str(row.get("created") or ""),
                        description=str(row.get("description") or "")[:1500],
                        meta=" · ".join(
                            x
                            for x in [
                                display,
                                str(row.get("contract_type") or ""),
                                str((row.get("category") or {}).get("label") or ""),
                            ]
                            if x
                        ),
                    )
                )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        return {
            **super().probe(),
            "endpoint": "GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}",
            "auth": "ADZUNA_APP_ID + ADZUNA_APP_KEY",
            "configured": {
                "what": self.params.get("what"),
                "company": self.params.get("company"),
                "where": self.params.get("where"),
            },
        }
