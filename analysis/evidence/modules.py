"""Module identity for Dataset B.

reads only:  nothing at import; `crosscheck` consumes already-loaded captures
writes only: nothing

Step 1's labels are ORIGIN-BLIND: `procmine.label._name()` builds a slug from the route alone, so
`/payroll-items` on the HR portal and `/payroll-items` on the Finance portal collapse into one
label even though they are different business modules in different systems. Every figure in this
layer is therefore keyed on `module_id` derived from `(origin, route)`, never on the Step 1 label.

The map is taken verbatim from `analysis/step2_reanalysis.py`, where each entry was read off a
Dataset B screenshot showing the URL bar, the breadcrumb/H1 and the highlighted nav item together.

A SECOND, INDEPENDENT key exists and is used as a cross-check rather than as a source: business
record ids are `P<n>-<8 digits>-<3 digits>`, and the `P<n>` prefix is measured to co-occur with a
single portal origin (P1-P5 -> :5132 HR, P6-P10 -> :5133 FI, P11-P13 -> :5134 LO). The prefix-to-
module association is derived at RUNTIME from co-occurrence, never hard-coded, and a record whose
prefix disagrees with the URL of the capture it was read from is RECORDED as a disagreement, not
silently resolved.
"""
from __future__ import annotations

import collections
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# (origin, route) -> (module_id, system, name_ja, name_en)
MODULE: Dict[Tuple[str, str], Tuple[str, str, str, str]] = {
    ('http://127.0.0.1:5132', '/payroll-items'):      ('M01', 'HR', '経費精算・給与変更', 'expense settlement + payroll change'),
    ('http://127.0.0.1:5132', '/leave-applications'): ('M02', 'HR', '勤怠・休暇申請', 'attendance & leave applications'),
    ('http://127.0.0.1:5132', '/onboarding'):         ('M03', 'HR', '入社手続き', 'onboarding verification'),
    ('http://127.0.0.1:5132', '/social-insurance'):   ('M04', 'HR', '福利厚生申請', 'benefits applications'),
    ('http://127.0.0.1:5133', '/payroll-items'):      ('M05', 'FI', '請求書承認・経費精算', 'invoice approval'),
    ('http://127.0.0.1:5133', '/onboarding'):         ('M06', 'FI', '支払処理', 'payment processing'),
    ('http://127.0.0.1:5133', '/leave-applications'): ('M07', 'FI', '経費承認（管理職）', 'managerial expense approval'),
    ('http://127.0.0.1:5133', '/resident-tax'):       ('M08', 'FI', '発注管理', 'purchase-order management'),
    ('http://127.0.0.1:5134', '/payroll-items'):      ('M09', 'LO', '在庫管理', 'inventory management'),
    ('http://127.0.0.1:5134', '/leave-applications'): ('M10', 'LO', '契約管理', 'contract management'),
    ('http://127.0.0.1:5134', '/social-insurance'):   ('M11', 'LO', 'IT申請', 'IT requests'),
}
PORTAL_ROUTES = ("/", "/dashboard", "")
PORTAL = ("PORTAL", "-", "ポータル", "portal / dashboard")

ALL_MODULE_IDS: Tuple[str, ...] = tuple(sorted({v[0] for v in MODULE.values()}))


def split_url(url: Optional[str]) -> Tuple[str, str]:
    """`http://127.0.0.1:5133/#/payroll-items` -> ('http://127.0.0.1:5133', '/payroll-items').

    The portal is a hash-router SPA, so the business route lives after `#`. A URL with no
    fragment is the portal root.
    """
    if not url:
        return ("", "")
    base, _, frag = url.partition("#")
    origin = base.split("/")[0] + "//" + base.split("//", 1)[1].split("/")[0] if "//" in base else ""
    route = frag if frag.startswith("/") else ("/" + frag if frag else "/")
    if not frag:
        # no fragment: the path itself, minus a trailing slash, is all we have
        path = base.split("//", 1)[1] if "//" in base else base
        path = path[path.find("/"):] if "/" in path else "/"
        route = path or "/"
    return (origin, route)


def module_of_url(url: Optional[str]) -> Optional[Tuple[str, str, str, str]]:
    """Module for a browser URL, or `PORTAL` for the root/dashboard, or None when unknown."""
    origin, route = split_url(url)
    if not origin:
        return None
    if route in PORTAL_ROUTES:
        return PORTAL
    return MODULE.get((origin, route))


def module_id_of_url(url: Optional[str]) -> Optional[str]:
    m = module_of_url(url)
    return m[0] if m else None


def record_prefix(record_id: str) -> Optional[str]:
    """`P6-07010448-001` -> `P6`."""
    if not record_id or not record_id.startswith("P"):
        return None
    head = record_id.split("-", 1)[0]
    return head if head[1:].isdigit() else None


def learn_prefix_map(pairs: Iterable[Tuple[str, Optional[str]]]) -> Dict[str, Dict[str, Any]]:
    """Derive `P<n>` -> module from observed co-occurrence. Never hard-coded.

    `pairs` is (record_id, module_id_from_url). Returns, per prefix, the modal module and the
    full distribution, so a caller can see how clean the association is rather than trusting it.
    """
    dist: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for rid, mid in pairs:
        p = record_prefix(rid)
        if p and mid and mid != "PORTAL":
            dist[p][mid] += 1
    out: Dict[str, Dict[str, Any]] = {}
    for p in sorted(dist):
        c = dist[p]
        total = sum(c.values())
        modal, n = c.most_common(1)[0]
        out[p] = {"modal_module_id": modal, "support": n, "total": total,
                  "purity": round(n / total, 4), "distribution": dict(c.most_common())}
    return out


def crosscheck(record_id: str, module_id_from_url: Optional[str],
               prefix_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compare the two independent module keys. A disagreement is reported, never resolved.

    `module_id` stays the URL-derived value — it is the authoritative one, read off the address
    bar of the capture the record came from. The prefix is corroboration.
    """
    p = record_prefix(record_id)
    expected = (prefix_map.get(p) or {}).get("modal_module_id") if p else None
    agree: Optional[bool] = None
    if expected and module_id_from_url and module_id_from_url != "PORTAL":
        agree = (expected == module_id_from_url)
    return {"record_prefix": p, "prefix_modal_module_id": expected,
            "module_id_agrees_with_prefix": agree}
