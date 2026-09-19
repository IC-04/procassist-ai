# Git History as an Engineering Narrative — Step 2.5

## Submission-Ready Narrative

**Status:** Submission-ready engineering history  
**Scope:** Step 2.5 — Git history / engineering narrative  
**Purpose:** Document what the commit history establishes, including refutations, corrections, scope decisions, and verification that Step 1 remained frozen.  
**Evidence basis:** Repository Git history and the artifacts described in this report.

> **Submission note:** This document is a historical engineering narrative. It records what the cited commits establish and does not replace the authoritative Step 1 specification or later phase specifications.

## Reviewer Navigation

1. [The graph](#the-graph)
2. [Phase-by-phase narrative](#phase-by-phase)
3. [Commits recording negative or refuting results](#commits-that-record-a-negative-or-refuting-result)
4. [Confirmation that Step 1 was not modified](#confirmation-that-step-1-was-not-modified)
5. [Tags](#tags)

## Submission Integrity

- The document distinguishes completed work, superseded hypotheses, corrections, and negative results.
- Refutations are retained rather than rewritten out of the history.
- The narrative does not claim that a negative result is a failed implementation; it records what the evidence ruled out.
- Step 1 is explicitly checked for non-modification during this history window.
- The final test-suite result and repository tags are reported as recorded in the source.

Fourteen commits, six phases, one blocked start. The history is a graded deliverable, so this
document says what each commit establishes and names the ones that record a refutation.

## The graph

```
* aeeeaff (HEAD -> phase-0-setup) [S2.5] Give the repository README a reading order
* 8e44b5a [S2.5] ADR-023 and ADR-024: dependency governance and the refutation
* 1f61966 [S2.5] Mark supersession in STEP2_AUTOMATION_OPPORTUNITY in place
* b087437 (tag: phase6-complete) [S2.5] Reframe Step 3 as prepare-and-present; recommend a lookup, not a model
* 8c6deca [S2.5] Deterministic lookup reaches 64.2% on retrieval; AI not yet justified
* 99fc43e (tag: phase5-complete) [S2.5] The strong hypothesis is refuted: no decision was ever observed
* cf5de47 (tag: phase4-cancelled) [S2.5] Cancel the blanket VLM pass; answer Q1 and Q2 from free text
* a83111b (tag: phase3.9-complete) [S2.5] Correction: G4 reopens — operator-typed comments carry variance
* d5b2f67 [S2.5] Sweep for negative outcomes: null result, but the UI can reject
* d8d8b9e (tag: phase3.5-complete) [S2.5] ADR-022: the screen header names a record's module, not the URL
* d5b23ba [S2.5] Record the module-key reconciliation artifact
* 4fe512b [S2.5] Reconcile three module keys; derive the prefix map from screen text
* 566c150 [S2.5] Track evidence artifacts; narrow the build/ ignore rule
* ac6726a [S2.5] Evidence extraction layer: Pass 0, Pass 1, hypothesis harness
```

## Phase by phase

### Unblocking — before any work

A zero-byte `.git/index.lock` dated 16 September had blocked every commit since the evidence
layer was written. Confirmed stale (no live git process), removed, `git fsck` clean apart from
dangling blobs and tags left by earlier `git tag -f` moves. The repository's existing subject
convention — `[TAG] imperative summary`, consistent across 25 commits — was kept; the
What/Why/Evidence/Impact/Limits body structure was adopted from this point and the first commit
body says so.

### Phase 0–3 — the evidence layer (`ac6726a`, `566c150`)

`ac6726a` commits `analysis/evidence/` — eleven modules, 25 tests — and the finding that made
everything downstream possible: `context.extracted_text` carries screen text on 939 of 20,477
events, so most of what a vision model was scoped to read was already in the telemetry for free.

`566c150` narrows the `build/` ignore rule to expose only `build/dataset_b/evidence/`. Its body
records a mistake caught before staging: a first attempt used `!build/dataset_b/` and exposed
Step 1's frozen `blocks.jsonl`, `segments_rich.jsonl` and `candidates.jsonl` as trackable.

### Phase 3.5 — module key reconciliation (`4fe512b`, `d5b23ba`, `d8d8b9e`)

Three commits: the script, the artifact, the document and ADR-022.

The leading hypothesis — that the 539 disagreeing records were cross-module queue views, so both
keys were right about different questions — was tested directly and **refuted**: 33 captures mix
record-id prefixes and **0** of them cross a module boundary. The screen header and the record
prefix agree on 2,904 of 2,904 records; the URL dissents alone in all 552 disagreements.

`4fe512b`'s body records a defect in its own first derivation: a gate on four hard-coded list
headings silently dropped `P10 / FI|発注管理` out of the prefix map entirely, because that module
renders a different heading. A heuristic that fails closed looks like missing data rather than a
bug.

### Phase 3.9 — the outcome sweep, and a correction (`d5b2f67`, `a83111b`)

**These two commits are the most important pair in the history, and the second one corrects the
first.**

`d5b2f67` reported a clean null result over 25,495,968 characters and closed gate G4. It was
wrong — not in its arithmetic, but in where it looked. It swept every place a *system* outcome
would appear and never looked at what the operator typed.

`a83111b` corrects it. `payload.target_field.value` on keystroke events carries 481 distinct
operator-written comments, of which 26 (5.4%) carry `差異あり` / `要注意` / `要確認`. **G4 reopens,
narrowly**: the system disposition is still constant, but the operator's recorded judgement
varies — and every flagged record was still disposed positively. The learnable target is
"predict the annotation", not "predict the decision".

Per the protocol, the first commit was not amended or rewritten. Both stand.

### Phase 4 — cancelled (`cf5de47`)

The blanket pass over 4,746 screenshots is cancelled and the reasoning is committed. Q1 (the ⚠
marker) and Q2 (authority fields) were both answered from free text; Q3 had nothing to confirm.
**0 images, 0 calls, $0.00.** The capability is built, bounded and fail-safe-verified so that
not spending is a measured decision rather than an absence, and the commit body states what the
cancellation costs.

### Phase 5 — the refutation record (`99fc43e`)

The narrative centrepiece. The strong hypothesis is false in its strong form, and the body says
why in one line: with 0 negative outcomes there is no supervision signal, so a model trained
here learns `return approve` and scores 100% while being worth nothing.

It also records that **H5–H18 do not exist** — four hypotheses were ever defined, and reporting
eighteen would have been inventing fourteen.

### Phase 6 — AI does not earn its place (`8c6deca`, `b087437`)

The one surviving positive result (H3) is formalised into a retrieval task and then attacked
with four baselines before any model is proposed. A deterministic `(module, record type) →
document` lookup reaches **64.2%**, and a learned retriever would have to exceed **71.5%** before
n=148 could tell it apart. The recommendation is the lookup table.

`8c6deca` also records that the label space had to be settled first: content hashing fragments
one document into 50 labels and depresses the baseline to 42.6%; the document's own heading gives
17 labels and 64.2%.

### Phase 7 — reconciling the record (`1f61966`, `8e44b5a`, `aeeeaff`)

Supersession marked **in place** in `STEP2_AUTOMATION_OPPORTUNITY.md` — two dated notices, no
original text deleted. ADR-023 (dependency governance, with the VLM recorded as a new dependency
*class*) and ADR-024 (the four-gate table as the decision record). A reading order in the
repository README so a cold reader meets the refutation rather than only the superseded document.

---

## Commits that record a negative or refuting result

This is the list worth reading first.

| Commit | What died |
|---|---|
| `4fe512b` | **The cross-module-view hypothesis.** 33 mixed-prefix captures, 0 crossing a module boundary |
| `d8d8b9e` | **The URL as a module key.** Wrong about the displayed screen in 21% of captures; and the inventory is missing a module entirely |
| `d5b2f67` | The first null result on negative outcomes — **itself later corrected** |
| `a83111b` | **My own previous commit.** G4 reopens; the sweep had never looked at what the operator typed |
| `cf5de47` | **The blanket VLM pass.** Cancelled; both its questions answered from free text |
| `99fc43e` | **The strong hypothesis.** 0/225 negative dispositions; no supervision signal exists |
| `8c6deca` | **The case for a learned retriever.** A lookup table reaches 64.2% and AI cannot be distinguished from it at n=148 |
| `b087437` | States the strongest reason the surviving reframe may *also* be wrong: H3 measures sequence, not causation |

Eight of fourteen commits record something that did not work, including one that corrects
another. Two of them (`4fe512b`, `d5b2f67`) record a defect in the very code being committed.

---

## Confirmation that Step 1 was not modified

```
$ git log --oneline 1cce841..HEAD -- procmine/ build/dataset_b/blocks.jsonl \
    build/dataset_b/segments_rich.jsonl build/dataset_b/candidates.jsonl \
    build/dataset_b/segments_provisional.jsonl segments.jsonl dataset_a/ dataset_b/
(no output)
```

**No commit in this session touches any Step 1 path**, the deliverable `segments.jsonl`, or
either dataset. The only write inside `build/dataset_b/` is the new `evidence/` subdirectory;
the ignore rule was written to re-ignore each level after re-including it, and every frozen path
was verified individually to still be ignored.

Test suite at the end of the session: **355 passed, 1 skipped.**

## Tags

`phase3.5-complete` · `phase3.9-complete` · `phase4-cancelled` · `phase5-complete` ·
`phase6-complete` — annotated, not pushed. `step1-frozen` predates this session.