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

from procmine import identity as ID, evaluate as EV, label as LB

# NOT importorskip. These are hard requirements of the SHIPPED identity method (ADR-021), and
# skipping when they are missing is precisely how the S-E9 degradation stayed invisible: the
# suite was green on a host that could not run the method it was supposed to be testing. If
# these cannot be imported, this module must FAIL.
_missing = LB.missing_graph_dependencies()
assert not _missing, (
    f"the graph identity method requires {list(LB.REQUIRED_FOR_GRAPH)} and cannot import "
    f"{_missing}. Run `make setup` and use .venv/bin/python. These tests must fail rather "
    f"than skip: a skipped identity suite hides a deliverable built by a different method.")

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
    assert {"where", "how", "what", "seq"} <= set(v)
    assert set(v["_applicable"]) == {"where", "how", "what", "seq"}
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


# ---------------------------------------------------------------- S-E6b: IDF and combination

def test_idf_discounts_a_universal_term():
    """The measured S-E6 defect: a surface every execution visits carried the same weight as a
    unique one. IDF must reduce the similarity of two executions whose ONLY shared surface is
    universal, without reducing it for a shared rare surface."""
    sets = [["universal", f"rare{i}"] for i in range(10)]
    plain = ID._binary_jaccard(sets, idf=False)
    idfed = ID._binary_jaccard(sets, idf=True)
    assert idfed[0, 1] < plain[0, 1]
    same = [["universal", "shared"] for _ in range(10)]
    assert ID._binary_jaccard(same, idf=True)[0, 1] == pytest.approx(1.0, abs=1e-5)


def test_combine_modes_agree_on_the_trivial_cases_and_differ_on_disjointness():
    _, reps = _reps()
    v = ID.similarity_views(reps)
    import numpy as np
    mats = {m: ID.combine(v, mode=m) for m in ID.COMBINE_MODES}
    for m, S in mats.items():
        assert np.allclose(np.diag(S), 1.0, atol=1e-5), m
        assert np.allclose(S, S.T, atol=1e-5), m
        assert float(S.min()) >= 0.0 and float(S.max()) <= 1.0, m
    # noisy_or lets a single strong view carry a pair, so it is never below the linear sum
    assert float(mats["noisy_or"].mean()) >= float(mats["linear"].mean())


def test_unknown_combine_mode_is_an_error_not_a_silent_default():
    _, reps = _reps()
    with pytest.raises(ValueError):
        ID.combine(ID.similarity_views(reps), mode="bogus")


# ---------------------------------------------------------------- S-E7: freeze

def test_tiebreak_discards_a_saturated_where_term():
    """S-E6b measured the residual to be pairs whose surface sets are IDENTICAL. A Jaccard of
    1.0 is maximally similar and minimally informative, so above the saturation threshold the
    WHERE term must be discarded and the pair decided on WHAT and sequence alone."""
    import numpy as np
    _, reps = _reps()
    v = ID.similarity_views(reps)
    sat = v["_parts"]["surface"]
    lin = ID.combine(v, mode="linear")
    tb = ID.combine(v, mode="tiebreak")
    off = ~np.eye(len(reps), dtype=bool)
    saturated = (sat >= ID.SATURATED_WHERE) & off
    unsaturated = (sat < ID.SATURATED_WHERE) & off
    if unsaturated.any():
        assert np.allclose(lin[unsaturated], tb[unsaturated], atol=1e-5)
    if saturated.any():
        # On saturated pairs the value must be the WHAT/seq-only combination, whatever that is.
        w = ID.DEFAULT_WEIGHTS
        tot = w["what"] + w["seq"]
        alt = (w["what"] / tot) * v["what"] + (w["seq"] / tot) * v["seq"]
        assert np.allclose(np.clip(alt, 0, 1)[saturated], tb[saturated], atol=1e-5)


def test_grouping_is_byte_identical_across_repeated_runs():
    """The freeze contract: same input, same seed, same assignment — every time."""
    _, reps = _reps()
    sess = [r["session_id"] for r in reps]
    a = ID.select_config(reps, sess, seed=7, weightings=("where_heavy",), modes=("tiebreak",))
    b = ID.select_config(reps, sess, seed=7, weightings=("where_heavy",), modes=("tiebreak",))
    a.pop("_views"); b.pop("_views")
    assert a == b
    import json
    Sa = ID.combine(ID.similarity_views(reps), ID.WEIGHT_GRID["where_heavy"], mode="tiebreak")
    Sb = ID.combine(ID.similarity_views(reps), ID.WEIGHT_GRID["where_heavy"], mode="tiebreak")
    assert json.dumps(ID.louvain(ID.knn_graph(Sa, k=5), seed=7)) == \
           json.dumps(ID.louvain(ID.knn_graph(Sb, k=5), seed=7))
