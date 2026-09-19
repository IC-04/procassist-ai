"""A recorded trace of what the engine actually did, step by step, with real timings.

The engine already performs every one of these steps; until now they were invisible, which
made a deterministic system look like a black box for no reason. Each step names its
mechanism — `lookup`, `threshold`, `template`, `audit` — so a reader can see the system is
deterministic **by choice**, not by accident.

Timings are measured with `perf_counter`, not estimated. They are small, and that is part of
the point: the expensive thing in this workflow was never the computation.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class Trace:
    """An append-only list of (step, mechanism, detail, milliseconds)."""

    __slots__ = ("steps", "_t0")

    def __init__(self) -> None:
        self.steps: List[Dict[str, Any]] = []
        self._t0 = time.perf_counter()

    def step(self, name_en: str, name_ja: str, mechanism: str, detail_ja: str,
             detail_en: str = "", link: Optional[str] = None) -> None:
        """Close the current step. Elapsed time is measured from the previous close."""
        now = time.perf_counter()
        self.steps.append({
            "n": len(self.steps) + 1,
            "name_en": name_en,
            "name_ja": name_ja,
            "mechanism": mechanism,
            "detail_ja": detail_ja,
            "detail_en": detail_en or detail_ja,
            "link": link,
            "ms": round((now - self._t0) * 1000, 2),
        })
        self._t0 = now

    def dump(self) -> Dict[str, Any]:
        return {
            "steps": list(self.steps),
            "total_ms": round(sum(s["ms"] for s in self.steps), 2),
            "mechanisms": sorted({s["mechanism"] for s in self.steps}),
            "note_en": ("every step is a deterministic lookup, comparison or template "
                        "substitution; no model is consulted at any point"),
            "note_ja": "すべての手順は決定的な参照・比較・テンプレート置換です。モデルは一切使用しません。",
        }
