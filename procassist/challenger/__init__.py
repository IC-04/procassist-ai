"""The challenger: a local retriever, run beside the lookup table so it can lose in public.

ADR-024 recorded that a `(module, record type) → document` table reaches 64.2% (95% Wilson CI
56.2–71.5%) on n=148 labelled pairs over 17 document labels, and that a learned retriever would
have to exceed **71.5%** before that evidence could tell the two apart at all. The table won the
pre-registered comparison and is what ships.

This module exists so a reviewer can watch the alternative run rather than take that on trust.
It is BM25 over character 3-grams plus a character-n-gram cosine, entirely local: no API key,
no network, no embedding download, no model file. Japanese has no whitespace, so character
n-grams are the tokeniser — and that is also why this is a reasonable challenger rather than a
straw man.

**It is not evaluated.** The 148 labelled pairs behind the 64.2% are not recoverable from the
committed artifacts (`retrieval_feasibility.json` keeps the aggregates, not the pairs), and
regenerating them would mean reopening frozen Step 2 extraction. So what the panel shows is a
live comparison, explicitly labelled UNEVALUATED, against a bar that was set in advance. That
is a weaker claim than "the model scores X", and it is the one the evidence supports.
"""
from __future__ import annotations

from .retriever import Challenger, ChallengerResult, hybrid_scores

__all__ = ["Challenger", "ChallengerResult", "hybrid_scores"]
