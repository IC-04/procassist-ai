"""Tests for `procmine/identity.py` — representation, similarity, grouping (S-E6).

Four things are asserted, in the order they matter:

  1. **The G-A0 contract.** Grouping never touches a boundary. Identity is a labelling of a
     frozen segmentation, so boundary metrics must be byte-identical whatever the arm does.
  2. Determinism under a fixed seed.
  3. No ground truth reaches the module (AST, not grep — the Phase C test learned that).
  4. It runs on `dataset_b` and selects its own `k` there, with `dataset_a/` irrelevant.
"""
from __future__ import annotations
import ast, os
import pytest

from procmine import identity as ID, evaluate as EV

pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("networkx")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _row(ts, et="keystroke", app="App", title="T", route="", url=""):
    return {"ts_ms": ts, "event_type": et, "app_name": app, "title": title, "route": route,
            "url": url, "origin": "", "ms_since_last": 100, "element_label": "", "element_id": "",
            "field_key": "", "layer": "L3"}


def _block(i, a, b, surface="app:App:T", route="", title="T"):
    return {"block_id": f"s#b{i}", "idx": i, "start_ms": a, "end_ms": b, "surface": surface,
            "app": "App", "title": title, "route": route, "origin": "", "n_events": 3,
            "element_labels": [], "element_ids": [], "field_keys": [], "value_hashes": []}


def _world(n_seg=12):
    """n_seg alternating two-shape executions across three sessions."""
    segs, rows, blocks = [], {}, {}
    for k in range(n_seg):
        sid = f"ses_{k % 3}"
        a = 100000 * k
        shape = ["app:Alpha:Invoice", "web:https://x/pay"] if k % 2 == 0 else \
                ["app:Beta:Report", "web:https://y/rep"]
        rows.setdefault(sid, [])
        blocks.setdefault(sid, [])
        for j, s in enumerate(shape):
            blocks[sid].append(_block(len(blocks[sid]), a + j * 20000, a + j * 20000 + 19000,
                                      surface=s, title=s.split(":")[-1]))
            for t in range(5):
                rows[sid].append(_row(a + j * 20000 + t * 100,
                                      et="keystroke" if k % 2 == 0 else "mouse_click"))
        segs.append({"session_id": sid, "start_ms": a, "end_ms": a + 39000})
    return segs, rows, blocks


def _reps():
    segs, rows, blocks = _world()
    return segs, [ID.represent(s, rows[s["session_id"]], blocks[s["session_id"]]) for s in segs]


# ---------------------------------------------------------------- 1. the G-A0 contract

def test_grouping_cannot_move_a_boundary():
    """Boundary metrics are a function of the intervals alone. Whatever labels an arm assigns,
    boundary F1 must not move — that is the S-E6 contract, and a moved F1 is a violation, not
    a result."""
    segs, reps = _reps()
    ref = {"ses_0": {"intervals": [(0, 39000), (200000, 239000)], "labels": ["A", "A"]}}
    hyp_iv = [(s["start_ms"], s["end_ms"]) for s in segs if s["session_id"] == "ses_0"]
    cfg = {"taus_ms": [2000], "kappas": [], "ious": [0.5], "timelines": {}}

    base = None
    for labels in ([f"L{i}" for i in range(len(hyp_iv))],      # all distinct
                   ["same"] * len(hyp_iv),                      # all merged
                   ["a", "b"] * (len(hyp_iv) // 2 + 1)):        # alternating
        h = {"ses_0": {"intervals": hyp_iv, "labels": list(labels)[:len(hyp_iv)]}}
        m = EV.evaluate_all(ref, h, cfg)["overall"]["boundary_time"]["2000"]
        if base is None:
            base = m
        assert m == base, "labelling changed a boundary metric — G-A0 violated"


def test_group_returns_one_label_per_segment_and_mutates_nothing():
    segs, reps = _reps()
    snapshot = [dict(s) for s in segs]
    g = ID.group(reps, k=4, seed=7)
    assert len(g["labels"]) == len(reps)
    assert segs == snapshot


# ---------------------------------------------------------------- 2. determinism

def test_grouping_is_deterministic_under_a_fixed_seed():
    _, reps = _reps()
    a = ID.group(reps, k=4, seed=7)
    b = ID.group(reps, k=4, seed=7)
    assert a["labels"] == b["labels"]
    assert a["n_clusters"] == b["n_clusters"]


def test_similarity_is_symmetric_with_unit_diagonal():
    _, reps = _reps()
    S = ID.combine(ID.similarity_views(reps))
    import numpy as np
    assert np.allclose(S, S.T, atol=1e-5)
    assert np.allclose(np.diag(S), 1.0, atol=1e-5)
    assert float(S.min()) >= 0.0 and float(S.max()) <= 1.0


def test_two_shapes_are_more_similar_within_than_across():
    """The representation has to separate the two synthetic processes at all, or nothing
    downstream can."""
    _, reps = _reps()
    S = ID.combine(ID.similarity_views(reps))
    within = [S[i, j] for i in range(len(reps)) for j in range(len(reps))
              if i != j and i % 2 == j % 2]
    across = [S[i, j] for i in range(len(reps)) for j in range(len(reps)) if i % 2 != j % 2]
    assert sum(within) / len(within) > sum(across) / len(across)


def test_views_are_present_and_named():
    _, reps = _reps()
    v = ID.similarity_views(reps)
    assert set(v) == {"where", "how", "what", "seq"}
    a = ID.audit(reps)
    assert set(a) >= {"where", "how", "what", "n_executions"}
    assert 0.0 <= a["what"]["coverage"] <= 1.0


# ---------------------------------------------------------------- 3. GT leakage (AST)

def test_identity_py_reads_no_ground_truth():
    tree = ast.parse(open(ID.__file__, encoding="utf-8").read())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
            modules.update(f"{node.module or ''}.{a.name}" for a in node.names)
    assert not any(m.rsplit(".", 1)[-1] == "gt" or m.endswith(".gt") for m in modules)
    assert not any(m.rsplit(".", 1)[-1] == "evaluate" for m in modules)

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
    forbidden = ("process_code", "case_id", "family_name", "split_id", "task_id",
                 "expected_boundaries", "executions_canonical", "gt_manifest")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            for f in forbidden:
                assert f not in node.value, f"identity.py names a GT field in code: {f!r}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            assert node.slice.value not in ("process_code", "case_id", "variant",
                                            "family_name", "split_id", "phase", "task_id")


# ---------------------------------------------------------------- 4. runs on dataset_b

@pytest.mark.skipif(not os.path.isdir(os.path.join(ROOT, "dataset_b")),
                    reason="dataset_b not present")
def test_selects_its_own_k_on_dataset_b():
    """ADR-010: A's `k` never transfers. The grouping must pick its own community count from
    whatever data is in front of it, with `dataset_a/` playing no part."""
    from procmine import normalise as N, blocks as BK
    segs, rows, blocks = [], {}, {}
    sess = list(N.iter_session_dirs(os.path.join(ROOT, "dataset_b")))[:4]
    for sd in sess:
        sid = os.path.basename(sd)
        r = N.load_session(sd)
        if not r:
            continue
        b = BK.build_blocks(r)
        rows[sid], blocks[sid] = r, b
        for i in range(0, max(0, len(b) - 3), 3):       # crude fixed windows; only the
            segs.append({"session_id": sid,             # grouping is under test here
                         "start_ms": b[i]["start_ms"], "end_ms": b[i + 2]["end_ms"]})
    if len(segs) < 10:
        pytest.skip("too few dataset_b segments to group")
    reps = [ID.represent(s, rows[s["session_id"]], blocks[s["session_id"]]) for s in segs]
    g = ID.group(reps, k=10, seed=7)
    assert 1 < g["n_clusters"] <= len(reps)
    assert g["modularity"] is not None
    assert len(g["labels"]) == len(reps)
