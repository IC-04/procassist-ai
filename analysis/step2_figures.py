"""Step 2 figures. matplotlib only, deterministic, no seaborn.

Three figures, each answering one question a reader will ask of the inventory. Restrained
palette, direct labels, no chartjunk, no pie charts, no 3D. Gate failures are shown rather than
hidden — a process excluded by a declared gate is evidence, and the figure annotates which gate
excluded it.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

# Ordinal axes carry no arithmetic; these positions exist only to place a point on a grid.
BAND_POS = {"Low": 0, "Medium": 1, "High": 2, "Unknown": -1}
INK = "#1a1a1a"
MUTED = "#8a8a8a"
ACCENT = "#2f6f9f"
GREY = "#cccccc"


# Dataset B carries Japanese window titles, and one process label is `hr人事給与システム__p09`.
# matplotlib's default font has no CJK coverage and renders them as tofu boxes — caught in Task 7
# validation by looking at the figure rather than at the exit code. A CJK-capable family is
# prepended when the host has one; the ASCII fallback below keeps the label legible when it does
# not, rather than drawing squares.
CJK_FONTS = ("Hiragino Sans", "Hiragino Maru Gothic Pro", "Noto Sans CJK JP", "Noto Sans JP",
             "Yu Gothic", "Meiryo", "Arial Unicode MS", "PingFang SC", "Heiti TC",
             "Apple SD Gothic Neo")
_HAS_CJK = False


def _setup():
    global _HAS_CJK
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager as fm
    import matplotlib.pyplot as plt
    available = {f.name for f in fm.fontManager.ttflist}
    picked = [f for f in CJK_FONTS if f in available]
    _HAS_CJK = bool(picked)
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 150, "font.size": 8,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
        "grid.color": "#ebebeb", "grid.linewidth": 0.6, "axes.axisbelow": True,
        "svg.hashsalt": "step2",          # determinism
        "font.family": "sans-serif",
        "font.sans-serif": picked + ["DejaVu Sans"],
    })
    return plt


def _short(label: str) -> str:
    """Shorten for display, and keep it legible when the host has no CJK font."""
    if not _HAS_CJK:
        label = "".join(c if ord(c) < 0x2E80 else "\u25a1" for c in label)
    return label if len(label) <= 30 else label[:27] + "\u2026"


def _failed_gate(gates: Dict[str, Any], label: str) -> str:
    g = gates.get(label, {})
    for k in ("G1_evidence_sufficiency", "G2_is_business_work", "G3_has_target_surface"):
        if k in g and not g[k]["pass"]:
            return k.split("_")[0]
    return ""


def render(inv: Dict[str, Any], out_dir: str) -> Dict[str, str]:
    plt = _setup()
    os.makedirs(out_dir, exist_ok=True)
    procs: List[Dict] = inv["processes"]
    gates = inv.get("_gates", {})
    written: Dict[str, str] = {}

    # ---------------------------------------------------- 1. impact x suitability
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    jitter = {}
    for p in procs:
        key = (BAND_POS[p["impact_band"]], BAND_POS[p["suitability_band"]])
        jitter.setdefault(key, []).append(p)
    # Labels are STACKED, not jittered: several processes share a band cell, and horizontal
    # jitter alone made them illegible (seen in Task 7 validation). Points fan out slightly;
    # the text is laid out in a column with a leader offset so nothing overlaps.
    for (x, y), members in sorted(jitter.items()):
        members = sorted(members, key=lambda q: (-q["share_of_segmented_time"], q["label"]))
        n = len(members)
        for i, p in enumerate(members):
            dx = (i - (n - 1) / 2) * 0.12
            passed = p["gates_all_pass"]
            ax.scatter([x + dx], [y], s=40 + 260 * p["share_of_segmented_time"],
                       color=ACCENT if passed else GREY,
                       edgecolor=INK if passed else MUTED, linewidth=0.6,
                       zorder=3 if passed else 2)
            fg = "" if passed else f"  ({_failed_gate(gates, p['label'])})"
            ax.annotate(_short(p["label"]) + fg, (x, y),
                        textcoords="offset points", xytext=(0, 13 + 9.5 * (n - 1 - i)),
                        ha="center", fontsize=6,
                        color=INK if passed else MUTED, zorder=4)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["Low", "Medium", "High"])
    ax.set_yticks([0, 1, 2]); ax.set_yticklabels(["Low", "Medium", "High"])
    ax.set_xlim(-0.6, 2.6); ax.set_ylim(-0.6, 3.0)
    ax.set_xlabel("Impact band  (share of segmented time · executions · operators · sessions)")
    ax.set_ylabel("Suitability band  (route-set Jaccard · transfer · apps · concentration)")
    ax.set_title("Dataset B — impact × suitability (ordinal; the axes are never summed)",
                 loc="left", fontsize=9)
    ax.text(0.0, -0.17, "Point area ∝ share of segmented time. Grey = excluded by a declared "
                        "gate, annotated with the gate that excluded it.\nWithin a cell, "
                        "labels read top-to-bottom in the same order as their points read "
                        "left-to-right.",
            transform=ax.transAxes, fontsize=6.5, color=MUTED)
    fig.tight_layout()
    p1 = os.path.join(out_dir, "impact_suitability.png")
    fig.savefig(p1, bbox_inches="tight"); plt.close(fig)
    written["impact_suitability"] = p1

    # ---------------------------------------------------- 2. time share
    order = sorted(procs, key=lambda p: (p["share_of_segmented_time"], p["label"]))
    fig, ax = plt.subplots(figsize=(7.4, 0.34 * len(order) + 1.4))
    ys = range(len(order))
    ax.barh(list(ys), [p["share_of_segmented_time"] for p in order],
            color=[ACCENT if p["gates_all_pass"] else GREY for p in order],
            edgecolor="none", height=0.66)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([_short(p["label"]) for p in order], fontsize=7)
    for i, p in enumerate(order):
        ax.text(p["share_of_segmented_time"] + 0.004, i,
                f"{p['share_of_segmented_time']*100:.1f}%  (n={p['n_executions']})",
                va="center", fontsize=6.5, color=MUTED)
    ax.set_xlabel("Share of segmented time  —  RELATIVE comparison only; "
                  "waits are compressed in the capture environment")
    ax.set_xlim(0, max(p["share_of_segmented_time"] for p in order) * 1.28)
    ax.set_title("Dataset B — observed time share by process label", loc="left", fontsize=9)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    p2 = os.path.join(out_dir, "time_share.png")
    fig.savefig(p2, bbox_inches="tight"); plt.close(fig)
    written["time_share"] = p2

    # ---------------------------------------------------- 3. determinism
    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    pts = [p for p in procs if p["route_set_jaccard"] is not None
           and p["surface_set_jaccard"] is not None]
    # Labels sit BESIDE their point, not above it. Above-the-point placement plus a flip rule
    # put labels on top of each other and, worse, next to the wrong marker — visible in Task 7
    # validation. Side placement keeps the attachment unambiguous; points near the right edge
    # flip to the left. Deterministic: fixed visit order, no randomness.
    for p in sorted(pts, key=lambda q: (-q["n_executions"], q["label"])):
        x, y = p["route_set_jaccard"], p["surface_set_jaccard"]
        r = 18 + 7 * p["n_executions"]
        ax.scatter([x], [y], s=r, color=ACCENT if p["gates_all_pass"] else GREY,
                   edgecolor=INK if p["gates_all_pass"] else MUTED, linewidth=0.6,
                   alpha=0.85, zorder=3)
        right = x < 0.62
        pad = 4 + (r ** 0.5) / 2
        ax.annotate(_short(p["label"]), (x, y), textcoords="offset points",
                    xytext=(pad if right else -pad, 0),
                    ha="left" if right else "right", va="center", fontsize=6,
                    color=INK if p["gates_all_pass"] else MUTED, zorder=4)

    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=0.6, linestyle=":", zorder=1)
    ax.set_xlim(-0.30, 1.12); ax.set_ylim(-0.03, 1.08)
    ax.set_xlabel("Mean pairwise Jaccard of the ROUTE set  (operative measure)")
    ax.set_ylabel("Mean pairwise Jaccard of the SURFACE set")
    ax.set_title("Dataset B — execution-to-execution repeatability within a process",
                 loc="left", fontsize=9)
    ax.text(0.0, -0.15, "Point area ∝ executions. A PROXY for the Bosco et al. (BPM 2019) "
                        "determinism condition, not a validated production predictor.",
            transform=ax.transAxes, fontsize=6.5, color=MUTED)
    fig.tight_layout()
    p3 = os.path.join(out_dir, "determinism.png")
    fig.savefig(p3, bbox_inches="tight"); plt.close(fig)
    written["determinism"] = p3

    return written
