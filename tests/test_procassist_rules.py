"""Tier arithmetic, band semantics, the declared ceiling, and the four statuses.

第２条's tiers overlap as written — ¥135,181 satisfies both `5万円以上` and `10万円以上` — and are
read as bands, most-specific tier winning, so the applicable authority is 社長承認. The overlap
is kept as an `INF` note, not as the verdict. The verdict (`OK` vs `FLAG`) then turns on the
queue's declared authority ceiling. See procassist/core/rules.py and definitions/*.toml.
"""
from __future__ import annotations

import os

import pytest

from procassist.adapters.defs import load_all, registry
from procassist.adapters.documents import DocumentIndex
from procassist.core.definitions import Status
from procassist.core.rules import (SEMANTICS, format_amount_jpy, matching_tiers,
                                   parse_amount_jpy, strictest_tier)

RULE_ID = "3ece1f98df11:c002"


@pytest.fixture(scope="module")
def tiers():
    """The real tiers, read from the corpus — not a fixture we wrote."""
    if not os.path.exists("build/dataset_b/evidence/documents.jsonl"):
        pytest.skip("Dataset B evidence is not present")
    parsed = DocumentIndex.load().parsed_rule(RULE_ID)
    assert parsed is not None, "接待交際費規程 第２条 is missing from documents.jsonl"
    return parsed["tiers"]


def test_the_corpus_has_exactly_three_tiers(tiers):
    assert [t["value_jpy"] for t in tiers] == [50000.0, 50000.0, 100000.0]
    assert [t["consequent"] for t in tiers] == ["部門長承認", "役員承認", "社長承認"]


@pytest.mark.parametrize(
    "amount,n_literal_matches,applicable",
    [
        (1, 1, "部門長承認"),
        (49_999, 1, "部門長承認"),
        (50_000, 1, "役員承認"),        # boundary: 5万円未満 false, 5万円以上 true
        (50_001, 1, "役員承認"),
        (60_936, 1, "役員承認"),        # the real record P1-07089771-005
        (99_999, 1, "役員承認"),
        (100_000, 2, "社長承認"),       # boundary: the literal overlap starts here
        (135_181, 2, "社長承認"),       # the real record P1-07106250-010
        (3_000_000, 2, "社長承認"),
    ],
)
def test_band_semantics_select_one_authority_at_every_boundary(tiers, amount,
                                                               n_literal_matches, applicable):
    """However many tiers match literally, band semantics select exactly one authority."""
    matched = matching_tiers(amount, tiers)
    assert len(matched) == n_literal_matches
    assert strictest_tier(matched)["consequent"] == applicable


def test_the_semantics_choice_is_named_not_implicit():
    assert SEMANTICS == "MOST_SPECIFIC_TIER"


@pytest.mark.parametrize(
    "definition_id,authority,exceeds",
    [
        ("hr_expense_settlement", "部門長承認", False),
        ("hr_expense_settlement", "役員承認", False),      # the declared ceiling itself
        ("hr_expense_settlement", "社長承認", True),       # what makes case 2 a FLAG
        ("fi_managerial_expense_approval", "部門長承認", False),
        ("fi_managerial_expense_approval", "役員承認", True),
    ],
)
def test_the_ceiling_decides_flag_not_the_clause(definition_id, authority, exceeds):
    ladder = registry().by_id[definition_id].authority
    assert ladder is not None
    assert ladder.exceeds_ceiling(authority) is exceeds


def test_every_declared_ceiling_states_its_evidence_basis():
    """The half of the rule that is not quoted from the document must say so."""
    for definition in registry().all:
        ladder = definition.authority
        if ladder is None:
            continue
        assert ladder.basis in ("OBSERVED", "DERIVED", "INF"), ladder.basis
        assert ladder.basis_note_ja and ladder.basis_note_en
        assert ladder.ceiling_ja in ladder.ladder_ja
        if ladder.basis == "INF":
            assert "[INF]" in ladder.basis_note_ja


def test_the_ladder_is_quoted_from_the_clause():
    """ladder_ja must be exactly the consequents the corpus's clause names, in order."""
    from procassist.adapters.documents import DocumentIndex
    if not os.path.exists("build/dataset_b/evidence/documents.jsonl"):
        pytest.skip("Dataset B evidence is not present")
    parsed = DocumentIndex.load().parsed_rule(RULE_ID)
    quoted = list(dict.fromkeys(t["consequent"] for t in parsed["tiers"]))
    for definition in registry().all:
        if definition.authority is not None:
            assert definition.authority.ladder_ja == quoted


@pytest.mark.parametrize(
    "raw,expected",
    [("135,181円", 135181), ("6,066円", 6066), ("1,832,962円", 1832962), ("100円", 100),
     (None, None), ("", None), ("—", None), ("135181", None), ("¥135,181", None),
     ("135,181 yen", None)],
)
def test_amount_parsing_is_strict(raw, expected):
    assert parse_amount_jpy(raw) == expected


def test_amount_formatting_uses_en_as_a_suffix_not_a_sign():
    assert format_amount_jpy(135181) == "135,181円"
    assert "¥" not in format_amount_jpy(1832962)


def test_no_definition_restates_the_tiers():
    """The thresholds must live in the corpus, not be copied into a definition file."""
    for path_text in (open(d, encoding="utf-8").read() for d in _definition_paths()):
        assert "50000" not in path_text and "100000" not in path_text


def _definition_paths():
    import os
    from procassist.adapters.paths import DEFINITIONS
    return [os.path.join(DEFINITIONS, n) for n in sorted(os.listdir(DEFINITIONS))
            if n.endswith(".toml")]


def test_every_definition_validates_and_claims_a_distinct_host():
    definitions = load_all()
    assert len(definitions) >= 3
    hosts = [(d.host.origin, d.host.route) for d in definitions]
    assert len(set(hosts)) == len(hosts)


def test_status_vocabulary_is_exactly_four():
    assert {s.value for s in Status} == {"OK", "FLAG", "REQUIRES_REVIEW", "MISS"}
