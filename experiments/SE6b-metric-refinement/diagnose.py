#!/usr/bin/env python3
"""S-E6b diagnostic — did IDF do what it was supposed to, and was the defect diagnosed right?

IDF cost 0.031 ARI instead of buying anything, and case study 3 moved from 1.000 to 0.991.
Two very different explanations produce that, and they imply opposite next steps:

  (a) IDF is not reducing the similarity of the offending pairs at all  -> implementation bug
  (b) IDF IS reducing it, and they cluster together anyway              -> the defect was
      misdiagnosed: the shared dashboard root is a symptom, not the cause

This measures which.
"""
from __future__ import annotations
import collections, json, os, pickle, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import numpy as np                                     # noqa: E402
from procmine import identity as ID                    # noqa: E402

D = pickle.load(open(os.path.join(ROOT, "build", "dataset_a", "se6_frozen.pkl"), "rb"))
segs = sorted(D["segments"], key=lambda s: (s["session_id"], s["start_ms"]))
reps = [ID.represent(s, D["rows"][s["session_id"]], D["blocks"][s["session_id"]]) for s in segs]
n = len(segs)


def iou(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return 0.0 if hi <= lo else (hi - lo) / ((a[1] - a[0]) + (b[1] - b[0]) - (hi - lo))


by_sess = collections.defaultdict(list)
for i, s in enumerate(segs):
    by_sess[s["session_id"]].append(i)
target = {}
for s in D["sessions"]:
    r = D["ref"].get(s, {})
    hyp = [(segs[i]["start_ms"], segs[i]["end_ms"]) for i in by_sess[s]]
    c = sorted(((-iou(a, b), i, j) for i, a in enumerate(r.get("intervals", []))
                for j, b in enumerate(hyp) if iou(a, b) >= 0.5))
    ur, uh = set(), set()
    for _v, i, j in c:
        if i in ur or j in uh:
            continue
        ur.add(i); uh.add(j); target[by_sess[s][j]] = r["labels"][i]
idx = sorted(target)

V0 = ID.similarity_views(reps, idf=False)
V1 = ID.similarity_views(reps, idf=True)
S0 = ID.combine(V0, ID.WEIGHT_GRID["where_heavy"])
S1 = ID.combine(V1, ID.WEIGHT_GRID["where_heavy"])

out = {}

# --- how much IDF mass does the universal surface actually lose?
surf_sets = [r["where"]["surface_set"] for r in reps]
df = collections.Counter(x for s in surf_sets for x in set(s))
top = df.most_common(6)
out["surface_document_frequency"] = [
    {"surface": s, "df": c, "df_share": round(c / n, 4),
     "idf_weight": round(float(np.log1p(n / c)), 4)} for s, c in top]
out["idf_weight_of_a_singleton"] = round(float(np.log1p(n / 1)), 4)

# --- the offending pairs: same-cluster-worthy by similarity, different process
off0 = S0[np.triu_indices(n, 1)]
thr0 = float(np.percentile(off0, 99.9))
pairs = [(a, b) for a in idx[:900] for b in idx[:900]
         if a < b and target[a] != target[b] and S0[a, b] > thr0]
out["case3"] = {
    "n_pairs": len(pairs),
    "mean_similarity_plain": round(float(np.mean([S0[a, b] for a, b in pairs])), 4),
    "mean_similarity_idf": round(float(np.mean([S1[a, b] for a, b in pairs])), 4),
    "share_sharing_the_top_surface": round(
        sum(1 for a, b in pairs
            if top[0][0] in set(reps[a]["where"]["surface_set"]) &
               set(reps[b]["where"]["surface_set"])) / max(1, len(pairs)), 4),
    "mean_shared_surfaces": round(float(np.mean(
        [len(set(reps[a]["where"]["surface_set"]) & set(reps[b]["where"]["surface_set"]))
         for a, b in pairs])), 2),
    "mean_jaccard_surface_plain": round(float(np.mean(
        [V0["_parts"]["surface"][a, b] for a, b in pairs])), 4),
    "mean_jaccard_surface_idf": round(float(np.mean(
        [V1["_parts"]["surface"][a, b] for a, b in pairs])), 4),
}

# --- the control: same-process pairs. IDF must not damage these more than it damages the above.
same = [(a, b) for a in idx[:900] for b in idx[:900]
        if a < b and target[a] == target[b] and S0[a, b] > thr0]
out["same_process_high_similarity_control"] = {
    "n_pairs": len(same),
    "mean_similarity_plain": round(float(np.mean([S0[a, b] for a, b in same])), 4) if same else None,
    "mean_similarity_idf": round(float(np.mean([S1[a, b] for a, b in same])), 4) if same else None,
}

# --- SEPARABILITY, the number that actually decides whether a metric can work at all:
#     mean within-code similarity minus mean between-code similarity, over matched executions.
sub = np.array(idx)
yy = np.array([target[i] for i in sub])
for name, S in (("plain", S0), ("idf", S1)):
    M = S[np.ix_(sub, sub)]
    same_mask = (yy[:, None] == yy[None, :])
    iu = np.triu_indices(len(sub), 1)
    w = M[iu][same_mask[iu]]
    b = M[iu][~same_mask[iu]]
    out.setdefault("separability", {})[name] = {
        "mean_within_code": round(float(w.mean()), 4),
        "mean_between_code": round(float(b.mean()), 4),
        "gap": round(float(w.mean() - b.mean()), 4),
        "cohens_d": round(float((w.mean() - b.mean()) /
                                np.sqrt(0.5 * (w.var() + b.var()))), 4),
    }

# --- per-view separability: which view could separate processes at all, unsupervised?
for vn in ("where", "how", "what", "seq"):
    for name, V in (("plain", V0), ("idf", V1)):
        M = V[vn][np.ix_(sub, sub)]
        iu = np.triu_indices(len(sub), 1)
        same_mask = (yy[:, None] == yy[None, :])
        w, b = M[iu][same_mask[iu]], M[iu][~same_mask[iu]]
        out.setdefault("per_view_separability", {}).setdefault(vn, {})[name] = {
            "gap": round(float(w.mean() - b.mean()), 4),
            "cohens_d": round(float((w.mean() - b.mean()) /
                                    np.sqrt(0.5 * (w.var() + b.var()) + 1e-12)), 4)}

json.dump(out, open(os.path.join(HERE, "diagnostic.json"), "w"), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
