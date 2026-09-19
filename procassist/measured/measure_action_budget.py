"""Measure the per-disposition action budget from Dataset B. Run to regenerate; not imported.

Writes `procassist/measured/action_budget.json`, which IS committed, so the demo states
measured numbers without needing `dataset_b/` present at runtime.

    .venv/bin/python -m procassist.measured.measure_action_budget

What is counted, per `(origin, route)` — the module key, ADR-022, never the Step 1 label:

  * `word_switches`  — transitions of the foreground application into WINWORD.EXE while that
    route was the last browser route seen. This is the Word round trip the panel removes.
  * `dispositions`   — clicks on that screen's `btn-*-ok`.
  * `comment_chars`  — the length of every distinct string typed into that screen's `*-note`.

The ratio is reported with a Wilson 95% interval, and everything downstream uses the interval,
never the point estimate.
"""
from __future__ import annotations

import collections
import glob
import json
import math
import os
import re
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "action_budget.json")
BTN_OK = re.compile(r"^btn-\w{2}-ok$")


def wilson(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson interval. Hand-rolled: it is four lines and adds no dependency."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def measure(pattern: str = "dataset_b/*/*/events.jsonl") -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    for path in glob.glob(pattern):
        with open(path, encoding="utf-8") as fh:
            events.extend(json.loads(line) for line in fh if line.strip())
    events.sort(key=lambda e: (e.get("session_id", ""), e.get("timestamp_ms") or 0))

    switches: collections.Counter = collections.Counter()
    dispositions: collections.Counter = collections.Counter()
    lengths: Dict[str, List[int]] = collections.defaultdict(list)
    route, app = None, None

    for event in events:
        ctx = event.get("context") or {}
        process = ((ctx.get("active_app") or {}).get("process_name") or "").lower()
        url = ((ctx.get("active_browser_tab") or {}).get("url")) or ""
        if url:
            route = url
        if process and process != app:
            if "winword" in process and route:
                switches[route] += 1
            app = process
        payload = event.get("payload") or {}
        target = payload.get("target_element") or payload.get("element") or {}
        if not isinstance(target, dict):
            continue
        element_id = target.get("automation_id") or (target.get("attributes") or {}).get("id")
        if not element_id or not route:
            continue
        if BTN_OK.match(str(element_id)):
            dispositions[route] += 1
        value = target.get("value")
        if str(element_id).endswith("-note") and isinstance(value, str) and value.strip():
            lengths[route].append(len(value))

    rows: Dict[str, Any] = {}
    for key in sorted(set(switches) | set(dispositions)):
        n = dispositions[key]
        s = switches[key]
        lo, hi = wilson(min(s, n), n)
        observed = sorted(set(lengths.get(key, [])))
        rows[key] = {
            "word_switches": s,
            "dispositions": n,
            "switches_per_disposition": round(s / n, 4) if n else None,
            "switches_ci95": [round(lo, 4), round(hi, 4)],
            "comment_chars_observed": {
                "n_distinct": len(observed),
                "min": observed[0] if observed else None,
                "max": observed[-1] if observed else None,
                "median": observed[len(observed) // 2] if observed else None,
            },
        }
    return {
        "measured_from": "dataset_b/*/*/events.jsonl",
        "n_events": len(events),
        "keyed_on": "(origin, route) — the module key (ADR-022), never the Step 1 label",
        "interval": "Wilson 95%",
        "caveat_en": ("counts of actions only. No seconds, no yen, no FTE: waiting times were "
                      "compressed in the capture environment, so no absolute time claim can be "
                      "made from this corpus."),
        "by_route": rows,
    }


if __name__ == "__main__":
    data = measure()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    print(f"wrote {OUT}: {len(data['by_route'])} routes from {data['n_events']} events")
