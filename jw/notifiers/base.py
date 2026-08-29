from __future__ import annotations

from typing import Any, ClassVar


class Notifier:
    type_name: ClassVar[str] = ""

    def __init__(
        self,
        channel_id: str,
        params: dict[str, Any],
        secrets: dict[str, str],
    ) -> None:
        self.channel_id = channel_id
        self.params = dict(params or {})
        self.secrets = secrets

    def ready(self) -> tuple[bool, str]:
        return True, "ok"

    def send(self, text: str) -> bool:
        raise NotImplementedError

    def send_jobs(
        self,
        jobs: list[dict[str, Any]],
        *,
        header: str,
        scores: list[int] | None = None,
    ) -> bool:
        from jw.notify import format_jobs, pack_jobs_dp

        packed = pack_jobs_dp(jobs, header=header, scores=scores)
        return self.send(format_jobs(packed, header))
