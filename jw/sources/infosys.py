from __future__ import annotations

import urllib.parse
from typing import Any

from jw.http import http_get_json
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class InfosysSource(Source):
    type_name = "infosys_api"

    def fetch(self) -> list[dict[str, Any]]:
        location = self.params.get("location", "All locations")
        source_id_param = str(self.params.get("sourceId", "1,21"))
        query = urllib.parse.urlencode(
            {"location": location, "sourceId": source_id_param}
        )
        url = (
            "https://intapgateway.infosysapps.com/careersci/search/intapjbsrch/"
            f"getHotJobsDetails?{query}"
        )
        data = http_get_json(
            url,
            headers={
                "Origin": "https://career.infosys.com",
                "Referer": "https://career.infosys.com/",
            },
        )
        rows: list[dict[str, Any] | None] = []
        for row in data.get("hotJobsLists") or []:
            job_id = str(
                row.get("referenceCode")
                or row.get("requisitionId")
                or row.get("postingId")
                or ""
            )
            posting_id = row.get("postingId")
            loc = str(row.get("location") or "")
            min_exp, max_exp = row.get("minExperienceLevel"), row.get("maxExperienceLevel")
            exp = ""
            if min_exp is not None and max_exp is not None:
                exp = f"{min_exp}-{max_exp} yrs"
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=self.name,
                    job_id=job_id,
                    title=str(row.get("postingTitle") or ""),
                    url=f"https://career.infosys.com/jobdesc?jobId={posting_id}",
                    location=loc,
                    description=str(row.get("rolesResponsibilities") or "")[:1500],
                    meta=" · ".join(x for x in [loc, exp] if x),
                    extra={
                        "min_exp": str(min_exp) if min_exp is not None else "",
                        "max_exp": str(max_exp) if max_exp is not None else "",
                    },
                )
            )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        jobs = self.fetch()
        return {**super().probe(), "count": len(jobs), "spam_note": "hot list rotates"}
