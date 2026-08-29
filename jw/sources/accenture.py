from __future__ import annotations

import urllib.parse
from typing import Any

from jw.http import http_post_multipart
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class AccentureElasticSource(Source):
    type_name = "accenture_elastic"

    def fetch(self) -> list[dict[str, Any]]:
        page_size = int(self.params.get("pageSize", 50))
        country_site = self.params.get("countrySite", "in-en")
        fields = {
            "startIndex": "0",
            "maxResultSize": str(page_size),
            "jobCountry": self.params.get("jobCountry", "India"),
            "jobLanguage": self.params.get("jobLanguage", "en"),
            "countrySite": country_site,
            "sortBy": str(self.params.get("sortBy", "0")),
        }
        data = http_post_multipart(
            "https://www.accenture.com/api/accenture/elastic/findjobs",
            fields,
            headers={
                "Origin": "https://www.accenture.com",
                "Referer": "https://www.accenture.com/in-en/careers/jobsearch",
            },
        )
        rows: list[dict[str, Any] | None] = []
        for row in data.get("data") or []:
            job_id = str(row.get("requisitionId") or row.get("guid") or "")
            url_tpl = str(row.get("jobDetailUrl") or "")
            url = url_tpl.replace("{0}", country_site)
            if url and not url.startswith("http"):
                url = urllib.parse.urljoin("https://www.accenture.com", url)
            loc = ", ".join(row.get("location") or []) or ""
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=self.name,
                    job_id=job_id,
                    title=str(row.get("title") or ""),
                    url=url,
                    location=loc,
                    posted_at=str(row.get("updateDate") or row.get("postedDateText") or ""),
                    description=str(row.get("jobDescriptionClean") or "")[:1500],
                    meta=" · ".join(
                        x
                        for x in [
                            loc,
                            str(row.get("postedDateText") or ""),
                            str(row.get("careerLevel") or ""),
                        ]
                        if x
                    ),
                    extra={
                        "update_date": str(row.get("updateDate") or ""),
                        "posted_text": str(row.get("postedDateText") or ""),
                    },
                )
            )
        return collect_jobs(rows)
