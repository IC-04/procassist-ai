"""Stage 3 — candidate generation (STEP1_SPEC §3.2, DATA_CONTRACT §10.2).

The four guarantees the generator makes are each pinned here, because everything downstream
inherits them: a boundary the generator never nominates cannot be recovered by any scorer,
gate or decoder.
"""
from __future__ import annotations
import os, json
import pytest

from procmine import normalise as N, blocks as B, candidates as CA
from conftest import ev, flat, needs_b, DATASET_B


def rows_one_block():
    """One surface throughout, so every candidate inside is genuinely intra-block."""
    return flat(*[ev(1000 + i * 200, app="Word", title="doc", et="keystroke")
                  for i in range(12)])


# ---------------------------------------------------------------- contract 1: superset

def test_every_block_edge_is_emitted_as_a_candidate():
    rows = flat(ev(0, app="W", title="a"), ev(3000, app="E", title="b"),
                ev(6000, app="N", title="c"))
    bl = B.build_blocks(rows, min_events=1, min_ms=0)
    cand = CA.generate(rows, bl)
    edges = {b["first_seq"] for b in bl}
    got = {c["at_seq"] for c in cand if c["kind"] == "block_edge"}
    assert edges <= got, "the old candidate space must be a strict subset of the new one"
    assert len(bl) == len(edges)


@needs_b
def test_every_block_edge_survives_on_real_data():
    rows = N.load_session(os.path.join(DATASET_B, "ses_20260701-183232-LAPTOP-76QMG9DE"))
    bl = B.build_blocks(rows)
    cand = CA.generate(rows, bl)
    edge_seqs = {c["at_seq"] for c in cand if c["kind"] == "block_edge"}
    assert {b["first_seq"] for b in bl} <= edge_seqs


# ---------------------------------------------------------------- contract 2: intra-block

@needs_b
def test_a_candidate_is_placed_strictly_inside_a_block_on_real_data():
    """The whole point of ADR-015: a boundary may sit BETWEEN two events inside a block."""
    rows = N.load_session(os.path.join(DATASET_B, "ses_20260701-183232-LAPTOP-76QMG9DE"))
    bl = B.build_blocks(rows)
    by_id = {b["block_id"]: b for b in bl}
    intra = [c for c in CA.generate(rows, bl) if c["kind"] == "intra_block"]
    assert intra, "no intra-block candidate produced on real data"
    strict = [c for c in intra
              if by_id[c["block_id"]]["first_seq"] < c["at_seq"] <= by_id[c["block_id"]]["last_seq"]]
    assert strict, "no candidate sits strictly inside a block"


def test_intra_block_candidates_are_not_a_fixed_stride():
    """Contract 2: event-level structure, never a time grid or every-nth-event rule."""
    rows = rows_one_block()
    bl = B.build_blocks(rows, min_events=1, min_ms=0)
    cand = CA.generate(rows, bl)
    # a uniform run of keystrokes on one surface offers no structure to trigger on
    assert [c for c in cand if c["kind"] == "intra_block"] == []


# ---------------------------------------------------------------- contract 3: self-switch

def test_a_candidate_is_nominated_at_a_self_referential_app_switch():
    """S-E2: app_switch at 71.0% of missed boundaries while app_change is 0.6%. These create
    no block edge and are the largest recoverable mass (ADR-014 kept them in the stream)."""
    rows = flat(
        ev(0, app="Word", title="doc", et="keystroke"),
        ev(1000, app="Word", title="doc", et="keystroke"),
        ev(2000, app="Word", title="doc", et="app_switch", new_app="Word", previous_app="Word"),
        ev(3000, app="Word", title="doc", et="keystroke"),
    )
    bl = B.build_blocks(rows, min_events=1, min_ms=0)
    assert len(bl) == 1, "the self-switch must not create a block edge"
    cand = CA.generate(rows, bl)
    at = [c for c in cand if c["at_seq"] == 2]
    assert at, "no candidate at the self-referential app_switch"
    assert at[0]["kind"] == "intra_block"
    assert "app_switch_self" in at[0]["triggers"]
    assert at[0]["features"]["app_switch_self_at"] is True
    assert at[0]["features"]["app_change"] is False


@needs_b
def test_self_switch_candidates_exist_on_real_data():
    rows = N.load_session(os.path.join(DATASET_B, "ses_20260701-183232-LAPTOP-76QMG9DE"))
    bl = B.build_blocks(rows)
    cand = CA.generate(rows, bl)
    assert [c for c in cand if "app_switch_self" in c["triggers"]]


# ---------------------------------------------------------------- contract 4: determinism

def test_generation_is_deterministic():
    rows = rows_one_block()
    bl = B.build_blocks(rows, min_events=1, min_ms=0)
    a = CA.generate(rows, bl)
    b = CA.generate(rows, bl)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


@needs_b
def test_generation_is_deterministic_on_real_data():
    rows = N.load_session(os.path.join(DATASET_B, "ses_20260701-183232-LAPTOP-76QMG9DE"))
    bl = B.build_blocks(rows)
    assert json.dumps(CA.generate(rows, bl), sort_keys=True) == \
        json.dumps(CA.generate(rows, bl), sort_keys=True)


def test_candidates_py_imports_no_ground_truth_module():
    """Contract 4: the generator cannot be fitted to the answer, even accidentally.

    Parsed with `ast` rather than grepped, so the module's own prose explaining that it does
    NOT read ground truth cannot fail its own test — only real imports and real string
    literals in executable code count.
    """
    import ast
    tree = ast.parse(open(CA.__file__, encoding="utf-8").read())

    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
            modules.update(f"{node.module or ''}.{a.name}" for a in node.names)
    assert not any("gt" == m.rsplit(".", 1)[-1] or m.endswith(".gt") for m in modules), \
        f"candidates.py imports a ground-truth module: {sorted(modules)}"

    # docstrings are prose; every OTHER string literal is code and must not name a GT artifact
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
    forbidden = ("executions_canonical", "expected_boundaries", "gt_events",
                 "gt.jsonl", "gt_manifest", "executions.jsonl")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            for f in forbidden:
                assert f not in node.value, \
                    f"candidates.py names a ground-truth artifact in code: {f!r}"


# ---------------------------------------------------------------- shape / invariants

@needs_b
def test_record_matches_the_data_contract():
    rows = N.load_session(os.path.join(DATASET_B, "ses_20260701-183232-LAPTOP-76QMG9DE"))
    bl = B.build_blocks(rows)
    for c in CA.generate(rows, bl):
        assert set(c) >= {"cand_id", "session_id", "at_seq", "at_ms", "block_id",
                          "kind", "features"}
        assert c["kind"] in ("block_edge", "intra_block")
        assert isinstance(c["at_seq"], int)
        for k, v in c["features"].items():
            assert isinstance(v, (int, float, bool)), f"{k} is not numeric or boolean"


@needs_b
def test_at_seq_is_strictly_increasing_within_a_session():
    rows = N.load_session(os.path.join(DATASET_B, "ses_20260701-183232-LAPTOP-76QMG9DE"))
    seqs = [c["at_seq"] for c in CA.generate(rows, B.build_blocks(rows))]
    assert seqs == sorted(set(seqs))


def test_generator_handles_empty_input():
    assert CA.generate([], []) == []
    assert CA.generate(rows_one_block(), []) == []


@needs_b
def test_generator_runs_on_dataset_b_without_raising():
    total = 0
    for sd in N.iter_session_dirs(DATASET_B):
        rows = N.load_session(sd)
        if not rows:
            continue
        bl = B.build_blocks(rows)
        c = CA.generate(rows, bl)
        total += len(c)
        assert CA.density(c, rows, bl)["per_event"] <= 1.0
    assert total > 0


def test_mode_transition_is_featurised_but_does_not_trigger():
    """§3.2.1 requires the interaction-mode transition as a FEATURE; it is not a trigger
    because it fires on 77.7% of intra-block positions and pushed dataset_b density to
    0.33/event, over the gate."""
    assert "mode_transition" not in CA.ENABLED_TRIGGERS
    rows = flat(ev(0, app="W", title="d", et="keystroke"),
                ev(1000, app="W", title="d", et="app_switch",
                   new_app="W", previous_app="W"))
    bl = B.build_blocks(rows, min_events=1, min_ms=0)
    c = CA.generate(rows, bl)
    assert "mode_transition" in c[0]["features"]


# ---------------------------------------------------------------- blocks §10.1

@needs_b
def test_block_seq_span_invariants_on_real_data():
    """DATA_CONTRACT §10.1: first_seq <= last_seq, and blocks tile the session contiguously."""
    for sd in N.iter_session_dirs(DATASET_B):
        rows = N.load_session(sd)
        if not rows:
            continue
        bl = B.build_blocks(rows)
        for b in bl:
            assert b["first_seq"] <= b["last_seq"]
        for a, c in zip(bl, bl[1:]):
            assert a["last_seq"] + 1 == c["first_seq"]
        assert bl[0]["first_seq"] == 0
        assert bl[-1]["last_seq"] == len(rows) - 1
