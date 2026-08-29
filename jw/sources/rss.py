from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from jw.http import http_get
from jw.models import collect_jobs, make_job
from jw.registry import register
from jw.sources.base import Source


@register
class RssSource(Source):
    type_name = "rss"

    def fetch(self) -> list[dict[str, Any]]:
        feed_url = self.params.get("url", "")
        if not feed_url:
            return []
        raw = http_get(
            feed_url, headers={"Accept": "application/rss+xml, application/xml, */*"}
        )
        root = ET.fromstring(raw)
        items = root.findall(".//item") + root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )
        rows: list[dict[str, Any] | None] = []
        for item in items:

            def _text(tag: str) -> str:
                el = item.find(tag)
                if el is None:
                    el = item.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
                if el is None:
                    return ""
                return "".join(el.itertext()).strip()

            title = _text("title")
            link = _text("link")
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            if not link and link_el is not None:
                link = link_el.attrib.get("href", "")
            guid = _text("guid") or _text("id") or link or title
            desc = _text("description") or _text("summary") or _text("content")
            location = ""
            for marker in ("Location:", "location:"):
                if marker in desc:
                    chunk = desc.split(marker, 1)[1]
                    location = chunk.split("<")[0].split("\n")[0].strip()[:120]
                    break
            pub = _text("pubDate") or _text("published") or _text("updated")
            rows.append(
                make_job(
                    source_id=self.source_id,
                    company=self.name,
                    job_id=guid,
                    title=title or "Job",
                    url=link,
                    location=location,
                    posted_at=pub,
                    description=desc[:1500],
                    meta=location,
                )
            )
        return collect_jobs(rows)

    def probe(self) -> dict[str, Any]:
        jobs = self.fetch()
        return {
            **super().probe(),
            "endpoint": self.params.get("url"),
            "count": len(jobs),
        }
