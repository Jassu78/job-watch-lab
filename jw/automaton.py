from __future__ import annotations

from collections import deque


class MultiPattern:
    """Aho–Corasick automaton for multi-substring queries."""

    __slots__ = ("_goto", "_fail", "_out", "_empty")

    def __init__(self, patterns: list[str]) -> None:
        cleaned = [p.lower() for p in patterns if p and p.strip()]
        self._empty = not cleaned
        self._goto: list[dict[str, int]] = [{}]
        self._fail: list[int] = [0]
        self._out: list[list[int]] = [[]]
        for i, pat in enumerate(cleaned):
            node = 0
            for ch in pat:
                nxt = self._goto[node].get(ch)
                if nxt is None:
                    nxt = len(self._goto)
                    self._goto[node][ch] = nxt
                    self._goto.append({})
                    self._fail.append(0)
                    self._out.append([])
                node = nxt
            self._out[node].append(i)
        self._build_failure()

    def _build_failure(self) -> None:
        q: deque[int] = deque()
        for nxt in self._goto[0].values():
            q.append(nxt)
            self._fail[nxt] = 0
        while q:
            r = q.popleft()
            for ch, s in self._goto[r].items():
                q.append(s)
                f = self._fail[r]
                while f and ch not in self._goto[f]:
                    f = self._fail[f]
                self._fail[s] = self._goto[f].get(ch, 0)
                if self._fail[s] != s:
                    self._out[s].extend(self._out[self._fail[s]])

    def hits_any(self, text: str) -> bool:
        if self._empty:
            return False
        node = 0
        for ch in text.lower():
            while node and ch not in self._goto[node]:
                node = self._fail[node]
            node = self._goto[node].get(ch, 0)
            if self._out[node]:
                return True
        return False

    def hit_count(self, text: str) -> int:
        if self._empty:
            return 0
        seen: set[int] = set()
        node = 0
        for ch in text.lower():
            while node and ch not in self._goto[node]:
                node = self._fail[node]
            node = self._goto[node].get(ch, 0)
            for pid in self._out[node]:
                seen.add(pid)
        return len(seen)
