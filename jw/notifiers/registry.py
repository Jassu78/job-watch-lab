from __future__ import annotations

from typing import Type

from jw.notifiers.base import Notifier

_REGISTRY: dict[str, Type[Notifier]] = {}


def register(cls: Type[Notifier]) -> Type[Notifier]:
    name = getattr(cls, "type_name", "") or ""
    if not name:
        raise ValueError(f"{cls.__name__} missing type_name")
    _REGISTRY[name] = cls
    return cls


def get_notifier(
    channel: dict,
    secrets: dict[str, str],
) -> Notifier:
    ntype = channel.get("type", "")
    cls = _REGISTRY.get(ntype)
    if not cls:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise RuntimeError(f"Unknown notifier type {ntype!r}. Known: {known}")
    return cls(
        str(channel.get("id") or ntype),
        channel.get("params") or {},
        secrets,
    )


def list_types() -> list[str]:
    return sorted(_REGISTRY)


def _load_builtins() -> None:
    from jw.notifiers import telegram  # noqa: F401


_load_builtins()
