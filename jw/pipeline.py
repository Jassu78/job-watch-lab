from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from jw.config import enabled_notifiers, load_notifiers_config
from jw.filters import CompiledFilters, apply_filters, compile_filters, rank_jobs
from jw.notify import format_jobs, pack_jobs_dp
from jw.notifiers.registry import get_notifier
from jw.registry import get_source
from jw.state import load_state, new_matches, save_state, update_seen

MAX_WORKERS = 8


def fetch_source(
    source_cfg: dict[str, Any],
    filters: dict[str, Any],
    secrets: dict[str, str],
) -> tuple[str, list[dict[str, Any]], str | None]:
    sid = source_cfg["id"]
    try:
        src = get_source(source_cfg, secrets)
        src.prepare(filters)
        jobs = src.fetch()
    except Exception as e:
        return sid, [], f"ERROR {sid}: {e}"
    return sid, jobs, None


def settle_source(
    sid: str,
    jobs: list[dict[str, Any]],
    matched: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    mode: str,
    max_per_source: int,
    compiled: CompiledFilters,
) -> tuple[list[dict[str, Any]], str]:
    entry = state.setdefault("sources", {}).setdefault(
        sid, {"initialized": False, "seen_ids": []}
    )

    if mode == "dry-run":
        ranked = rank_jobs(matched, compiled)[:max_per_source]
        return ranked, (
            f"DRY {sid}: fetch={len(jobs)} match={len(matched)} show={len(ranked)}"
        )

    seed = mode == "seed"
    if seed or not entry.get("initialized"):
        update_seen(
            entry,
            fetched_ids=[j["id"] for j in jobs],
            match_count=len(matched),
            fetch_count=len(jobs),
            seed=True,
        )
        # Return ranked matches for /latest catalog only; caller must not notify.
        ranked = rank_jobs(matched, compiled)[:max_per_source]
        return ranked, (
            f"SEED {sid}: fetch={len(jobs)} match={len(matched)} "
            f"tracking={len(entry['seen_ids'])} catalog={len(ranked)} (no alert)"
        )

    alerts_all = new_matches(entry, matched)
    ranked = rank_jobs(alerts_all, compiled)
    alerts = ranked[:max_per_source]
    update_seen(
        entry,
        fetched_ids=[j["id"] for j in jobs],
        match_count=len(matched),
        fetch_count=len(jobs),
        seed=False,
    )
    return alerts, (
        f"OK {sid}: fetch={len(jobs)} match={len(matched)} "
        f"new={len(alerts_all)} alert={len(alerts)}"
    )


def build_notifiers(secrets: dict[str, str]) -> list[Any]:
    channels = enabled_notifiers(load_notifiers_config())
    out = []
    for ch in channels:
        n = get_notifier(ch, secrets)
        ready, reason = n.ready()
        if not ready:
            print(f"notifier {ch.get('id')}: skip ({reason})")
            continue
        out.append(n)
    return out


def dispatch_alerts(
    by_source: dict[str, list[dict[str, Any]]],
    compiled: CompiledFilters,
    secrets: dict[str, str],
    *,
    notify: bool,
) -> None:
    from jw.bot.prefs import is_muted, push_recent

    notifiers = build_notifiers(secrets) if notify else []
    muted = is_muted() if notify else False
    for sid, jobs in by_source.items():
        header = f"🆕 {sid} ({len(jobs)})"
        scores = [compiled.score(j) for j in jobs]
        packed = pack_jobs_dp(jobs, header=header, scores=scores)
        block = format_jobs(packed, header)
        print("\n" + block)
        push_recent(packed, source_id=sid)
        if not notify:
            continue
        if muted:
            print(f"notify skipped: muted (/unmute to resume) [{sid}]")
            continue
        if not notifiers:
            print("notify skipped: no ready channels in config/notifiers.json")
            continue
        for n in notifiers:
            try:
                ok = n.send_jobs(packed, header=header, scores=scores)
                print(f"{n.type_name}:{n.channel_id} {sid}: {'ok' if ok else 'FAIL'}")
            except Exception as e:
                print(f"{n.type_name}:{n.channel_id} {sid}: FAIL {e}")


def run_one(
    source_cfg: dict[str, Any],
    filters: dict[str, Any],
    secrets: dict[str, str],
    state: dict[str, Any],
    *,
    mode: str,
    max_per_source: int,
    compiled: CompiledFilters | None = None,
) -> tuple[list[dict[str, Any]], str]:
    compiled = compiled or compile_filters(filters)
    sid, jobs, err = fetch_source(source_cfg, filters, secrets)
    if err:
        return [], err
    matched = apply_filters(jobs, compiled)
    return settle_source(
        sid,
        jobs,
        matched,
        state,
        mode=mode,
        max_per_source=max_per_source,
        compiled=compiled,
    )


def run_all(
    sources: list[dict[str, Any]],
    filters: dict[str, Any],
    secrets: dict[str, str],
    *,
    mode: str,
    notify: bool = False,
    reset_state: bool = False,
) -> int:
    from jw.config import STATE_PATH

    max_per = int(filters.get("max_per_source") or 5)
    compiled = compile_filters(filters)
    if reset_state and STATE_PATH.is_file():
        STATE_PATH.unlink()
        print(f"Reset {STATE_PATH}")

    state = {"sources": {}} if mode == "dry-run" else load_state()
    print(f"Sources: {len(sources)} | mode={mode}")

    fetched: list[tuple[str, list[dict[str, Any]], str | None]] = []
    workers = min(MAX_WORKERS, max(1, len(sources)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(fetch_source, cfg, filters, secrets): cfg for cfg in sources
        }
        for fut in as_completed(futs):
            fetched.append(fut.result())

    order = {cfg["id"]: i for i, cfg in enumerate(sources)}
    fetched.sort(key=lambda row: order.get(row[0], 10**9))

    by_source: dict[str, list[dict[str, Any]]] = {}
    total = 0

    for sid, jobs, err in fetched:
        if err:
            print(err)
            continue
        matched = apply_filters(jobs, compiled)
        alerts, status = settle_source(
            sid,
            jobs,
            matched,
            state,
            mode=mode,
            max_per_source=max_per,
            compiled=compiled,
        )
        print(status)
        if alerts:
            by_source[sid] = alerts
            total += len(alerts)

    if mode != "dry-run":
        save_state(state)

    if not by_source:
        print("\nNo matches to show.")
        return 0

    dispatch_alerts(by_source, compiled, secrets, notify=notify and mode == "watch")
    print(f"\nTotal shown: {total}")
    return 0
