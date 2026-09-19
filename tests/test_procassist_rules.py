"""Tier arithmetic, the four statuses, and the boundaries that decide them.

The two boundaries are ¥50,000 and ¥100,000, and they behave differently on purpose:
¥50,000 satisfies exactly one tier of 第２条 and is therefore unambiguous, while ¥100,000
satisfies two (`5万円以上` and `10万円以上`) and the clause as written does not choose between
them. See procassist/core/rules.py.
"""
from __future__ import annotations

import os

import pytest

from procassist.adapters.defs import load_all
from procassist.adapters.documents import DocumentIndex
from procassist.core.definitions import Status
from procassist.core.rules import (format_amount_jpy, matching_tiers, parse_amount_jpy,
                                   strictest_tier)

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
    "amount,n_matching,strictest",
    [
        (1, 1, "部門長承認"),
        (49_999, 1, "部門長承認"),
        (50_000, 1, "役員承認"),        # boundary: 5万円未満 is false, 5万円以上 is true
        (50_001, 1, "役員承認"),
        (99_999, 1, "役員承認"),
        (100_000, 2, "社長承認"),       # boundary: two tiers match from here up
        (135_181, 2, "社長承認"),       # the real record P1-07106250-010
        (3_000_000, 2, "社長承認"),
    ],
)
def test_tier_boundaries(tiers, amount, n_matching, strictest):
    matched = matching_tiers(amount, tiers)
    assert len(matched) == n_matching
    assert strictest_tier(matched)["consequent"] == strictest


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
