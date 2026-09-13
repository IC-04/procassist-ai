"""Stage C — TEKG construction (TEKG_SPEC.md)."""
from __future__ import annotations

from procmine import blocks as B, tekg as G
from conftest import ev, flat


SPEC_RELATIONS = {
    "temporal_next", "same_surface_as", "returns_to", "same_route_as",
    "same_system_as", "same_field_as", "shared_value_with", "dataflow_to",
}


def _blocks(*events, **kw):
    return B.build_blocks(flat(*events), min_events=kw.pop("min_events", 1),
                          min_ms=kw.pop("min_ms", 0))


def test_relation_vocabulary_is_exactly_the_eight_in_the_spec():
    assert {G.NEXT, G.SAME_SURFACE, G.RETURNS_TO, G.SAME_ROUTE, G.SAME_ORIGIN,
            G.SAME_FIELD, G.SHARED_VALUE, G.DATAFLOW} == SPEC_RELATIONS


def test_emitted_relations_stay_inside_the_vocabulary():
    bl = _blocks(*[ev(i * 1000, app="Edge", title="T", url=f"http://h{i%2}/#/r{i%3}",
                      field=f"f{i%2}") for i in range(10)])
    rels = {r for (_s, r, _d, _a) in G.build_graph(bl)["edges"]}
    assert rels <= SPEC_RELATIONS


def test_edges_never_cross_a_session_boundary():
    a = _blocks(ev(1000, app="W", title="x", session="ses_a"),
                ev(2000, app="E", title="y", session="ses_a"))
    b = _blocks(ev(3000, app="W", title="x", session="ses_b"),
                ev(4000, app="E", title="y", session="ses_b"))
    g = G.build_graph(a + b)
    for (s, _r, d, _at) in g["edges"]:
        assert s.split("#")[0] == d.split("#")[0], f"{s} -> {d} crosses sessions"


def test_max_lag_is_respected():
    bl = _blocks(*[ev(i * 1000, app="A", title=f"t{i % 4}") for i in range(30)])
    for lag in (2, 5, 12):
        for (_s, rel, _d, at) in G.build_graph(bl, max_lag=lag)["edges"]:
            if rel != G.NEXT and at.get("lag") is not None:
                assert at["lag"] <= lag


def test_temporal_next_is_adjacent_and_carries_a_gap():
    bl = _blocks(ev(0, app="A", title="a"), ev(5000, app="B", title="b"))
    nxt = [(s, d, at) for (s, r, d, at) in G.build_graph(bl)["edges"] if r == G.NEXT]
    assert len(nxt) == 1
    assert nxt[0][2]["gap_ms"] == 5000


def test_returns_to_marks_the_interruption_signature_only_when_non_adjacent():
    bl = _blocks(ev(0, app="A", title="a"), ev(1000, app="B", title="b"),
                 ev(2000, app="A", title="a"))
    edges = G.build_graph(bl)["edges"]
    assert any(r == G.RETURNS_TO and at["lag"] == 2 for (_s, r, _d, at) in edges)
    # adjacent identical surfaces cannot occur (they would be one block), so every
    # returns_to must have lag > 1
    assert all(at["lag"] > 1 for (_s, r, _d, at) in edges if r == G.RETURNS_TO)


def test_shared_field_and_value_edges_carry_cardinality():
    bl = _blocks(ev(0, app="A", title="a", field="f1", vhash="v1"),
                 ev(1000, app="B", title="b"),
                 ev(2000, app="C", title="c", field="f1", vhash="v1"))
    edges = G.build_graph(bl)["edges"]
    for rel in (G.SAME_FIELD, G.SHARED_VALUE):
        matching = [at for (_s, r, _d, at) in edges if r == rel]
        assert matching and all(at["n"] >= 1 for at in matching)


def test_nodes_match_the_blocks():
    bl = _blocks(*[ev(i * 1000, app=f"A{i}", title="t") for i in range(5)])
    g = G.build_graph(bl)
    assert g["nodes"] == [b["block_id"] for b in bl]


def test_graph_is_deterministic():
    bl = _blocks(*[ev(i * 1000, app="A", title=f"t{i % 3}", field=f"f{i % 2}")
                   for i in range(12)])
    assert G.build_graph(bl)["edges"] == G.build_graph(bl)["edges"]


def test_local_evidence_stays_inside_its_window():
    bl = _blocks(*[ev(i * 1000, app="A", title=f"t{i % 4}") for i in range(20)])
    g = G.build_graph(bl)
    evd = G.local_evidence(g, 10, bl, window=3)
    ids = {b["block_id"] for b in evd["window"]}
    assert len(evd["window"]) == 7
    for e in evd["evidence"]:
        assert e["src"] in ids and e["dst"] in ids
        assert e["rel"] != G.NEXT


def test_local_evidence_clamps_at_the_edges():
    bl = _blocks(*[ev(i * 1000, app="A", title=f"t{i}") for i in range(4)])
    g = G.build_graph(bl)
    assert len(G.local_evidence(g, 0, bl, window=5)["window"]) == 4


def test_attach_dataflow_is_optional_and_absent_tolerant():
    """extensions.* is undocumented and optional (DATA_CONTRACT §0): zero coverage
    must produce zero edges, not an error."""
    rows = flat(*[ev(i * 1000, app="A", title=f"t{i}") for i in range(4)])
    bl = B.build_blocks(rows, min_events=1, min_ms=0)
    g = G.build_graph(bl)
    assert G.attach_dataflow(g, rows, bl) == 0


def test_edge_summary_counts_by_relation():
    bl = _blocks(ev(0, app="A", title="a"), ev(1000, app="B", title="b"))
    s = G.edge_summary(G.build_graph(bl))
    assert s.get(G.NEXT) == 1
    assert set(s) <= SPEC_RELATIONS
