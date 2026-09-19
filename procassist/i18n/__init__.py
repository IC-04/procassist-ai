"""A committed Japanese-to-English gloss for screen vocabulary. Deterministic, offline.

The engine is already bilingual: every claim it makes carries its own `*_en` alongside the
Japanese, because each was written in both languages when the rule was written. This file
covers only the residue — what the *screen* says: column headers, status words, expense
categories, button labels, placeholders.

Two things it will not do:

  * **It never translates a 規程 clause at runtime.** The one clause gloss in the file is
    human-written, committed, and labelled 参考訳 / reference gloss — not authoritative. The
    Japanese source text is shown in every view, always, and a gloss never replaces it.
  * **It never touches record data.** Ids, names, dates and amounts pass through untouched;
    `135,181円` stays `135,181円`.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
GLOSS = os.path.join(HERE, "gloss_ja_en.json")


@lru_cache(maxsize=1)
def gloss() -> Dict[str, Any]:
    with open(GLOSS, encoding="utf-8") as fh:
        return json.load(fh)


def term(ja: Optional[str]) -> Optional[str]:
    """The English gloss for a screen term, or `None` when we have not written one.

    `None` rather than the Japanese echoed back, so a caller can tell the difference between
    "glossed" and "not glossed" and the UI can stay silent instead of pretending.
    """
    if not ja:
        return None
    return (gloss().get("terms") or {}).get(ja)


def clause_gloss(text_ja: Optional[str]) -> Optional[Dict[str, str]]:
    """The committed reference gloss for a clause, with its not-authoritative labels."""
    if not text_ja:
        return None
    return (gloss().get("clauses") or {}).get(text_ja)
