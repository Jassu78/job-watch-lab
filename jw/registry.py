from __future__ import annotations

from typing import Type

from jw.sources.base import Source

_REGISTRY: dict[str, Type[Source]] = {}


def register(cls: Type[Source]) -> Type[Source]:
    name = getattr(cls, "type_name", "") or ""
    if not name:
        raise ValueError(f"{cls.__name__} missing type_name")
    _REGISTRY[name] = cls
    return cls


def get_source(
    source: dict,
    secrets: dict[str, str],
) -> Source:
    stype = source.get("type", "")
    cls = _REGISTRY.get(stype)
    if not cls:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise RuntimeError(f"Unknown source type {stype!r}. Known: {known}")
    return cls(
        source["id"],
        source.get("name", source["id"]),
        source.get("params") or {},
        secrets,
    )


def list_types() -> list[str]:
    return sorted(_REGISTRY)


def _load_builtins() -> None:
    # Import side-effect: each module registers itself.
    from jw.sources import (  # noqa: F401
        accenture,
        adzuna,
        amazon,
        ashby,
        greenhouse,
        infosys,
        jsearch,
        lever,
        remotive,
        rss,
        smartrecruiters,
        workday,
    )


_load_builtins()
