#!/usr/bin/env python3
"""S-E6b — fix the two similarity defects S-E6 measured, and re-measure the same case studies.

Segmentation is FROZEN: the exact 1,717 S-E4 segments, boundary F1 0.6904 @ tau=2 s. Nothing
here touches the decoder, scorer, gate or candidate generator. Every identity metric comes from
`evaluate.evaluate_all`; none is reimplemented.

  TASK 1  IDF-weight every set-based similarity. Acceptance test: case study 3's 99%.
  TASK 2  adaptive / noisy-OR view combination. Acceptance test: case studies 1 and 2's 13.3%.
  TASK 3  scaffolding contamination — counted and reported, NEVER removed.

Run:  .venv/bin/python experiments/SE6b-metric-refinement/run.py
"""
from __future__ import annotations
import collections, json, os, pickle, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                # noqa: E402
from procmine import identity as ID, evaluate as EV               # noqa: E402

FROZEN = os.path.join(ROOT, "build", "dataset_a", "se6_frozen.pkl")
TAUS = [1000, 2000, 5000, 10000]
SEED, IOU = 7, 0.5


def iou(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return 0.0 if hi <= lo else (hi - lo) / ((a[1] - a[0]) + (b[1] - b[0]) - (hi - lo))


def align(ref_iv, hyp_iv, thr=IOU):
    c = sorted(((-iou(r, h), i, j) for i, r in enumerate(ref_iv)
                for j, h in enumerate(hyp_iv) if iou(r, h) >= thr))
    ur, uh, out = set(), set(), []
    for _v, i, j in c:
        if i in ur or j in uh:
            continue
        ur.add(i); uh.add(j); out.append((i, j))
    return out


# ---- TASK 3: scaffolding signatures. Structural patterns, not a list of A's process names.
SCAFFOLD_FILE = re.compile(r"(?i)\b(setup|readme|launch[_-]?\w*|install|bootstrap|seed|"
                           r"theme[_ -]?\w*|_reference|fixture|scenario)\b")
SCAFFOLD_EXT = re.compile(r"(?i)\.(md|ps1|sh|bat|cmd|ya?ml|ini|cfg|toml)\b")
TERMINAL_APPS = ("WindowsTerminal", "Windows PowerShell", "PowerShell", "cmd", "Command Prompt",
                 "Terminal", "conhost")


def scaffolding_flags(rep):
    apps = rep["where"]["apps"]
    surfaces = rep["where"]["surface_set"]
    text = rep["what"]
    terminal_only = bool(apps) and all(
        any(t.lower() in (a or "").lower() for t in TERMINAL_APPS) for a in apps)
    file_hit = bool(SCAFFOLD_FILE.search(text)) or bool(SCAFFOLD_EXT.search(text))
    terminal_present = any(any(t.lower() in (a or "").lower() for t in TERMINAL_APPS)
                           for a in apps)
    no_web = not any(s.startswith("web:") for s in surfaces)
    return {"terminal_only": terminal_only, "scaffold_filename": file_hit,
            "terminal_present": terminal_present, "no_web_surface": no_web,
            "any": terminal_only or file_hit or (terminal_present and no_web)}


def main() -> int:
    t0 = time.time()
    D = pickle.load(open(FROZEN, "rb"))
    segs = sorted(D["segments"], key=lambda s: (s["session_id"], s["start_ms"]))
    rows, blocks, ref, sessions = D["rows"], D["blocks"], D["ref"], D["sessions"]
    n = len(segs)
    reps = [ID.represent(s, rows[s["session_id"]], blocks[s["session_id"]]) for s in segs]
    print(f"frozen: {n} segments  bF1@2s={D['frozen_boundary']['2000']['f1']}  "
          f"({time.time()-t0:.0f}s)", flush=True)

    by_sess = collections.defaultdict(list)
    for i, s in enumerate(segs):
        by_sess[s["session_id"]].append(i)
    hyp_iv_by = {s: [(segs[i]["start_ms"], segs[i]["end_ms"]) for i in by_sess[s]]
                 for s in sessions}
    target = {}
    for s in sessions:
        r = ref.get(s, {})
        for i, j in align(r.get("intervals", []), hyp_iv_by[s]):
            target[by_sess[s][j]] = r["labels"][i]
    idx_sup = sorted(target)
    y = np.array([target[i] for i in idx_sup])
    cfg = {"taus_ms": TAUS, "kappas": [1, 2, 5, 10], "ious": [0.3, 0.5, 0.7],
           "timelines": {s: [r["ts_ms"] for r in rows[s]] for s in sessions}}
    out = {"frozen": {"n_segments": n, "boundary_time": D["frozen_boundary"],
                      "count_ratio": D["frozen_count_ratio"]},
           "n_matched": len(idx_sup), "n_reference_codes": int(len(set(y.tolist())))}

    # ---------------------------------------------------------- the two similarity worlds
    views = {False: ID.similarity_views(reps, idf=False),
             True: ID.similarity_views(reps, idf=True)}
    print(f"views built ({time.time()-t0:.0f}s)", flush=True)

    # ---------------------------------------------------------- case studies, parameterised
    by_code = collections.defaultdict(list)
    for i in idx_sup:
        by_code[target[i]].append(i)

    def rset(i):
        return set(reps[i]["where"]["routes"])

    def sset(i):
        return set(reps[i]["where"]["surface_set"])

    def disjoint_pairs(pred, cap=60):
        found = []
        for code, mem in by_code.items():
            for a in mem[:40]:
                for b in mem[:40]:
                    if a < b and pred(a, b):
                        found.append((code, a, b))
                        if len(found) >= cap:
                            return found
        return found

    pairs1 = disjoint_pairs(lambda a, b: not (rset(a) & rset(b)) and (rset(a) or rset(b)))
    pairs2 = disjoint_pairs(lambda a, b: not (sset(a) & sset(b)))

    def case3_pairs(S):
        off = S[np.triu_indices(n, 1)]
        thr = float(np.percentile(off, 99.9))
        out_ = []
        for a in idx_sup[:900]:
            for b in idx_sup[:900]:
                if a < b and target[a] != target[b] and S[a, b] > thr:
                    out_.append((a, b))
        return out_, thr

    def evaluate_world(idf, mode, wname, k_nn):
        V = views[idf]
        S = ID.combine(V, ID.WEIGHT_GRID[wname], mode=mode)
        lab = ID.louvain(ID.knn_graph(S, k=k_nn), seed=SEED)
        hb = {s: {"intervals": hyp_iv_by[s], "labels": [str(lab[i]) for i in by_sess[s]]}
              for s in sessions}
        m = EV.evaluate_all(ref, hb, cfg)["overall"]
        ident = m["identity_pooled"]
        c3, thr = case3_pairs(S)
        sess_of = collections.defaultdict(set)
        for i, l in enumerate(lab):
            sess_of[l].add(segs[i]["session_id"])
        return {
            "idf": idf, "mode": mode, "weights": wname, "k_nn": k_nn,
            "n_labels": len(set(lab)),
            "boundary_f1_2000": m["boundary_time"]["2000"]["f1"],
            "boundary_f1_all": {t: m["boundary_time"][t]["f1"] for t in m["boundary_time"]},
            "count_ratio": m["count_ratio"],
            "ari": ident["ari"], "nmi": ident["nmi"], "homogeneity": ident["homogeneity"],
            "completeness": ident["completeness"], "match_rate": ident["match_rate"],
            "interruption_recall": (m.get("interruption") or {}).get("recall"),
            "cross_session_reuse": round(sum(1 for v in sess_of.values() if len(v) > 1)
                                         / max(1, len(sess_of)), 4),
            "case1_same_process_disjoint_routes_grouped": round(
                sum(1 for _c, a, b in pairs1 if lab[a] == lab[b]) / max(1, len(pairs1)), 4),
            "case2_same_process_disjoint_surfaces_grouped": round(
                sum(1 for _c, a, b in pairs2 if lab[a] == lab[b]) / max(1, len(pairs2)), 4),
            "case3_n_pairs": len(c3), "case3_threshold": round(thr, 4),
            "case3_wrongly_grouped": round(
                sum(1 for a, b in c3 if lab[a] == lab[b]) / max(1, len(c3)), 4),
            "_labels": lab,
        }

    # ---------------------------------------------------------- TASK 1 + 2 ablation grid
    #
    # The S-E6 shipped configuration is (where_heavy, k_nn=20, linear). Every cell below holds
    # that fixed except the one factor under test, so each delta is attributable.
    base_w, base_k = "where_heavy", 20
    grid = []
    for idf in (False, True):
        for mode in ID.COMBINE_MODES:
            r = evaluate_world(idf, mode, base_w, base_k)
            grid.append(r)
            print(f"  idf={int(idf)} mode={mode:9} k={r['n_labels']:3} ARI={r['ari']:.4f} "
                  f"NMI={r['nmi']:.4f} hom={r['homogeneity']:.3f} cmp={r['completeness']:.3f} "
                  f"c1={r['case1_same_process_disjoint_routes_grouped']:.3f} "
                  f"c2={r['case2_same_process_disjoint_surfaces_grouped']:.3f} "
                  f"c3={r['case3_wrongly_grouped']:.3f} ({time.time()-t0:.0f}s)", flush=True)
    out["ablation_grid"] = [{k: v for k, v in r.items() if not k.startswith("_")}
                            for r in grid]

    # ---------------------------------------------------------- unsupervised re-selection
    sel = ID.select_config(reps, [s["session_id"] for s in segs], seed=SEED)
    sel_views = sel.pop("_views")
    out["unsupervised_selection"] = {
        "_rule": "stability under 80% node resampling x cross-session reuse — unchanged from "
                 "S-E6, now sweeping the combination mode as well. No GT enters it.",
        "chosen": {k: v for k, v in sel.items() if k != "grid"},
        "grid": sel.get("grid", [])[:12]}
    chosen = evaluate_world(True, sel["mode"], sel["weights"], sel["k_nn"])
    out["chosen_arm"] = {k: v for k, v in chosen.items() if not k.startswith("_")}
    print(f"[select] {sel['weights']}/{sel['mode']}/k_nn={sel['k_nn']} -> "
          f"k={chosen['n_labels']} ARI={chosen['ari']}", flush=True)

    # ---------------------------------------------------------- TASK 3 scaffolding
    flags = [scaffolding_flags(r) for r in reps]
    sc_idx = {i for i, f in enumerate(flags) if f["any"]}
    sc_matched = [i for i in idx_sup if i in sc_idx]
    win = chosen["_labels"]
    maj = {}
    for lab in set(win[i] for i in idx_sup):
        c = collections.Counter(target[i] for i in idx_sup if win[i] == lab)
        maj[lab] = c.most_common(1)[0][0]
    wrong = [i for i in idx_sup if target[i] != maj[win[i]]]
    wrong_sc = [i for i in wrong if i in sc_idx]
    c1_sc = sum(1 for _c, a, b in pairs1 if a in sc_idx or b in sc_idx)
    c2_sc = sum(1 for _c, a, b in pairs2 if a in sc_idx or b in sc_idx)
    out["scaffolding"] = {
        "_policy": "COUNTED AND REPORTED, NEVER REMOVED. Excluding inconvenient executions is "
                   "fitting the evaluation set.",
        "_detector": "structural: terminal-only app set; scaffold-like filename or theme/"
                     "reference token in the WHAT bag; terminal present with no web surface. "
                     "No A process name or code is used.",
        "n_executions_flagged": len(sc_idx),
        "share_of_all": round(len(sc_idx) / n, 4),
        "n_matched_flagged": len(sc_matched),
        "share_of_matched": round(len(sc_matched) / max(1, len(idx_sup)), 4),
        "by_signature": {k: sum(1 for f in flags if f[k])
                         for k in ("terminal_only", "scaffold_filename", "terminal_present",
                                   "no_web_surface")},
        "misgrouped_total": len(wrong),
        "misgrouped_flagged": len(wrong_sc),
        "share_of_residual_error": round(len(wrong_sc) / max(1, len(wrong)), 4),
        "enrichment_vs_base_rate": round(
            (len(wrong_sc) / max(1, len(wrong))) / max(1e-9, len(sc_matched) / max(1, len(idx_sup))), 3),
        "case1_pairs_touching_scaffolding": f"{c1_sc}/{len(pairs1)}",
        "case2_pairs_touching_scaffolding": f"{c2_sc}/{len(pairs2)}",
        "examples": [{"session_id": reps[i]["session_id"],
                      "apps": reps[i]["where"]["apps"],
                      "what": reps[i]["what"][:110]} for i in sorted(sc_idx)[:4]],
    }
    print(f"[scaffold] {len(sc_idx)}/{n} flagged, {len(sc_matched)} matched, "
          f"{len(wrong_sc)}/{len(wrong)} of residual error", flush=True)

    # ---------------------------------------------------------- contract
    bf = {f"idf={r['idf']} {r['mode']}": r["boundary_f1_all"] for r in grid}
    bf["chosen"] = chosen["boundary_f1_all"]
    frozen_bf = {t: D["frozen_boundary"][t]["f1"] for t in D["frozen_boundary"]}
    viol = [k for k, v in bf.items() if v != frozen_bf]
    out["contract_boundary_f1"] = {"frozen": frozen_bf,
                                   "identical_on_every_arm": not viol, "violations": viol}
    out["runtime_s"] = round(time.time() - t0, 1)
    json.dump(out, open(os.path.join(HERE, "metrics.json"), "w"), indent=2,
              ensure_ascii=False, default=str)
    with open(os.path.join(HERE, "samples.jsonl"), "w", encoding="utf-8") as fh:
        for r in out["ablation_grid"]:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    print(f"contract ok: {out['contract_boundary_f1']['identical_on_every_arm']}")
    print(f"wrote {HERE} ({out['runtime_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
