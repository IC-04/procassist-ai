"""Stage 5 — the ambiguity gate (STEP1_SPEC §3.4).

Splits scored candidates into three bands: confident boundary, confident non-boundary, and an
uncertain middle that a semantic adjudicator would be asked about. **Nothing is sent to an LLM
here** — `--no-llm` is the only mode that exists in this phase, and every routed candidate falls
back to its deterministic `rule_decision`. That fallback is tested before any adjudicator exists,
so the pipeline can never become dependent on a stage that may be ablated away (ADR-018).

The Phase 1 warning still applies: the gate cannot route on "did the surface change" — those are
the easy ones. Its discriminator is score *uncertainty*, which is surface-agnostic.
"""
from __future__ import annotations
import collections
from typing import Any, Dict, List, Optional, Sequence

# Band edges on the score. Both are fitted on Dataset A and declared as such in thresholds.json.
DEFAULT_CFG = {
    "low": 0.35,        # below -> confident NOT a boundary
    "high": 0.65,       # above -> confident boundary
    "max_route_fraction": 0.15,   # STEP1_SPEC §3.4 target; widened bands if exceeded
}


def ambiguity(score: float, low: float, high: float) -> float:
    """0 at the band edges, 1 at the midpoint. A pure function of distance from confidence."""
    mid = (low + high) / 2.0
    half = max(1e-9, (high - low) / 2.0)
    return round(max(0.0, 1.0 - abs(score - mid) / half), 4)


def route(candidates_scored: Sequence[Dict], cfg: Optional[Dict] = None) -> List[Dict]:
    """Attach `route`, `rule_decision` and `ambiguity` to each scored candidate.

    `rule_decision` is the deterministic answer and is ALWAYS populated, including for routed
    candidates — that is what makes `--no-llm` a complete execution mode rather than a
    degraded one.
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    low, high = float(c["low"]), float(c["high"])
    out: List[Dict] = []
    for cand in candidates_scored:
        s = float(cand.get("score") or 0.0)
        d = dict(cand)
        d["rule_decision"] = bool(s >= (low + high) / 2.0)
        d["ambiguity"] = ambiguity(s, low, high)
        d["route"] = "llm" if (low <= s <= high) else "rule"
        out.append(d)
    return out


def routing_report(routed: Sequence[Dict], labels: Optional[Sequence[int]] = None,
                   bins: int = 10) -> Dict[str, Any]:
    """Size, composition and rule-only precision of the routed population.

    This is a required output, not a diagnostic: it is the number that decides whether an
    adjudicator stage is worth building at all. The routed population is NOT S-E2's category
    (d) — that was 14 boundaries. It is the low-precision mass.
    """
    n = len(routed)
    r = [x for x in routed if x["route"] == "llm"]
    hist = collections.Counter(min(bins - 1, int(float(x.get("score") or 0) * bins))
                               for x in routed)
    out: Dict[str, Any] = {
        "n_candidates": n,
        "n_routed": len(r),
        "routing_fraction": round(len(r) / n, 4) if n else None,
        "score_histogram": {f"{i/bins:.1f}-{(i+1)/bins:.1f}": hist.get(i, 0)
                            for i in range(bins)},
        "rule_decision_true": sum(1 for x in routed if x["rule_decision"]),
    }
    if labels is not None and len(labels) == n:
        pos = sum(labels)
        rpos = sum(l for x, l in zip(routed, labels) if x["route"] == "llm")
        rule_tp = sum(l for x, l in zip(routed, labels)
                      if x["route"] == "llm" and x["rule_decision"])
        rule_pred = sum(1 for x in routed if x["route"] == "llm" and x["rule_decision"])
        out.update({
            "true_boundaries_total": pos,
            "true_boundaries_in_routed": rpos,
            "routed_share_of_true_boundaries": round(rpos / pos, 4) if pos else None,
            "routed_population_base_rate": round(rpos / len(r), 4) if r else None,
            "rule_only_precision_on_routed": round(rule_tp / rule_pred, 4) if rule_pred else None,
            "rule_only_recall_on_routed": round(rule_tp / rpos, 4) if rpos else None,
        })
    return out
