from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Any


TELEGRAM_LIMIT = 4000


def _job_line_cost(job: dict[str, Any]) -> int:
    parts = [f"• [{job.get('company')}] {job.get('title')}"]
    meta = job.get("meta") or job.get("location") or ""
    if meta:
        parts.append(f"  {meta}")
    if job.get("url"):
        parts.append(f"  {job['url']}")
    parts.append("")
    return len("\n".join(parts)) + 1


def pack_jobs_dp(
    jobs: list[dict[str, Any]],
    *,
    header: str,
    limit: int = TELEGRAM_LIMIT,
    scores: list[int] | None = None,
) -> list[dict[str, Any]]:
    """0/1 knapsack on message bytes: max score under char budget."""
    if not jobs:
        return []
    budget = max(0, limit - len(header) - 2)
    n = len(jobs)
    costs = [_job_line_cost(j) for j in jobs]
    vals = scores if scores is not None else [1] * n

    if sum(costs) <= budget:
        return list(jobs)

    # Cap DP table size for large n: take top by value/cost then exact DP.
    order = sorted(range(n), key=lambda i: vals[i] / max(1, costs[i]), reverse=True)
    order = order[: min(n, 40)]
    m = len(order)
    dp = [[0] * (budget + 1) for _ in range(m + 1)]
    take = [[False] * (budget + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        idx = order[i - 1]
        c, v = costs[idx], vals[idx]
        for b in range(budget + 1):
            dp[i][b] = dp[i - 1][b]
            if c <= b and dp[i - 1][b - c] + v > dp[i][b]:
                dp[i][b] = dp[i - 1][b - c] + v
                take[i][b] = True
    chosen: list[int] = []
    b = budget
    for i in range(m, 0, -1):
        if take[i][b]:
            idx = order[i - 1]
            chosen.append(idx)
            b -= costs[idx]
    chosen.sort()
    return [jobs[i] for i in chosen]


def format_jobs(jobs: list[dict], header: str) -> str:
    lines = [header, ""]
    for job in jobs:
        lines.append(f"• [{job.get('company')}] {job.get('title')}")
        meta = job.get("meta") or job.get("location") or ""
        if meta:
            lines.append(f"  {meta}")
        if job.get("url"):
            lines.append(f"  {job['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def send_telegram(token: str, chat_ids: list[str], text: str) -> bool:
    if not token or not chat_ids:
        return False
    ok = True
    chunk = text[:TELEGRAM_LIMIT]
    for chat_id in chat_ids:
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": chunk}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except urllib.error.URLError:
            ok = False
    return ok
