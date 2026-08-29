from __future__ import annotations

from typing import Any

from jw.http import http_post_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class WorkdaySource(Source):
    type_name = "workday"

    def fetch(self) -> list[dict[str, Any]]:
        base = self.params["base"].rstrip("/")
        tenant = self.params["tenant"]
        site = self.params["site"]
        search = str(self.params.get("searchText") or "")
        max_pages = int(self.params.get("maxPages", 3))
        facets = self.params.get("appliedFacets") or {}
        url = f"{base}/wday/cxs/{tenant}/{site}/jobs"
        rows: list[dict[str, Any] | None] = []
        limit = 20
        for page in range(max_pages):
            body = {
                "appliedFacets": facets,
                "limit": limit,
                "offset": page * limit,
                "searchText": search,
            }
            data = http_post_json(url, body)
            batch = data.get("jobPostings") or []
            if not batch:
                break
            for row in batch:
                path = str(row.get("externalPath") or "")
                job_url = f"{base}/{site}{path}" if path else base
                bullets = row.get("bulletFields") or []
                job_id = str(bullets[0] if bullets else path or row.get("title") or "")
                posted = str(row.get("postedOn") or "")
                rows.append(
                    make_job(
                        source_id=self.source_id,
                        company=self.name,
                        job_id=job_id,
                        title=str(row.get("title") or ""),
                        url=job_url,
                        location=str(row.get("locationsText") or ""),
                        posted_at=posted,
                        meta=" · ".join(
                            x
                            for x in [str(row.get("locationsText") or ""), posted]
                            if x
                        ),
                        extra={"posted_on_text": posted},
                    )
                )
            total = int(data.get("total") or 0)
            if (page + 1) * limit >= total:
                break
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        base = self.params["base"].rstrip("/")
        url = f"{base}/wday/cxs/{self.params['tenant']}/{self.params['site']}/jobs"
        body = {
            "appliedFacets": self.params.get("appliedFacets") or {},
            "limit": 5,
            "offset": 0,
            "searchText": self.params.get("searchText") or "",
        }
        data = http_post_json(url, body)
        batch = data.get("jobPostings") or []
        return {
            **super().probe(),
            "endpoint": f"POST {url}",
            "total": data.get("total"),
            "job_keys": sorted(batch[0].keys()) if batch else [],
        }
