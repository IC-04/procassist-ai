"""BM25 + character-n-gram cosine over the captured clause corpus. Pure Python, no deps.

Tokenisation is character n-grams because Japanese is not whitespace-delimited; a word-based
tokeniser would need a morphological analyser, which would be a new dependency and, worse,
would make the comparison unfair in the table's favour.
"""
from __future__ import annotations

import collections
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

NGRAM = 3
K1 = 1.5
B = 0.75


def ngrams(text: str, n: int = NGRAM) -> List[str]:
    """Character n-grams. Whitespace and the ideographic space are dropped, nothing else."""
    cleaned = "".join(c for c in (text or "") if not c.isspace())
    if len(cleaned) < n:
        return [cleaned] if cleaned else []
    return [cleaned[i:i + n] for i in range(len(cleaned) - n + 1)]


@dataclass
class Doc:
    doc_id: str
    clause_id: str
    heading_ja: Optional[str]
    text_ja: str
    regulation_hint_ja: str
    tokens: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)

    def key(self) -> str:
        return f"{self.doc_id}:{self.clause_id}"


class Challenger:
    """An index over every clause in the corpus, scored two ways and blended."""

    def __init__(self, docs: Sequence[Doc], alpha: float = 0.5) -> None:
        self.docs = list(docs)
        self.alpha = alpha
        self.n = len(self.docs) or 1
        self.df: collections.Counter = collections.Counter()
        for d in self.docs:
            d.tokens = ngrams(d.text_ja + " " + (d.heading_ja or ""))
            d.counts = dict(collections.Counter(d.tokens))
            for t in set(d.tokens):
                self.df[t] += 1
        self.avg_len = (sum(len(d.tokens) for d in self.docs) / self.n) or 1.0

    @classmethod
    def from_documents(cls, rows: Iterable[Dict[str, Any]], alpha: float = 0.5) -> "Challenger":
        docs: List[Doc] = []
        for row in rows:
            for clause in row.get("clauses") or []:
                text = clause.get("text_ja") or ""
                if len(text) < 12:                       # a fragment is not a retrievable unit
                    continue
                docs.append(Doc(
                    doc_id=row["document_id"],
                    clause_id=clause["clause_id"],
                    heading_ja=clause.get("heading_ja"),
                    text_ja=text,
                    regulation_hint_ja=_regulation_hint(row),
                ))
        return cls(docs, alpha)

    def _idf(self, token: str) -> float:
        df = self.df.get(token, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def bm25(self, query_tokens: Sequence[str], doc: Doc) -> float:
        length = len(doc.tokens) or 1
        score = 0.0
        for token in set(query_tokens):
            tf = doc.counts.get(token, 0)
            if not tf:
                continue
            denom = tf + K1 * (1 - B + B * length / self.avg_len)
            score += self._idf(token) * (tf * (K1 + 1)) / denom
        return score

    @staticmethod
    def cosine(query_tokens: Sequence[str], doc: Doc) -> float:
        q = collections.Counter(query_tokens)
        d = doc.counts
        shared = set(q) & set(d)
        if not shared:
            return 0.0
        dot = sum(q[t] * d[t] for t in shared)
        qn = math.sqrt(sum(v * v for v in q.values()))
        dn = math.sqrt(sum(v * v for v in d.values()))
        return dot / (qn * dn) if qn and dn else 0.0

    def search(self, query_ja: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Top-k clauses by the blended score. Scores are shown; they are not confidences."""
        tokens = ngrams(query_ja)
        if not tokens:
            return []
        raw = [(self.bm25(tokens, d), self.cosine(tokens, d), d) for d in self.docs]
        max_bm = max((r[0] for r in raw), default=0.0) or 1.0
        ranked = sorted(
            ((self.alpha * (bm / max_bm) + (1 - self.alpha) * cos, bm, cos, d)
             for bm, cos, d in raw),
            key=lambda t: (-t[0], t[3].key()),
        )
        return [{
            "rank": i + 1,
            "document_id": d.doc_id,
            "clause_id": d.clause_id,
            "heading_ja": d.heading_ja,
            "text_ja": d.text_ja,
            "regulation_hint_ja": d.regulation_hint_ja,
            "score": round(score, 4),
            "bm25": round(bm, 3),
            "cosine": round(cos, 4),
        } for i, (score, bm, cos, d) in enumerate(ranked[:top_k])]


@dataclass
class ChallengerResult:
    """The two answers side by side, and the reason one of them is authoritative."""

    query_ja: str
    lookup: Optional[Dict[str, Any]]
    retrieved: List[Dict[str, Any]]
    agrees: Optional[bool]
    authority_en: str
    authority_ja: str
    evaluated: bool = False
    bar_en: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "query_ja": self.query_ja,
            "lookup": self.lookup,
            "retrieved": self.retrieved,
            "agrees": self.agrees,
            "authority_en": self.authority_en,
            "authority_ja": self.authority_ja,
            "evaluated": self.evaluated,
            "bar_en": self.bar_en,
        }


def hybrid_scores(challenger: Challenger, query_ja: str,
                  lookup: Optional[Dict[str, Any]], bar: Optional[float]) -> ChallengerResult:
    """Run the retriever and state, flatly, why the table still wins."""
    retrieved = challenger.search(query_ja)
    agrees: Optional[bool] = None
    if lookup and retrieved:
        agrees = (retrieved[0]["document_id"] == lookup.get("document_id")
                  and retrieved[0]["clause_id"] == lookup.get("clause_id"))
    bar_pct = f"{bar * 100:.1f}%" if bar else "the pre-registered bar"
    return ChallengerResult(
        query_ja=query_ja,
        lookup=lookup,
        retrieved=retrieved,
        agrees=agrees,
        authority_en=(
            "The lookup table is authoritative. It won the pre-registered comparison: "
            f"64.2% (95% CI 56.2–71.5%) on n=148 pairs over 17 labels, and a retriever must "
            f"exceed {bar_pct} before this evidence could tell it apart from the table. "
            "This retriever has NOT been scored on those pairs — they are not recoverable "
            "from the committed artifacts — so what you see here is a live illustration, "
            "not a result."),
        authority_ja=(
            "参照表が正です。事前登録した比較で勝っています（n=148・17ラベルで 64.2%、95%CI 56.2–71.5%）。"
            f"検索器が参照表と区別できるには {bar_pct} を超える必要があります。"
            "この検索器はその148件で評価していません（対データが成果物に残っていないため）。"
            "ここに表示されるのは実演であって、評価結果ではありません。"),
        evaluated=False,
        bar_en=bar_pct,
    )


def _regulation_hint(row: Dict[str, Any]) -> str:
    """A human-readable name for a captured body, for display only.

    The Word window title is used when there is one, with the caveat that ADR-025 records:
    a title alias is what the title bar said at capture time and can disagree with the body.
    """
    aliases = row.get("title_aliases") or []
    if aliases:
        return str(aliases[0]).split("  -  ")[0]
    return (row.get("document_id") or "")[:12]
