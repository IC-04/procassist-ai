# Dataset A — Ingestion and Readiness

## Source

Dataset A was downloaded manually by the project owner from the Google Drive folder
supplied with the assignment:

```
https://drive.google.com/drive/folders/1gCW_uGRl-BeYNBxmX4DkMivdsV9HO0yY
```

The link is a read-only public share. It carries **no credential, token or authenticated
download URL**, and none is stored anywhere in this repository.

Because the folder exceeds Google Drive's ~2 GB single-download limit, Drive delivered it as
a **multi-part export**: five *independent, self-contained* ZIP archives, not split parts of
one archive.

```
dataset_a-20260913T121812Z-1-001.zip   2,149,624,091 bytes
dataset_a-20260913T121812Z-1-002.zip   2,149,568,471
dataset_a-20260913T121812Z-1-003.zip   2,149,681,422
dataset_a-20260913T121812Z-1-004.zip   2,149,625,868
dataset_a-20260913T121812Z-1-005.zip   1,656,185,616
                                       ─────────────
                                       9.5 GB compressed
```

> **Do not concatenate these files.** Each begins with its own local file header
> (`PK\x03\x04`) and ends with its own end-of-central-directory record (`PK\x05\x06`) — every
> archive is a complete ZIP holding a disjoint subset of the tree. `cat *.zip > combined.zip`
> would produce a corrupt file. They are extracted **independently into the same target**.

Verified disjoint: 34,923 entries across the five archives, **0 duplicated paths**.

### Reconstruction actually performed

```bash
# 1. verify each archive's CRC32 before extracting anything   -> 5/5 "No errors detected"
for f in dataset_a-*.zip; do unzip -t "$f"; done

# 2. extract each into the repository root; every archive carries a dataset_a/ prefix,
#    so this lands directly at dataset_a/.  -n never overwrites an existing file.
for f in dataset_a-*.zip; do unzip -n -q "$f" -d .; done
```

The source archives were **not modified and not deleted**. Dataset A contents were not
renamed, restructured, preprocessed, cleaned or transformed in any way.

## Local location

```
<repo root>/dataset_a/ses_<date>-<time>-<machine>/
    chunk_<...>/events.jsonl
    chunk_<...>/manifest.json
    chunk_<...>/screenshots/*.jpg
    gt.jsonl
    gt_manifest.json
```

`dataset_a/` is gitignored and stays local input data. The delivered archives are now
gitignored too (see *Git safety*).

**Verify presence:**
```bash
ls -d dataset_a/ses_* | wc -l      # 63
find dataset_a -type f | wc -l     # 34923
du -sh dataset_a                   # 10 GB
```

**Run the readiness check:**
```bash
make build-a                                        # full Phase 0 build
python3 -m procmine.cli --dataset dataset_a --no-windows   # lighter ingestion probe
```

## Integrity

| Measure | Dataset A |
|---|---|
| Archives passing CRC32 verification | **5 / 5** |
| Files extracted | **34,923 / 34,923** expected |
| Unreadable files | **0** |
| Size on disk | **10.22 GB** |
| File types | 34,563 `.jpg` · 180 `.jsonl` · 180 `.json` |
| Sessions | **63** |
| Chunks | 133 (1–4 per session) |
| `events.jsonl` / `manifest.json` | 117 each |
| `gt.jsonl` / `gt_manifest.json` | **63 / 63** — every session |
| Events parsed | **162,768** |
| Malformed JSON lines | **0** |
| `schema_version` | `1.0.0` on 100% of events |
| Distinct `session_id` in events | 63 — matches directory count |
| Ground-truth records | **10,609**, malformed **0** |
| Screenshot references | 34,580, **0 truly absent** |

`README.md` states Dataset A is "63 sessions / ~162,000 events". Measured: **63 sessions,
162,768 events**. Nothing is truncated.

Ground-truth record types: `clipboard_paste` 3,010 · `task_started` 2,009 ·
`process_started` 1,819 · `clipboard_copy` 1,766 · `process_switched_out` 1,590 ·
`process_resumed` 190 · `process_suspended` 99 · `run_config` 63 · `session_ended` 63.

## Schema compatibility

Audited against `DATA_SCHEMA.md` as the sole authority. No schema was inferred from B.

**Top-level (§2): all 13 documented fields present on 100% of 162,768 events** —
`schema_version`, `event_id`, `session_id`, `timestamp_ms`, `timestamp_iso`, `layer`,
`event_type`, `source`, `context`, `correlation`, `payload`, `metadata`, `extensions`.

**`correlation.*` (§2): all five documented fields at 100%** — `sequence_number`, `chunk_id`,
`triggered_by`, `ms_since_last_event`, plus `correlated_events`.

**`context.*` (§2)** — the schema notes "how often each field is populated varies":

| Field | A present | A populated | B populated |
|---|---|---|---|
| `active_app` | 100% | 99.7% | 99.4% |
| `active_monitor` | 100% | 99.7% | 99.4% |
| `active_browser_tab` | 100% | 52.6% | 46.5% |
| `open_apps` | 100% | 94.0% | 85.9% |
| `visible_windows` | 100% | 21.2% | 23.2% |
| `extracted_text` | 4.5% | 4.5% | 4.6% |

`extracted_text` at 4.5% matches the documented "roughly 4% of events".

**Layers (§2):** `L2` 118,399 · `L1` 34,580 · `L3` 9,335 · `SYSTEM` 454. All four represented.

**`extensions.*` — recorded separately as UNDOCUMENTED and optional** (`DATA_CONTRACT.md` §0).
Present in A: `capture_quality_v1` 63.3%, `uia_v2` 57.9%, `field_identity_v1` 12.0%,
`dataflow_v2` 7.4%, `cross_layer_v1` 5.5%, `dom_v2` 5.5%, `ocr_v1` ~0%, `uia_v2_start` ~0%.
`uia_v2_start` does not occur in B. **None of these is treated as a contractual field.**

**Screenshots (§2):** every one of the 34,580 `payload.file_reference.filename` references
resolves to a file that exists in its session — see *Dataset-specific observations* for where.

## Differences from Dataset B

Factual measurements only. None of these is interpreted as a problem here.

| | Dataset A | Dataset B | ratio |
|---|---|---|---|
| Sessions | 63 | 15 | 4.2× |
| Events | 162,768 | 20,477 | 7.9× |
| Files / size | 34,923 / 10.22 GB | 4,786 / 1.61 GB | 6.3× |
| Chunks (max per session) | 133 (4) | 20 (2) | |
| Ground truth | present, all 63 sessions | none | — |
| `app_switch` share of events | **31.1%** (50,588) | 8.1% (1,654) | |
| `mouse_scroll` share | 2.0% | 8.4% | |
| `dataflow_v2` coverage | 7.4% | 8.6% | |

**Six documented event types occur in A but not in B:** `browser_alert` (137),
`browser_tab_event` (103), `dialog_opened` (28), `dialog_closed` (28), `upload_failed` (5),
`mouse_drag_drop` (4). All are listed in `DATA_SCHEMA.md` §2, so A exercises *more* of the
documented schema than B does. The perception layer keys on `layer` rather than on an
enumerated list of event types, so it consumes them without modification.

The `app_switch` share is the largest behavioural difference: nearly a third of A's events are
application switches, against a twelfth in B. **Recorded, not acted on.** Whether it changes
block or boundary behaviour is a Phase 2 question, not an ingestion question.

## Pipeline smoke test

Goal: establish only that the **existing generic pipeline discovers and reads** Dataset A.
The lighter probe was used rather than the full build, since reasoner payloads are not needed
to verify ingestion.

```bash
python3 -m procmine.cli --dataset dataset_a --no-windows
```

**Result: success, exit 0, 6.1 s.**

| | measured |
|---|---|
| Sessions discovered | **63** |
| Events read | **162,768** |
| Blocks | 4,968 |
| Empty-surface blocks | 0 |
| One-event blocks | 211 (4.2%) |
| Events per block | 32.8 |
| TEKG documents written | 63 / 63 |
| `blocks.jsonl` contract violations | **0** |
| TEKG contract violations | **0** |

Artifacts inspected, not just the exit code: `build/dataset_a/blocks.jsonl` (4,968 rows, 63
sessions, validates clean), `build/dataset_a/tekg/*.json` (63 files, sample validates clean),
`summary.json`. No corruption observed.

Ingestion was additionally checked against a synthetic **A-shaped** fixture before the real
data arrived — a session carrying `gt.jsonl` and `gt_manifest.json` alongside its chunks — to
confirm the Phase 0 perception layer discovers the session and correctly ignores the
ground-truth files. It does.

**No Dataset-A-specific code exists.** No `if dataset == "dataset_a"` branch, no A application
name, URL, window title or vocabulary anywhere in `procmine/`. The identical code path that
processes B processed A.

## Problems / blockers

**None blocking Phase 1 from the data side.**

One pre-existing environment issue carries over from Phase 0: this machine has no Python
≥3.10, so `make setup` still fails by design and Phase 0 acceptance criterion 1 remains
BLOCKED. Everything above was run on the ambient Python 3.9.6. This is unrelated to Dataset A.

## Dataset-specific observations

Recorded as observations about **this data**. None is a generic pipeline rule, and nothing was
changed in response to any of them.

### O1 — Screenshots are stored in a parallel chunk directory in 11 of 63 sessions

`DATA_SCHEMA.md` §2 says an image "sits at `<chunk>/screenshots/<filename>`". In 11 sessions
that join does not hold: the telemetry lives in the schema-named chunk while the images live
in a **sibling, short-named chunk** whose name is the time component alone.

```
ses_20260630-121953-LAPTOP-R36BQBTE/
    chunk_20260630-1200-LAPTOP-R36BQBTE/   events.jsonl, manifest.json   (no screenshots/)
    chunk_1200/                            screenshots/*.jpg             (no events.jsonl)
```

Measured over all 34,580 screenshot references:

| Resolution strategy | resolves |
|---|---|
| `<chunk-of-the-event>/screenshots/<filename>` — the literal §2 join | 31,012 (**89.68%**) |
| anywhere within the same session | 34,580 (**100.00%**) |
| truly absent from the dataset | **0** |

So this is a *directory-layout* variance, **not missing data**. It accounts for the 16 chunk
directories that hold no `events.jsonl` and no `manifest.json` (they are image-only), and for
`chunks_total` 133 against 117 `events.jsonl`.

**Impact today: none.** The perception layer globs `chunk_*/events.jsonl`, so image-only
chunks contribute nothing and are silently skipped; `blocks.screenshots` stores the bare
filename and never resolves a path. **Impact later:** the first phase that actually opens an
image — ADR-009 selective vision (Phase 3) or the prototype (Phase 6) — must resolve by
filename **within the session** rather than assuming the event's own chunk directory. That
would be a *generic* change benefiting A and B equally, to be made in the phase that needs it.
**Not implemented now.**

### O2 — Two sessions have no `session_end` event

`session_start` occurs 63 times, `session_end` 61. Two recordings end without the terminating
SYSTEM event. `SYSTEM` events are surface-transparent (ADR-012) and Phase 0 derives no
boundary from them, so nothing downstream depends on this. Phase 1 should confirm the GT for
those two sessions is still usable; `gt.jsonl` carries its own `session_ended` record, present
63 times.

### O3 — `app_switch` dominates A's event mix

50,588 of 162,768 events (31.1%), against 8.1% in B. Noted because ADR-014 deliberately does
**not** suppress `app_switch` self-transitions, a decision taken on B evidence where the event
is four times rarer. Phase 2 should re-measure that decision on A. **No change made now.**

### O4 — Block statistics differ markedly from B

A compresses to 32.8 events/block against B's 15.3, with 4.2% one-event blocks against B's
11.4%. On its face the perception layer behaves *better* on A than on B. **This is not
validation** — it is a first observation from an ingestion probe. Risk R1 in
`ARCHITECTURE.md` §7 is assessed in Phase 2 with the proper A-versus-B block-quality
comparison, not here.

## Git safety

`dataset_a/` was confirmed gitignored **before** anything was downloaded or extracted.

One real issue was found and fixed: the five delivered archives sat in the repository root as
**9.5 GB of untracked-but-committable files** — `.gitignore` covered `dataset_a/` but not
`dataset_a-*.zip`. A single `git add -A` would have staged them. `.gitignore` now also covers:

```
dataset_?-*.zip
dataset_?-*.zip.*
*.zip.[0-9][0-9][0-9]
```

Verified after the change: all five archives ignored, `git status` clean apart from tracked
documentation, tracked-file count unchanged at 54, no screenshot, telemetry, build artifact or
credential staged, and no Drive URL in any source file. The folder URL appears only in this
document, by decision, and is a credential-free public share link.

## Phase 1 readiness

**READY.**

Evidence: 63/63 sessions present and 162,768 events parsed with **zero** malformed lines;
5/5 archives CRC-verified before extraction and 34,923/34,923 files extracted; all 13
documented top-level schema fields and all five `correlation.*` fields present on 100% of
events; ground truth present for **every** session (63 `gt.jsonl` + 63 `gt_manifest.json`,
10,609 records, 0 malformed); and the unmodified generic pipeline discovered and processed the
dataset end to end in 6.1 s with 0 artifact-contract violations.

The four observations above are recorded findings, not blockers. O1 affects only a phase that
opens images, which Phase 1 does not.

The Python ≥3.10 environment gap from Phase 0 is unrelated to Dataset A but still open.

**Stopped here. Phase 1 not started.**
