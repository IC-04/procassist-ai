"""S-E7 — the Step 1 freeze contract.

Four things this file exists to prevent regressing:

  1. the granularity-fair identity metric behaves as specified, including coverage accounting
  2. the validator checks what DATA_CONTRACT §6.7 actually requires
  3. labelling is deterministic and cannot move a boundary
  4. no inference module reads a ground-truth artifact — checked over EVERY inference module,
     by AST, so a new module cannot be added without being covered
"""
from __future__ import annotations
import ast, os
import pytest

from procmine import evaluate as EV, validate_segments as VS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every module downstream of perception that participates in inference. `evaluate`, `gt` and
# `baselines` are evaluation-only and are deliberately NOT in this list.
INFERENCE_MODULES = ("normalise", "blocks", "candidates", "score", "gate", "decoder",
                     "label", "identity", "tekg", "context", "emit_segments")

GT_FIELDS = ("process_code", "case_id", "variant", "family_name", "split_id", "phase",
             "task_id", "expected_boundaries")


# ---------------------------------------------------------------- 1. the fair metric

def _bundle(iv, lab):
    return {"s": {"intervals": iv, "labels": lab}}


def test_pointwise_identity_covers_the_whole_timeline_and_labels_gaps():
    tl = {"s": list(range(0, 1001, 10))}
    ref = _bundle([(0, 200), (600, 800)], ["A", "B"])
    hyp = _bundle([(0, 200), (600, 800)], ["x", "y"])
    m = EV.pointwise_identity(ref, hyp, tl, "event")
    assert m["ari"] == 1.0
    assert m["n_points"] == len(tl["s"])            # 100% of the timeline, nothing dropped
    assert 0.0 < m["reference_coverage"] < 1.0      # the gap is real and is reported
    assert EV.UNASSIGNED not in ("A", "B", "x", "y")


def test_pointwise_identity_does_not_reward_over_segmentation():
    """Splitting one correct segment into ten, each with its own label, must not raise the
    score — that is the whole reason this metric exists."""
    tl = {"s": list(range(0, 1001, 10))}
    ref = _bundle([(0, 500), (500, 1000)], ["A", "B"])
    coarse = _bundle([(0, 500), (500, 1000)], ["x", "y"])
    split = _bundle([(i, i + 100) for i in range(0, 1000, 100)],
                    [f"s{i}" for i in range(10)])
    assert EV.pointwise_identity(ref, split, tl, "event")["ari"] < \
           EV.pointwise_identity(ref, coarse, tl, "event")["ari"]


def test_pointwise_identity_time_unit_is_not_event_weighted():
    """A dense burst of events must not out-weigh a long quiet execution."""
    tl = {"s": [0] * 0 + list(range(0, 100, 1)) + [5000, 10000]}
    ref = _bundle([(0, 100), (4000, 11000)], ["A", "B"])
    hyp = _bundle([(0, 100), (4000, 11000)], ["x", "y"])
    ev = EV.pointwise_identity(ref, hyp, tl, "event")
    tm = EV.pointwise_identity(ref, hyp, tl, "time", bin_ms=1000)
    assert ev["n_points"] != tm["n_points"]
    assert tm["unit"] == "time" and tm["bin_ms"] == 1000


def test_pointwise_identity_rejects_an_unknown_unit():
    with pytest.raises(ValueError):
        EV.pointwise_identity(_bundle([(0, 1)], ["A"]), _bundle([(0, 1)], ["x"]),
                              {"s": [0, 1]}, unit="furlongs")


# ---------------------------------------------------------------- 2. the validator

def test_generator_has_no_chunk_derived_trigger():
    """DATA_CONTRACT §6.7 checked at the SOURCE. The output check can only say a boundary
    coincides with a chunk edge; the clause forbids one placed BECAUSE of it, which is a
    property of the generator."""
    assert VS.chunk_triggers_in_generator() == []


def test_intra_block_boundary_on_a_chunk_edge_is_not_a_violation():
    """The bug this replaced: `justified` was built from BLOCK boundaries, which was right for
    the Phase B emitter and wrong from ADR-015 onward, when a boundary became allowed to occur
    inside a block. A valid intra-block boundary that happens to land on a chunk edge is a
    coincidence, not a violation."""
    seg = [{"session_id": "s", "start": "2026-07-01T00:00:10Z", "end": "2026-07-01T00:00:40Z",
            "label": "p"}]
    edge = {"s": {1782864010}}                                 # the start second
    justified = {"s": {1782864010}}                            # a candidate sits there
    assert VS.check_no_chunk_boundaries(seg, edge, justified) == []


def test_chunk_derived_boundary_with_no_other_explanation_is_a_violation():
    seg = [{"session_id": "s", "start": "2026-07-01T00:00:10Z", "end": "2026-07-01T00:00:40Z",
            "label": "p"}]
    edge = {"s": {1782864010}}
    assert VS.check_no_chunk_boundaries(seg, edge, {"s": set()}) != []


# ---------------------------------------------------------------- 3. no GT in inference

@pytest.mark.parametrize("mod", INFERENCE_MODULES)
def test_no_inference_module_reads_ground_truth(mod):
    path = os.path.join(ROOT, "procmine", f"{mod}.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module or ''}.{a.name}" for a in node.names)
    assert not any(m.rsplit(".", 1)[-1] == "gt" for m in imported), f"{mod} imports gt"

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            for f in GT_FIELDS:
                assert f not in node.value, f"{mod} names the GT field {f!r} in code"


def test_the_inference_module_list_is_complete():
    """A new module under procmine/ must be classified, so leakage coverage cannot be lost by
    simply adding a file."""
    evaluation_only = {"gt", "evaluate", "baselines", "schemas", "validate_segments", "cli",
                       "__init__"}
    present = {f[:-3] for f in os.listdir(os.path.join(ROOT, "procmine"))
               if f.endswith(".py")}
    unclassified = present - set(INFERENCE_MODULES) - evaluation_only
    assert not unclassified, f"unclassified module(s): {sorted(unclassified)}"
