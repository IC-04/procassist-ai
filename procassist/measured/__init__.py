"""Numbers measured once from Dataset B and committed, so the demo needs no raw telemetry.

Regenerate with `.venv/bin/python -m procassist.measured.measure_action_budget`.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict

HERE = os.path.dirname(os.path.abspath(__file__))
ACTION_BUDGET = os.path.join(HERE, "action_budget.json")


@lru_cache(maxsize=1)
def measured_action_budget() -> Dict[str, Any]:
    with open(ACTION_BUDGET, encoding="utf-8") as fh:
        return json.load(fh)
