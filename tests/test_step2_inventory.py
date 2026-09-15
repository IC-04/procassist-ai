"""Step 2 inventory — conformance, determinism, and the no-ground-truth guarantee.

The AST test is the important one. Step 2 reads the frozen Step 1 output and must never touch
Dataset A: a metric computed with knowledge of A's process codes would make the whole Dataset B
analysis circular, and prose saying so is not a test (Phase C learned that).
"""
from __future__ import annotations

import ast
import json
import os
import shutil

import pytest

from analysis import step2_inventory as S
from conftest import needs_b, DATASET_B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_B = os.path.join(ROOT, "build", "dataset_b")
HAS_STEP1 = os.path.exists(os.path.join(BUILD_B, "segments_rich.jsonl"))
needs_step1 = pytest.mark.skipif(
    not HAS_STEP1, reason="build/dataset_b/segments_rich.jsonl absent — run `make run-b`")


# ---------------------------------------------------------------- no ground truth

def test_analysis_package_reads_no_ground_truth():
    """AST, not grep: no GT module imported, and no Dataset A path mentioned in code."""
    pkg = os.path.join(ROOT, "analysis")
    forbidden_paths = ("dataset_a", "build/dataset_a", "gt_manifest", "executions_canonical",
                       "expected_boundaries", "gt.jsonl")
    forbidden_fields = ("process_code", "case_id", "variant", "family_name", "split_id",
                        "phase", "task_id")
    for fn in sorted(f for f in os.listdir(pkg) if f.endswith(".py")):
        tree = ast.parse(open(os.path.join(pkg, fn), encoding="utf-8").read())

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(f"{node.module or ''}.{a.name}" for a in node.names)
        assert not any(m.rsplit(".", 1)[-1] == "gt" for m in imported), f"{fn} imports gt"
        assert not any("baselines" in m for m in imported), f"{fn} imports baselines"

        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                d = ast.get_docstring(node, clean=False)
                if d:
                    docstrings.add(d)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in docstrings:
                    continue
                for bad in forbidden_paths + forbidden_fields:
                    assert bad not in node.value, f"{fn} names {bad!r} in code"


# ---------------------------------------------------------------- gate logic

def _rec(**kw):
    base = dict(label="x", n_executions=10, n_sessions=5, n_operators=3,
                routes=["/payroll-items"], distinct_routes=1, distinct_element_ids=4,
                form_inputs_per_execution=2.0, clipboard_per_execution=2.0)
    base.update(kw)
    return base


@pytest.mark.parametrize("kw,expect", [
    ({}, True),
    ({"n_executions": 5}, True), ({"n_executions": 4}, False),      # boundary
    ({"n_sessions": 3}, True), ({"n_sessions": 2}, False),
    ({"n_operators": 2}, True), ({"n_operators": 1}, False),
])
def test_g1_boundaries(kw, expect):
    assert S.apply_gates(_rec(**kw))["G1_evidence_sufficiency"]["pass"] is expect


@pytest.mark.parametrize("kw,expect", [
    ({"routes": ["/dashboard"], "form_inputs_per_execution": 0.4,
      "clipboard_per_execution": 0.9}, False),                       # all three conditions met
    ({"routes": ["/dashboard"], "form_inputs_per_execution": 0.5,
      "clipboard_per_execution": 0.9}, True),                        # form boundary
    ({"routes": ["/dashboard"], "form_inputs_per_execution": 0.4,
      "clipboard_per_execution": 1.0}, True),                        # clipboard boundary
    ({"routes": ["/dashboard", "/payroll-items"], "form_inputs_per_execution": 0.4,
      "clipboard_per_execution": 0.9}, True),                        # not ALL routes are nav
    ({"routes": ["/"], "form_inputs_per_execution": 0.0,
      "clipboard_per_execution": 0.0}, False),
])
def test_g2_boundaries(kw, expect):
    assert S.apply_gates(_rec(**kw))["G2_is_business_work"]["pass"] is expect


@pytest.mark.parametrize("kw,expect", [
    ({}, True),
    ({"distinct_routes": 0}, False),
    ({"distinct_element_ids": 0}, False),
    ({"distinct_routes": 1, "distinct_element_ids": 1}, True),       # boundary
])
def test_g3_boundaries(kw, expect):
    assert S.apply_gates(_rec(**kw))["G3_has_target_surface"]["pass"] is expect


def test_every_gate_records_the_number_that_decided_it():
    g = S.apply_gates(_rec(n_sessions=1))
    assert g["G1_evidence_sufficiency"]["pass"] is False
    assert "n_sessions=1 < 3" in g["G1_evidence_sufficiency"]["decided_by"]


# ---------------------------------------------------------------- determinism + schema

@needs_b
@needs_step1
def test_two_runs_are_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        inv = S.build(DATASET_B, BUILD_B)
        S.write(inv, str(out))
    for name in ("process_inventory.json", "gates.json", "process_inventory.csv"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


@needs_b
@needs_step1
def test_inventory_matches_the_documented_schema(tmp_path):
    inv = S.build(DATASET_B, BUILD_B)
    S.write(inv, str(tmp_path))
    doc = json.load(open(tmp_path / "process_inventory.json", encoding="utf-8"))

    assert set(doc) >= {"dataset", "generated_from", "totals", "processes"}
    assert set(doc["totals"]) >= {"n_executions", "n_labels", "n_sessions", "n_operators",
                                  "segmented_seconds"}
    assert len(doc["generated_from"]["segments_rich_sha256"]) == 64

    segs = [json.loads(l) for l in
            open(os.path.join(BUILD_B, "segments_rich.jsonl"), encoding="utf-8")]
    assert {p["label"] for p in doc["processes"]} == {s["label"] for s in segs}
    assert sum(p["n_executions"] for p in doc["processes"]) == len(segs)
    assert doc["totals"]["n_executions"] == len(segs)
    assert doc["totals"]["n_labels"] == len(doc["processes"])

    shares = sum(p["share_of_segmented_time"] for p in doc["processes"])
    assert abs(shares - 1.0) <= 1e-6, shares

    # sorted by share descending — the documented order
    order = [p["share_of_segmented_time"] for p in doc["processes"]]
    assert order == sorted(order, reverse=True)

    for p in doc["processes"]:
        assert p["impact_band"] in ("High", "Medium", "Low", "Unknown")
        assert p["suitability_band"] in ("High", "Medium", "Low", "Unknown")
        assert p["n_operators"] <= doc["totals"]["n_operators"]
        assert p["p25_seconds"] <= p["median_seconds"] <= p["p75_seconds"]
        # no composite score may appear anywhere
        assert not any("candidate_score" in k or k == "score_total" for k in p)


@needs_b
@needs_step1
def test_absent_evidence_is_not_reported_as_perfect_determinism():
    """`_binary_jaccard` defines both-empty as 1.0. A label whose executions have NO routes must
    report `null`, not a perfect score."""
    assert S._pairwise_jaccard([[], []]) is None
    assert S._pairwise_jaccard([["/a"], ["/a"]]) == 1.0


@needs_b
@needs_step1
def test_attribution_is_by_seq_not_block_containment():
    """The reason the rule exists: containment drops events for labels averaging under one whole
    block per execution."""
    import collections
    from procmine import normalise as N
    world = S.load_world(DATASET_B, BUILD_B)
    seg = world["segments"][0]
    sid = seg["session_id"]
    rows, blocks = world["rows_by"][sid], world["blocks_by"][sid]
    att = S.attribute(seg, rows, blocks)
    by_hand = [r for r in rows if seg["start_seq"] <= r["seq"] <= seg["end_seq"]]
    assert len(att["events"]) == len(by_hand)
    contained = [b for b in blocks
                 if b["first_seq"] >= seg["start_seq"] and b["last_seq"] <= seg["end_seq"]]
    assert len(att["blocks"]) >= len(contained)


@needs_b
@needs_step1
def test_script_runs_on_dataset_b(tmp_path):
    rc = S.main(["--dataset", DATASET_B, "--build", BUILD_B, "--out", str(tmp_path),
                 "--no-figures"])
    assert rc == 0
    assert (tmp_path / "process_inventory.json").exists()
    assert (tmp_path / "gates.json").exists()
    assert (tmp_path / "process_inventory.csv").exists()
