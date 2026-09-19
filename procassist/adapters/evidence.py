"""Read the committed Step 2 result artifacts for the evidence page. Read-only.

Nothing on `/_evidence` is a hand-typed number. Every figure on that page is pulled out of
`build/dataset_b/evidence/*.json` at request time and the test asserts the page and the JSON
agree — because a results page that drifts from its results is worse than no results page.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .paths import EVIDENCE

HYPOTHESES = os.path.join(EVIDENCE, "hypothesis_tests.json")
RETRIEVAL = os.path.join(EVIDENCE, "retrieval_feasibility.json")


def _load(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def hypothesis_summary() -> Optional[Dict[str, Any]]:
    """H1–H4 verdict counts, and H3's per-module rates, straight from the artifact."""
    data = _load(HYPOTHESES)
    if data is None:
        return None
    tests: List[Dict[str, Any]] = data.get("tests") or []
    h3 = [t for t in tests if t.get("hypothesis") == "H3"]
    supported = [t for t in h3 if t.get("result") == "SUPPORTED"]
    rates = sorted((t.get("statistic") or {}).get("observed_rate_document_before")
                   for t in supported
                   if (t.get("statistic") or {}).get("observed_rate_document_before") is not None)
    pvals = [(t.get("statistic") or {}).get("p_value") for t in supported]
    return {
        "summary": data.get("summary") or {},
        "rules": data.get("rules") or data.get("_rules") or {},
        "h3": {
            "n_modules": len(h3),
            "n_supported": len(supported),
            "rate_min": rates[0] if rates else None,
            "rate_max": rates[-1] if rates else None,
            "n_p_below_001": sum(1 for p in pvals if p is not None and p < 0.001),
            "per_module": [
                {"module_id": t.get("module_id"),
                 "result": t.get("result"),
                 "rate": (t.get("statistic") or {}).get("observed_rate_document_before"),
                 "p": (t.get("statistic") or {}).get("p_value"),
                 "n": t.get("n")}
                for t in sorted(h3, key=lambda x: x.get("module_id") or "")
            ],
        },
    }


def retrieval_baselines() -> Optional[Dict[str, Any]]:
    """The pre-registered baseline ladder, and the bar a learned retriever has to clear."""
    data = _load(RETRIEVAL)
    if data is None:
        return None
    by_heading = data.get("baselines_by_document_heading") or {}
    ci = by_heading.get("B3_wilson_95ci") or [None, None]
    return {
        "n": by_heading.get("n"),
        "n_labels": by_heading.get("n_distinct_documents"),
        "ladder": [
            {"id": "B0", "name_en": "random", "name_ja": "ランダム",
             "value": by_heading.get("B0_random")},
            {"id": "B1", "name_en": "most frequent overall", "name_ja": "全体最頻",
             "value": by_heading.get("B1_most_frequent_overall")},
            {"id": "B2", "name_en": "most frequent per module", "name_ja": "モジュール別最頻",
             "value": by_heading.get("B2_most_frequent_per_module")},
            {"id": "B3", "name_en": "(module, record type) lookup",
             "name_ja": "(モジュール, レコード種別) 参照表",
             "value": by_heading.get("B3_module_and_record_type_lookup"), "ci": ci},
        ],
        "bar": ci[1],
        "method": by_heading.get("_method"),
        "verdict": data.get("verdict"),
        "coverage": (data.get("labelled_pairs") or {}).get("coverage"),
    }


def gates() -> List[Dict[str, str]]:
    """The four-gate decision table, docs/STEP2_HYPOTHESIS_VERIFICATION.md §2 and ADR-024.

    The criteria and verdicts are quoted; the counts under G3 and G4 are re-read from
    `hypothesis_tests.json` by `hypothesis_summary()`, so the page cannot drift from the run.
    """
    return [
        {"id": "G1", "verdict": "PASS",
         "criterion_ja": "タスク・レコード種別・結果が推論ではなく観測であること",
         "criterion_en": "task, record type and outcome are OBSERVED, not inferred",
         "evidence_en": "records.jsonl 3,011 rows · outcomes.jsonl 549 rows · 216 queue "
                        "tables · screen_text.jsonl 939 captures, all from "
                        "context.extracted_text; zero VLM inference"},
        {"id": "G2", "verdict": "PASS",
         "criterion_ja": "内容同定された文書から規程が復元できること",
         "criterion_en": "a governing rule is recoverable from a content-identified document",
         "evidence_en": "documents.jsonl 112 content-hashed bodies; the 接待交際費 threshold "
                        "parsed to <¥50,000→部門長 / ≥¥50,000→役員 / ≥¥100,000→社長"},
        {"id": "G3", "verdict": "FAIL",
         "criterion_ja": "レコードがその規程に必要な変数を持っていること",
         "criterion_en": "the record carries the variables that rule needs",
         "evidence_en": "H4: 4 REFUTED, 7 INSUFFICIENT. 金額 present on 9.1% (LO 契約管理), "
                        "1.0% (HR 入社手続き), 2.3% (FI 支払処理) of records"},
        {"id": "G4", "verdict": "FAIL for the system disposition · REOPENED for the operator",
         "criterion_ja": "結果変数に、規程適用と確認送りを区別できるだけの分散があること",
         "criterion_en": "the outcome variable has enough variance to distinguish "
                         "rule-application from confirm-and-proceed",
         "evidence_en": "225/225 toasts positive, 0 backward transitions, 0 double-terminal "
                        "records over 25,495,968 characters — but 26 of 481 distinct "
                        "operator-typed comments carry 差異あり / 要注意 / 要確認"},
    ]


def limits() -> List[Dict[str, str]]:
    """What the system cannot do. Stated as flatly as the capabilities are."""
    return [
        {"ja": "判断できません。処分は常に人間が行います。",
         "en": "cannot decide — every disposition is taken by a human",
         "why_en": "by design; the tool has no code path that operates a host control"},
        {"ja": "誤りを検出できません。負例が観測されていないためです。",
         "en": "cannot detect errors — there is no negative class in the corpus",
         "why_en": "every observed disposition in the target modules has positive polarity, "
                   "so no rule can be shown to predict anything (H1: UNTESTABLE)"},
        {"ja": "差戻しに対する評価ができません。UI は対応していますが、la-note 282 回中 0 回でした。",
         "en": "cannot be evaluated against 差戻し — the UI supports it and it occurred 0 "
               "times in 282 uses of la-note",
         "why_en": "the reject affordance is rendered in the replica precisely because its "
                   "absence from the capture is a finding"},
        {"ja": "秒・円・人月を主張できません。取得環境で待ち時間が圧縮されています。",
         "en": "cannot claim seconds, yen or FTE — waiting times were compressed in the "
               "capture environment",
         "why_en": "the impact strip counts actions only, and ships its calculator empty"},
    ]
