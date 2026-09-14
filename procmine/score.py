"""Stage 4 — deterministic candidate scoring (STEP1_SPEC §3.3).

Phase C solved recall: the candidate space reaches 88.0% of GT boundaries at τ = 2 s against a
90.0% ceiling. This stage is entirely a **precision** problem — roughly 28 true boundaries hide
among ~426 candidates per session, so the job is ranking and suppression, not recall.

Two findings from S-E3 shape the design, and both are counter-intuitive enough to state:

1. **The dominant evidence is negative.** Lifts over all boundaries: `shortcut_w` 0.01,
   `keystroke_w` 0.02, `browser_click_w` 0.03, `mouse_click_w` 0.03. These are 25–100×
   discriminators. The strongest positive, `is_web_surface`, is only 1.56. A boundary is
   recognised by what is *absent*.
2. **It is a composition signal, not a gap signal.** `large_relative_gap` has lift 0.91 — no
   signal at all. Boundaries do not sit at the big gaps, so ADR-003 stands and `B2-gap` remains
   worse than random. What marks a boundary is a window containing *navigation without work*.
   This module therefore derives explicit **composition ratios** rather than relying on presence
   flags, and introduces no raw gap threshold.

The model is a plain logistic regression so every prediction decomposes into
`weight × feature` terms that `top_features` reports verbatim. A model that cannot be explained
is worth less here than two points of F1.

Fitting uses the **`clean` GT tier only** (ADR-011) and evaluates leave-one-session-out. No GT
field is ever an input feature — ground truth supplies the label and nothing else.
"""
from __future__ import annotations
import collections, json, math, os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Events that represent the operator *doing the work* rather than moving between screens.
TRANSACTIONAL = ("keystroke", "mouse_click", "browser_click", "mouse_scroll",
                 "shortcut", "clipboard_change", "browser_form_input")
NAVIGATIONAL = ("app_switch", "browser_navigation", "window_title_change")

WINDOW_SECONDS = 4.0        # candidates.py featurises +/- 2000 ms

# Features the model may see. Ordered so weights are comparable across runs.
FEATURE_ORDER = (
    # --- composition (derived here; the S-E3 finding this module exists to encode)
    "transactional_ratio", "navigational_ratio", "transactional_per_sec",
    "navigational_per_sec", "window_event_rate",
    # --- negative evidence, the strongest discriminators S-E3 measured
    "shortcut_w", "keystroke_w", "browser_click_w", "mouse_click_w", "mouse_scroll_w",
    "clipboard_change_w", "browser_form_input_w",
    # --- positive evidence
    "is_web_surface", "app_switch_self_at", "app_switch_at", "app_switch_w",
    "browser_navigation_w", "window_title_change_w",
    "title_change", "route_change", "origin_change", "app_change", "field_key_change",
    # --- structure / position
    "pos_in_block", "is_block_edge", "mode_transition", "large_relative_gap", "rel_gap_capped",
)

# `is_web_surface` is the strongest positive feature and Dataset A is portal-heavy, so it is the
# one most at risk of being A-specific. The ablation is reported, never assumed away.
ABLATION_FEATURE = "is_web_surface"


def composition(feats: Dict[str, Any]) -> Dict[str, float]:
    """Derive composition ratios from the candidate's windowed counts.

    Presence flags say *whether* an event type occurred; ratios say what the window is made
    OF. S-E3's evidence is that a boundary window is navigation-heavy and work-light, which a
    flag cannot express.
    """
    n = float(feats.get("events_in_window") or 0)
    trans = sum(float(feats.get(f"{t}_w_n") or 0) for t in TRANSACTIONAL)
    nav = sum(float(feats.get(f"{t}_w_n") or 0) for t in NAVIGATIONAL)
    return {
        "transactional_ratio": (trans / n) if n else 0.0,
        "navigational_ratio": (nav / n) if n else 0.0,
        "transactional_per_sec": trans / WINDOW_SECONDS,
        "navigational_per_sec": nav / WINDOW_SECONDS,
        "window_event_rate": n / WINDOW_SECONDS,
    }


def vectorise(cand: Dict, drop: Sequence[str] = ()) -> Dict[str, float]:
    """Candidate -> the model's feature vector. Numeric only; no GT field is ever read."""
    f = dict(cand.get("features") or {})
    f.update(composition(f))
    f["is_block_edge"] = 1.0 if cand.get("kind") == "block_edge" else 0.0
    # rel_gap is heavy-tailed; cap rather than threshold, so no gap RULE is reintroduced
    f["rel_gap_capped"] = min(float(f.get("rel_gap") or 0.0), 20.0)
    out: Dict[str, float] = {}
    for k in FEATURE_ORDER:
        if k in drop:
            continue
        v = f.get(k, 0.0)
        out[k] = float(v) if not isinstance(v, bool) else (1.0 if v else 0.0)
    return out


class Scorer:
    """Logistic regression over `FEATURE_ORDER`. Transparent by construction."""

    def __init__(self, names: Sequence[str], weights: Sequence[float], bias: float,
                 mean: Sequence[float], scale: Sequence[float], meta: Optional[Dict] = None):
        self.names = list(names)
        self.weights = list(weights)
        self.bias = float(bias)
        self.mean = list(mean)
        self.scale = list(scale)
        self.meta = meta or {}

    # ---- inference
    def contributions(self, cand: Dict) -> List[Tuple[str, float]]:
        v = vectorise(cand, drop=[n for n in FEATURE_ORDER if n not in self.names])
        out = []
        for i, n in enumerate(self.names):
            z = (v.get(n, 0.0) - self.mean[i]) / (self.scale[i] or 1.0)
            out.append((n, z * self.weights[i]))
        return out

    def score(self, cand: Dict) -> float:
        total = self.bias + sum(c for _n, c in self.contributions(cand))
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, total))))

    def top_features(self, cand: Dict, k: int = 4) -> List[str]:
        """The terms that actually drove this score, signed. What the report cites."""
        cs = self.contributions(cand)
        cs.sort(key=lambda x: -abs(x[1]))
        return [f"{n}{'+' if c >= 0 else '-'}{abs(c):.2f}" for n, c in cs[:k]]

    def apply(self, candidates: Sequence[Dict]) -> List[Dict]:
        out = []
        for c in candidates:
            d = dict(c)
            d["score"] = round(self.score(c), 6)
            d["top_features"] = self.top_features(c)
            out.append(d)
        return out

    # ---- persistence (weights are a declared A->B transfer; see ADR-019)
    def to_dict(self) -> Dict:
        return {"names": self.names, "weights": self.weights, "bias": self.bias,
                "mean": self.mean, "scale": self.scale, "meta": self.meta}

    @classmethod
    def from_dict(cls, d: Dict) -> "Scorer":
        return cls(d["names"], d["weights"], d["bias"], d["mean"], d["scale"],
                   d.get("meta"))


def fit(candidates: Sequence[Dict], labels: Sequence[int],
        drop: Sequence[str] = (), C: float = 1.0, seed: int = 7) -> Scorer:
    """Fit on `clean`-tier-derived labels. `labels[i]` is 1 when the candidate is within τ of a
    GT boundary. The label is the ONLY place ground truth enters."""
    from sklearn.linear_model import LogisticRegression
    import numpy as np

    names = [n for n in FEATURE_ORDER if n not in drop]
    X = np.array([[vectorise(c, drop)[n] for n in names] for c in candidates], dtype=float)
    y = np.array(labels, dtype=int)
    mean = X.mean(axis=0)
    scale = X.std(axis=0)
    scale[scale == 0] = 1.0
    Z = (X - mean) / scale
    m = LogisticRegression(max_iter=2000, C=C, random_state=seed,
                           class_weight="balanced", solver="lbfgs")
    m.fit(Z, y)
    return Scorer(names, list(map(float, m.coef_[0])), float(m.intercept_[0]),
                  list(map(float, mean)), list(map(float, scale)),
                  {"n_train": len(y), "n_positive": int(y.sum()), "C": C,
                   "class_weight": "balanced", "dropped_features": list(drop)})


def ranking_report(scored: Sequence[Dict], labels: Sequence[int]) -> Dict[str, Any]:
    """Ranking quality, independent of any operating point."""
    pairs = sorted(zip((c["score"] for c in scored), labels), key=lambda x: -x[0])
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if not n_pos or not n_neg:
        return {"auc": None, "n_pos": n_pos, "n_neg": n_neg}
    # rank-based AUC
    ranks = {}
    srt = sorted(range(len(labels)), key=lambda i: scored[i]["score"])
    for r, i in enumerate(srt, 1):
        ranks[i] = r
    s = sum(ranks[i] for i, y in enumerate(labels) if y)
    auc = (s - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    out = {"auc": round(auc, 4), "n_pos": n_pos, "n_neg": n_neg}
    for k in (500, 1000, 2000, 3504):
        top = pairs[:k]
        out[f"precision_at_{k}"] = round(sum(y for _s, y in top) / max(1, len(top)), 4)
    return out


def save(scorer: Scorer, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(scorer.to_dict(), fh, ensure_ascii=False, indent=1)


def load(path: str) -> Scorer:
    with open(path, encoding="utf-8") as fh:
        return Scorer.from_dict(json.load(fh))
