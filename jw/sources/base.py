from __future__ import annotations

from typing import Any, ClassVar


class Source:
    type_name: ClassVar[str] = ""

    def __init__(
        self,
        source_id: str,
        name: str,
        params: dict[str, Any],
        secrets: dict[str, str],
    ) -> None:
        self.source_id = source_id
        self.name = name
        self.params = dict(params or {})
        self.secrets = secrets

    def prepare(self, filters: dict[str, Any]) -> None:
        return None

    def fetch(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def probe(self) -> dict[str, Any]:
        return {
            "type": self.type_name,
            "id": self.source_id,
            "name": self.name,
            "params_keys": sorted(self.params.keys()),
        }
