from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timezone
from typing import Any

from jw.automaton import MultiPattern
from jw.models import parse_iso_dt, utc_now


def job_blob(job: dict[str, Any]) -> str:
    return " ".join(
        str(job.get(k) or "")
        for k in ("title", "location", "meta", "description", "company")
    ).lower()


def parse_workday_posted_age_hours(text: str) -> int | None:
    if not text:
        return None
    lower = text.lower()
    if "today" in lower or "just" in lower:
        return 0
    if "yesterday" in lower:
        return 24
    m = re.search(r"(\d+)\+?\s*day", lower)
    if m:
        return int(m.group(1)) * 24
    m = re.search(r"(\d+)\s*hour", lower)
    if m:
        return int(m.group(1))
    return None


def job_age_hours(job: dict[str, Any], *, now_ts: float | None = None) -> float | None:
    posted = str(job.get("posted_at") or "")
    dt = parse_iso_dt(posted)
    if dt:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = utc_now() if now_ts is None else None
        if now_ts is not None:
            return (now_ts - dt.astimezone(timezone.utc).timestamp()) / 3600
        assert now is not None
        return (now - dt.astimezone(timezone.utc)).total_seconds() / 3600
    extra = job.get("extra") or {}
    wd = parse_workday_posted_age_hours(str(extra.get("posted_on_text") or posted))
    if wd is not None:
        return float(wd)
    return None


@dataclass(frozen=True, slots=True)
class CompiledFilters:
    companies: frozenset[str] | None
    keywords_any: MultiPattern | None
    keywords_all: tuple[str, ...]
    keywords_exclude: MultiPattern | None
    title_any: MultiPattern | None
    title_exclude: MultiPattern | None
    locations_any: MultiPattern | None
    max_age_hours: float | None
    now_ts: float

    def matches(self, job: dict[str, Any]) -> bool:
        if self.companies is not None:
            sid = str(job.get("source_id") or "").lower()
            cname = str(job.get("company") or "").lower()
            if sid not in self.companies and cname not in self.companies:
                return False

        title = str(job.get("title") or "").lower()
        if self.title_exclude is not None and self.title_exclude.hits_any(title):
            return False
        if self.title_any is not None and not self.title_any.hits_any(title):
            return False

        blob = job_blob(job)
        if self.keywords_exclude is not None and self.keywords_exclude.hits_any(blob):
            return False
        if self.keywords_any is not None and not self.keywords_any.hits_any(blob):
            return False
        for needle in self.keywords_all:
            if needle not in blob:
                return False

        if self.locations_any is not None:
            location = str(job.get("location") or job.get("meta") or "").lower()
            loc_hay = f"{location} {blob}"
            if not self.locations_any.hits_any(loc_hay):
                return False

        if self.max_age_hours is not None:
            age_h = job_age_hours(job, now_ts=self.now_ts)
            if age_h is not None and age_h > self.max_age_hours:
                return False

        return True

    def score(self, job: dict[str, Any]) -> int:
        blob = job_blob(job)
        title = str(job.get("title") or "").lower()
        hits = 0
        if self.keywords_any is not None:
            hits += self.keywords_any.hit_count(blob)
        if self.title_any is not None:
            hits += self.title_any.hit_count(title)
        age = job_age_hours(job, now_ts=self.now_ts)
        freshness = 0
        if age is not None:
            freshness = max(0, 48 - int(age))
        return hits * 10 + freshness


def compile_filters(filters: dict[str, Any]) -> CompiledFilters:
    companies_raw = filters.get("companies") or []
    companies = frozenset(c.lower() for c in companies_raw) if companies_raw else None

    def mp(key: str) -> MultiPattern | None:
        rows = [str(x) for x in (filters.get(key) or []) if str(x).strip()]
        return MultiPattern(rows) if rows else None

    keywords_all = tuple(
        str(x).lower() for x in (filters.get("keywords_all") or []) if str(x).strip()
    )
    max_days = filters.get("max_days_old")
    max_age = float(max_days) * 24 if max_days is not None else None
    return CompiledFilters(
        companies=companies,
        keywords_any=mp("keywords_any"),
        keywords_all=keywords_all,
        keywords_exclude=mp("keywords_exclude"),
        title_any=mp("title_any"),
        title_exclude=mp("title_exclude"),
        locations_any=mp("locations_any"),
        max_age_hours=max_age,
        now_ts=utc_now().timestamp(),
    )


def job_matches_filters(job: dict[str, Any], filters: dict[str, Any]) -> bool:
    return compile_filters(filters).matches(job)


def apply_filters(
    jobs: list[dict[str, Any]],
    filters: dict[str, Any] | CompiledFilters,
) -> list[dict[str, Any]]:
    compiled = filters if isinstance(filters, CompiledFilters) else compile_filters(filters)
    return [j for j in jobs if compiled.matches(j)]


def rank_jobs(
    jobs: list[dict[str, Any]],
    filters: dict[str, Any] | CompiledFilters,
) -> list[dict[str, Any]]:
    compiled = filters if isinstance(filters, CompiledFilters) else compile_filters(filters)
    return sorted(jobs, key=compiled.score, reverse=True)
