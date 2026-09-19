# STEP3_DOMAIN_RESEARCH — how this class of work is actually automated

**Purpose.** Stage 1 selected the `payroll-items` family as the Step 3 target. This document
researches how that *class* of business process is automated in practice, and derives the design
requirements Stage 3 must satisfy. It does **not** design the system.

**Test applied to every section.** Does it change or validate a Stage 3 architectural decision?
Sections that do not are short or absent. Section numbering follows that test, not a template.

**Evidence tags.** `[LIT]` peer-reviewed or scholarly · `[JP]` Japanese source · `[VENDOR]` vendor
primary documentation · `[OSS]` open-source project · `[DATASET]` measured in our own data ·
`[INF]` our inference. Never blurred. Vendor marketing is not treated as empirical evidence.

---

## 1. Executive summary

Seven findings, each of which forces a Stage 3 decision.

1. **The pattern is duplicate master-data entry across siloed core systems**, not document
   transcription. `[DATASET]` `/payroll-items` exists in all three observed systems;
   `[JP]` Japanese integration practice names the problem 二重入力 and its documented consequence
   転記ミス — transcription error.
2. **Whether a bulk-import or API path exists in the target systems is unverified, and it is the
   single highest-value open question.** `[JP]` CSV import is the *common* route between Japanese
   payroll and accounting systems. `[INF]` If one exists in the client's systems and staff are
   still hand-keying, the correct recommendation is partly process change, not a robot.
3. **Therefore the execution backend must be swappable.** UI automation is the defensible default
   *under uncertainty*, but the same definitions and validation must be able to drive an import
   or API path if one is confirmed. This is an architectural requirement, not a caveat.
4. **Verification survives automation.** `[JP]` Even with API integration, "仕訳結果や計上単位の確認は
   必要です" — confirmation of the result remains necessary. Human review is not optional garnish.
5. **Human review should be triggered by rule violations, not by a confidence score.**
   `[VENDOR]` AWS's IDP reference architecture routes to human review when *business rules fail*;
   confidence is one condition category among several, and only meaningful where extraction is
   probabilistic. Our mapping is deterministic `[DATASET]`, so a confidence number would be
   invented precision.
6. **Multi-system writes need idempotency keys and per-target state, but probably not automatic
   rollback.** `[LIT]` Sagas assume a compensating transaction exists for each step; in UI
   automation against systems we do not control, it usually does not. Pre-flight validation plus
   per-target independent commit plus a reconciliation record is the honest design.
7. **AI does not belong on the execution path.** `[LIT]` On WorkArena — enterprise form-filling and
   data entry on a real platform — GPT-4 reaches **42.7%** task success and the open-source SOTA
   **17.9%**. A deterministic selector-driven path either works or fails visibly; an agent fails
   silently more than half the time.

---

## 2. Naming the pattern

The observed work does not have one name; it has a different name in each discipline, and the
differences matter because each brings its own solution catalogue.

| Discipline | Term | Fit |
|---|---|---|
| Japanese enterprise IT | **二重入力** (duplicate entry) across **基幹システム** (core systems) | **closest** — names both the problem and the setting `[JP]` |
| Integration / middleware | master-data propagation; system-to-system 連携 | close; assumes a machine interface exists |
| RPA | multi-system data entry; attended/unattended data entry automation | close; assumes UI is the interface |
| Task mining `[LIT]` | a *deterministic routine* whose parameters are constant or derived (Bosco et al.) | the formal condition our Step 2 determinism proxy tested |
| Document automation | structured document ingestion | **poor fit** — the source is a structured 一覧, not an unstructured scan |

`[INF]` The correct framing is **duplicate master-data entry across siloed core systems, where the
source of record is a structured document and the human is the integration layer.** Framing it as
"document → web-form transcription" would import the wrong solution catalogue — it would suggest
IDP and OCR, which solve a problem we do not have, and would hide the multi-system dimension that
is the actual source of the waste.

---

## 3. Japanese enterprise context

`[JP]` Japanese guidance on connecting 給与計算 (payroll) and 会計 (accounting) systems states the
problem plainly: where the systems are disconnected, data is re-entered by hand, producing
**転記ミスや科目の選択漏れ** — transcription errors and missed account classifications. Three
integration routes are described, with caveats attached to each:

| Route | Description | Stated caveat `[JP]` |
|---|---|---|
| **CSV export/import** | export from one system, reformat, upload to the other | still requires 列の整形やアップロードの手順 — column formatting and upload steps. Manual work is reduced, not removed |
| **API integration** | direct transfer of journal entries | requires advance verification that the software is compatible and correctly configured |
| **Same-vendor series** | payroll, attendance, expenses and accounting from one vendor | data flows across the suite; not available when systems are from different vendors |

Two caveats apply to **all three** and are directly design-relevant `[JP]`:

- **"仕訳結果や計上単位の確認は必要です"** — confirmation of the posting result remains necessary.
  Integration does not remove the verification step.
- Exception scenarios — corrections and retroactive adjustments — can *increase* workload if not
  designed for in advance.

`[JP]` Governance: the 野良ロボット ("stray robot") problem — RPA whose owner becomes unknown and
that continues to operate unsupervised, in reported instances producing wrong calculations that
went unnoticed (Mitsubishi Research Institute). `[JP]` MIC's local-government guidance insists that
success requires **業務の整理・見直し** — reviewing and tidying the process — not deploying a robot
over an unexamined one.

`[DATASET]` Our three observed systems are exactly the silo pattern these sources describe:
**HR人事給与システム** (5132), **財務会計システム** (5133), **受発注在庫管理システム** (5134), with
`/payroll-items` present in all three.

---

## 4. The critical question: is there an import or API path?

This is the question most likely to overturn the modality choice, so the evidence is separated
strictly into three buckets.

**OBSERVED IN DATASET** `[DATASET]`
Three distinct origins serving the same module routes. Staff perform the registration through the
browser UI, alternating with a Word 一覧. Recovered widget ids follow `btn-{module}-ok` /
`{module}-note`. Values are hashed (`raw_value_persisted: false`), so no payload is recoverable.
**Nothing in the telemetry indicates the presence or absence of an import or API path.** Observing
that staff use the UI is not evidence that no other interface exists.

**COMMON INDUSTRY CAPABILITY** `[JP]` `[VENDOR]`
CSV import between payroll and accounting packages is a normal, documented capability in the
Japanese market, and API integration is offered where vendors are compatible. It is therefore
*likely* that at least one of the three systems offers a file-based route.

**UNVERIFIED FOR TARGET SYSTEM**
Whether *these* systems expose an import or API; whether it covers the payroll-item fields we
observed; whether staff have permission to use it; whether it is rejected for a reason we cannot
see (approval flow, audit requirement, data-quality gate).

### Under what conditions would integration beat UI automation?

`[INF]`, grounded in `[JP]` and `[LIT]`:

- the interface covers **all** required fields, not a subset — a partial import leaves the human
  doing the remainder and can be worse than either extreme;
- the interface is **available to the operators**, not only to IT;
- volumes justify batch semantics rather than per-record entry;
- the interface is **versioned and supported**, which `[LIT]` (Syed et al.; the maintainability
  study) says is the main determinant of long-run maintenance cost.

`[INF]` **The uncomfortable case, stated deliberately:** if a bulk import already exists and staff
are nevertheless hand-keying, the finding is a *process* finding, not a technology one. The
recommendation would then be partly training and process change — MIC's 業務の整理・見直し `[JP]` —
and a robot would automate around an organisational problem rather than fix it. Stage 3 must not
foreclose this outcome.

### What evidence would we need before deploying

1. Vendor documentation or an admin screen showing an import/API for the payroll-item entity in
   each of the three systems.
2. Field-level coverage comparison against the ~39 field keys we recovered `[DATASET]`.
3. Operator permissions for that interface.
4. Whether an import path is subject to the same approval and audit obligations as UI entry.
5. If an import exists but is unused — why.

---

## 5. Modality comparison

No weighted score. The trade-offs are stated and the conditions under which each wins are named.

| Modality | Wins when | Determinism | Maintenance | Auditability | Production prerequisites | Fit to our evidence |
|---|---|---|---|---|---|---|
| **API / direct integration** | a documented, field-complete, permissioned API exists | high | low — versioned contract | high, if the API logs | **API access, credentials, vendor support** | **unknown — the open question** |
| **Bulk / CSV import** | a file interface exists and volumes are batchy | high | low–moderate; format drift | moderate; file-level, not field-level | import permission; format spec | **unknown; likely to exist `[JP]`** |
| **UI / RPA (selector-driven)** | no machine interface is available or permitted | high *if* selectors are stable | **highest** — external UI changes are the documented main driver `[LIT]` | high, if the automation records its own actions | a reachable UI; stable selectors | **workable now; selectors recovered `[DATASET]`** |
| **Workflow orchestration** | multiple systems, handoffs, state across steps | n/a — a layer, not a mechanism | moderate | high — state is explicit | an execution substrate | **needed as a layer regardless of mechanism** `[INF]` |
| **Document processing / IDP** | the source is unstructured or scanned | probabilistic | moderate | moderate | a document corpus | **poor fit — source is a structured 一覧** |
| **AI-assisted / agentic** | the task requires judgement or the UI is unpredictable | **low — 42.7% on enterprise form-filling** `[LIT]` | unclear | poor — non-reproducible decisions | model access; evaluation harness | **rejected for the execution path (§11)** |
| **Process redesign** | the work exists only because systems are siloed | n/a | n/a | n/a | organisational authority | **partly indicated — and honest to say so** `[JP]` |

`[INF]` **The conclusion the evidence supports is conditional, and the conditionality is itself the
design requirement.** UI automation is the right default *under present uncertainty*, because it is
the only modality whose prerequisites we have verified. But since the prerequisites of the better
modality are merely *unverified* rather than *absent*, a design that hard-wires UI execution would
be betting on the client's systems being worse than they probably are. **The target adapter must be
an interface, with UI automation as its first implementation.**

---

## 6. Process-definition architecture

The question is whether a reusable definition layer is a real engineering pattern or an
affectation. It is a real pattern, and the mature products converge on it.

`[VENDOR]` **UiPath Object Repository** separates UI element definitions from process logic so that
"UI elements across the project are managed, updated, and modified from a centralized place."
Its taxonomy is **Applications → Versions → Screens → UI Elements**. A *UI Descriptor* holds the
element selector, **anchor selectors** (neighbouring elements used to identify the target more
robustly), screen context and captured images, plus metadata. The claimed benefit is that when the
application changes you update descriptors once rather than editing every workflow, and that anchors
let objects "keep their reliability in case the application received a slightly new UI."

`[LIT]` The maintainability study (*How to Keep RPA Maintainable?*) finds that **external system
changes** — vendors updating the applications bots depend on — are a principal source of maintenance
burden, alongside lack of development standards and poor modularity, and that updates must otherwise
be "applied individually across multiple bots." Among its eleven guidelines are **build reusable
modules**, **create development standards** and **perform technical reviews before bots go live**.
It offers no quantitative maintenance figures, and we do not invent any.

`[INF]` For us, the concrete implication is that a definition should declare at minimum:
the **source schema**; the **target system identity** (origin) separately from the **module/route**;
the **field mapping** source→target; **element descriptors with anchors**, versioned per system;
**validation rules**; **preconditions and postconditions**; the **approval policy**; and the
**exception policy**. `[DATASET]` Three systems sharing one widget convention but differing in
origin is precisely the Applications→Versions→Screens shape, which is why the pattern transfers.

---

## 7. Human-in-the-loop

The user's question was whether confidence scores belong here. The evidence says: mostly not.

`[VENDOR]` AWS's reference architecture for document processing with human review triggers review
**when business rules fail** — "send the document to Amazon A2I for a human to review if any
business rules fail" — rather than on a confidence threshold alone. Rules are expressed as
structured objects with a *condition category* (Confidence, Required, LengthCheck), a *condition
type* (ConfidenceThreshold, Required, ValueRegex) and a *setting*. Confidence is therefore **one
category among several**, and it exists because extraction from a document is probabilistic.

`[DATASET]` Our mapping is not probabilistic. Route Jaccard 0.74, route concentration 1.00 and ~39
stable field keys mean a source column maps to a target field deterministically. `[INF]` Attaching a
confidence number to a deterministic mapping would manufacture precision of exactly the kind the
Step 2 analysis refused. **The appropriate model is a validation verdict — VALID / INVALID /
REQUIRES_REVIEW — produced by declared rules.** Confidence becomes meaningful only if a later
version parses a source whose structure is uncertain.

`[VENDOR]` The same architecture records, for audit: reviewer identity, timestamps, time spent,
worker metadata, the reviewer's input, and a **required "CHANGE REASON"** free-text field. `[INF]`
The change reason is the part most often omitted and the part an auditor most wants.

`[JP]` And the Japanese integration guidance is explicit that confirmation of the posting result
remains necessary even with API integration — so review is a permanent feature of the process, not
a transitional safeguard while the robot is trusted.

**Where review sits.** `[INF]` Given statutory exposure on payroll, the defensible placement is
**pre-execution approval at record level**, with **exception-only review** for rule failures, and
**post-execution verification** of what actually landed in each target. Field-level review of every
field would be slower than the manual process it replaces.

---

## 8. Multi-system consistency

This is the section most likely to differentiate the artifact, and the literature gives a clear —
and partly cautionary — answer.

`[LIT]` The **saga pattern** handles a sequence of writes across systems that cannot share a
transaction: each step registers a **compensating transaction**, and on failure compensations run in
reverse (LIFO) order. Because steps are retried, **every operation must be idempotent** — achieved
in practice with "a distinct identifier ... to uniquely identify a particular transaction and
ensure it occurs effectively once", now standard in payment APIs. Retry semantics are
**at-least-once**, which is precisely why idempotency is mandatory rather than optional. The source
also notes that not every step necessarily has a compensation, and that without state tracking it is
hard to determine the recovery point.

`[INF]` **The honest adaptation for our setting.** Sagas assume a compensating transaction exists.
Against three enterprise UIs we do not control, it frequently will not: a payroll item, once
registered and approved, may have no user-accessible reversal, and inventing one by driving a
"delete" button would be a worse failure than the original. Therefore:

- **prefer prevention to compensation** — validate everything, against every target's rules, *before*
  the first write;
- **treat each target as an independent commit** with its own state, rather than pretending three UI
  writes are one transaction;
- **carry an idempotency key** per source record per target, so a retry cannot double-register;
- **when partial failure occurs, do not auto-rollback — reconcile.** Record which targets succeeded,
  which failed and why, and surface the inconsistency to a human as an explicit reconciliation item.

`[INF]` "What if system A succeeds and system B fails?" has a defensible answer here, and it is not
"undo A." It is: *A stands, B is marked failed with its reason, the record is flagged inconsistent,
and a human decides.* That is also what the Japanese guidance implies when it warns that corrections
and retroactive adjustments increase workload if unplanned `[JP]`.

---

## 9. Audit and governance

`[VENDOR]` Protiviti's guidance on RPA in SOX-relevant systems recommends: involving internal audit
from the start; IT general controls over **security, processing integrity and change management**;
flagging bots that affect financial reporting as SOX-relevant and documenting **"a bot's
requirements, system access, designs and actions" at a keystroke level, including how they handle
exceptions**; avoiding **segregation-of-duties conflicts** between the user who can initiate a bot
and the actions the bot performs; and business owners **monitoring transactional logs** rather than
letting automation run unwatched. It warns specifically against bots deployed "with default
credentials enabled and without proper governance."

`[JP]` The 野良ロボット problem is the same risk expressed as an ownership failure, with the
documented consequence that wrong results went unnoticed for an extended period.

`[INF]` An audit record for one execution should therefore carry: execution identity; **process
definition identity and version**; source record identity; the mapped field values; the validation
verdict and which rules fired; approver identity and timestamp; the change reason where a value was
corrected; per-target outcome with the failure reason; the target system identity; the
**automation version**; and the idempotency key. `[INF]` Definition *version* is the field most often
missing and the one that makes "why did it do that six months ago" answerable.

---

## 10. Failure-mode taxonomy

`[INF]`, informed by `[LIT]` and `[VENDOR]`. The column that matters is the last one: it determines
where in the pipeline each check must live.

| Class | Failure | Detect when | Response |
|---|---|---|---|
| **Input** | malformed source, missing required field, invalid value | **before execution** | reject record, no write attempted |
| **Mapping** | unmapped source field; ambiguous mapping | **at definition load** | fail fast — a definition error is a deploy-time bug, not a runtime one |
| **Validation** | business rule fails; target-specific rule fails | **before execution** | REQUIRES_REVIEW → human |
| **Target** | selector drift; page unavailable; timeout; unexpected UI state | at execution | stop that target, record the reason, do not guess |
| **Multi-system** | partial success; duplicate execution; inconsistent target states | at execution and after | reconcile, never auto-rollback (§8) |
| **Human** | rejection; correction; approval timeout | at approval | record with change reason; corrections re-enter validation |

`[INF]` Two rules follow. **Everything that can be checked before the first write must be** —
because the multi-system case makes post-hoc correction expensive and sometimes impossible. And
**selector drift must fail loudly**: `[LIT]` external application change is the documented principal
maintenance driver, so the system's response to an unrecognised screen must be to stop and report,
never to proceed on a best guess.

---

## 11. Where AI belongs

Asked as the user framed it — is there any part where AI provides *measurable* value over
deterministic automation?

`[LIT]` **On the execution path: no, with a number.** WorkArena (ServiceNow Research) benchmarks LLM
agents on 33 enterprise knowledge-work tasks on a real platform, including **form filling** and
service-catalogue ordering. GPT-4 with optimised configuration reaches **42.7%** task success;
the open-source state of the art reaches **17.9%**. The authors report "a considerable gap towards
achieving full task automation", with failure modes including enterprise HTML exceeding 100,000
tokens and agents "struggling to manipulate the UI."

`[INF]` Against a deterministic selector path driving a form whose element ids we have recovered,
an agent would be strictly worse on every axis that matters here — success rate, reproducibility,
explainability and auditability — and its failures would be silent rather than visible. For a
process with statutory exposure, that is disqualifying.

**Candidate roles assessed individually** `[INF]`:

| Candidate role | Verdict |
|---|---|
| Source→target **semantic field mapping** | Not needed for the observed columns — the mapping is stable and declarable once. *Possible* value as a **design-time assistant** proposing a draft mapping for a new module, with a human confirming it into a definition file. Off the execution path. |
| Schema inference from a new document | Same: design-time, human-confirmed, never runtime. |
| Anomaly detection over values | Deterministic rules (range, format, referential) cover the observed cases; no labelled anomalies exist to validate a model against. |
| Exception **classification** | Plausible, but the taxonomy in §10 is small and closed. A lookup beats a model. |
| Natural-language process configuration | Attractive demo, no measured benefit, and it puts free text between an operator and a statutory write. |
| Adaptive UI recovery on selector drift | **Explicitly rejected.** §10 requires drift to fail loudly; an AI that "figures out" a changed screen converts a visible failure into a silent wrong write. |
| Human-review **prioritisation** | Only meaningful at volumes we cannot observe. |

`[INF]` **Conclusion: no AI on the critical execution path.** The one defensible role is a
design-time mapping assistant whose output a human commits to a definition file — which is
governance-compatible because the artefact, not the model, is what executes. Stage 3 should decide
whether even that earns its place. This is the fourth time in this project that an LLM has been
sized against an alternative and declined on evidence; the consistency is the point.

---

## 12. Open-source landscape

Only what a Stage 3 decision would actually turn on.

| Component | Option | Licence | Verdict |
|---|---|---|---|
| Browser automation | **Playwright** `[OSS]` | Apache-2.0 | Auto-waiting removes the sleep-based flakiness that makes UI automation brittle; first-class selector engine supports the anchor-style robustness `[VENDOR]` describes. **Chromium already present in our environment.** Preferred. |
| | Selenium `[OSS]` | Apache-2.0 | W3C-standard, mature, larger ecosystem; weaker waiting semantics. Viable fallback, no advantage here. |
| Source parsing | `python-docx`, `openpyxl` `[OSS]` | MIT | Adequate and boring. The source is a structured 一覧; no IDP needed. |
| Definition validation | `pydantic` `[OSS]` | MIT | Already approved in this repo; gives definition-load-time failure (§10, Mapping class) for free. |
| Workflow engine | Temporal / Prefect / Airflow `[OSS]` | various | **Reject for this scope.** They solve durable execution at scale; our state is a handful of records across three targets. `[LIT]` The maintainability literature's warning is about *unnecessary* complexity as much as too little. |
| Audit storage | SQLite / JSONL `[OSS]` | PD / n/a | Sufficient; an append-only record is what §9 requires, not a database. |

`[INF]` Nothing in the OSS landscape replaces the definition layer — that is ours to build, and it
is the part that carries the engineering argument.

---

## 13. Replica versus production — principles for honest presentation

`[DATASET]` We hold: real routes, real element ids (`btn-pi-ok`, `pi-note`, …), real field keys
(~39 for payroll-items), real origin structure across three systems, 309 screenshots — and **no real
values**, because `raw_value_persisted: false`.

`[INF]` A replica is credible when it reproduces the things we actually observed and is explicit
about the rest:

**Reproduce** — routes and origins as observed; element ids exactly as recovered; the field set;
per-system differences where the telemetry shows them; success and failure states, including at
least one failure the automation must handle.

**Do not reproduce or claim** — visual fidelity beyond what screenshots support; validation rules
of the real systems (we cannot see them); performance characteristics; authentication.

**Label everything, in the artefact and in the report**, as exactly one of:
`TELEMETRY-RECOVERED` (routes, element ids, field keys) · `SYNTHETIC` (all values, the source
document) · `REPLICA` (the target application) · `PRODUCTION-UNVERIFIED` (selector stability, the
existence of an import path, real validation behaviour, volumes).

`[INF]` The claim the prototype can honestly make is: *"this mechanism drives the selectors the
client's own telemetry contains."* The claim it cannot make is that it has run against production.
Stating the second clearly is what makes the first believable.

---

## 14. Derived design requirements

Every requirement carries its reason. Stage 3 must satisfy these; how, is Stage 3's decision.

### Functional
- **F1** Ingest a structured source document and produce typed records. `[DATASET]`
- **F2** Map source fields to target fields via a **declarative definition**, not code. `[VENDOR]` `[LIT]`
- **F3** Execute the same source record against **multiple target systems**, each addressed
  independently. `[DATASET]`
- **F4** Support the two observed entry variants (type-led `__p01`, copy-led `__p05`) within one
  definition. `[DATASET]`
- **F5** Add a further module by adding a definition, without engine changes. `[VENDOR]` `[DATASET]`

### Reliability — what must never happen
- **R1** Never write without passing validation. `[JP]` `[VENDOR]`
- **R2** Never write without recorded human approval. `[JP]` `[VENDOR]`
- **R3** Never double-register a source record in a target — idempotency key required. `[LIT]`
- **R4** Never proceed on an unrecognised screen; stop and report. `[LIT]`
- **R5** Never auto-rollback a completed target write; reconcile instead. `[LIT]` `[INF]`
- **R6** Never fabricate a value not present in the source.

### Data
- **D1** Source schema declaration; **D2** target field keys per system; **D3** element descriptors
  with anchors, versioned per system `[VENDOR]`; **D4** validation rules as data, not code
  `[VENDOR]`; **D5** idempotency key derivation rule `[LIT]`.

### Human control
- **H1** Record-level pre-execution approval. `[JP]`
- **H2** Exception-only review for rule failures — not field-by-field. `[VENDOR]`
- **H3** Corrections captured **with a change reason**. `[VENDOR]`
- **H4** Post-execution verification of what landed in each target. `[JP]`
- **H5** Separation between who initiates and what executes. `[VENDOR]`

### Validation
- **V1** Verdicts are **VALID / INVALID / REQUIRES_REVIEW** — no confidence score on a
  deterministic mapping. `[VENDOR]` `[DATASET]` `[INF]`
- **V2** Rules declared per field and per target.
- **V3** All validation before the first write. `[INF]`

### Audit
- **A1** One immutable record per execution containing the §9 field list. `[VENDOR]` `[JP]`
- **A2** **Definition version** recorded with every execution. `[LIT]`
- **A3** Per-target outcome and failure reason recorded separately. `[LIT]`

### Integration
- **I1** The target adapter is an **interface**; UI automation is its first implementation, so an
  import or API path can replace it without touching definitions or validation. `[JP]` `[INF]`
- **I2** Target system identity (origin) is a parameter, never hard-coded. `[DATASET]`

### Extensibility
- **E1** New module = new definition file. **E2** New target system = new system entry, reusing the
  shared widget convention. `[DATASET]`

### Production prerequisites — cannot be demonstrated locally
- **P1** Existence and coverage of an import/API path in each system. `[JP]`
- **P2** Real selector stability over time. `[LIT]`
- **P3** Real validation rules of the target systems.
- **P4** Authentication, permissions and segregation of duties. `[VENDOR]`
- **P5** True volumes and seasonality. `[DATASET]`
- **P6** Ownership and maintenance responsibility — the 野良ロボット question. `[JP]`

---

## 15. Open questions carried into Stage 3

**Must be decided in Stage 3 (design choices, not research gaps)**
1. How far the definition schema goes — how much is declarative before it becomes a language.
2. Whether approval is per record or per batch, given the observed execution sizes.
3. Whether the design-time AI mapping assistant (§11) earns its place at all.
4. What the reconciliation view must show for a partially-applied record.

**Record as client validation questions (cannot be resolved by us)**
5. Import/API availability and field coverage — P1.
6. Real selector stability — P2.
7. Whether `__p01` and `__p05` are one procedure or two — carried from Step 2.
8. Who owns and maintains the automation — P6.

---

## 16. What Stage 3 must decide

The research makes these decisions possible and, we think, largely determined. Stage 3 should make
them explicitly rather than by default.

1. **Target adapter abstraction** — confirm the execution backend is an interface with UI automation
   as one implementation (I1), and fix its boundary.
2. **Definition schema scope** — which of the §6 concepts are declared, and which stay in code.
3. **Multi-target execution model** — independent per-target commits with idempotency keys, versus
   any attempt at transactional semantics (§8).
4. **Partial-failure policy** — reconciliation record and human decision, versus compensation (R5).
5. **Validation model** — VALID / INVALID / REQUIRES_REVIEW driven by declared rules, and explicitly
   *not* a confidence score (V1).
6. **HITL placement** — record-level pre-execution approval plus exception-only review plus
   post-execution verification (H1–H4), and what the operator actually sees.
7. **Audit record shape** — the §9 field list, storage form, and immutability guarantee.
8. **AI inclusion** — confirm exclusion from the execution path, and decide the design-time
   assistant either in or out (§11).
9. **Replica scope** — exactly which observed artefacts are reproduced, and how the four honesty
   labels appear in the artefact itself (§13).
10. **Demonstrable failure path** — which failure from §10 is deliberately exercised in the
    demonstration, since a prototype that only shows the happy path evidences less than one that
    shows a controlled failure.

---

## 17. References

`[LIT]`
- Bosco, A., Augusto, A., Dumas, M., La Rosa, M., Fortino, G. (2019). *Discovering Automatable Routines from User Interaction Logs.* BPM Forum. https://lepo.it.da.ut.ee/~dumas/pubs/rpadiscovery.pdf
- Syed, R. et al. (2020). *Robotic Process Automation: Contemporary Themes and Challenges.* Computers in Industry 115, 103162.
- *How to Keep RPA Maintainable?* BPM 2020. https://www.researchgate.net/publication/344176607_How_to_Keep_RPA_Maintainable
- Drouin, A. et al. *WorkArena: How Capable Are Web Agents at Solving Common Knowledge Work Tasks?* ServiceNow Research. https://servicenow.github.io/WorkArena/
- *RPA in Business Process Management: A Systematic Literature Review.* Technologies 14(4), 225. https://www.mdpi.com/2227-7080/14/4/225
- Saga pattern and idempotency in distributed transactions. https://temporal.io/blog/saga-pattern-made-easy

`[JP]`
- 給与計算と会計の連携とは？二重入力を減らす進め方と確認ポイント. https://bakuraku.jp/knowledge/knowledge-payroll/what-is-the-integration-of-payroll-and-accounting/
- 総務省. *自治体におけるRPA導入ガイドブック*, 令和7年7月. https://www.soumu.go.jp/main_content/000731625.pdf
- 三菱総合研究所. *RPAを「野良ロボ」にしない.* https://www.mri.co.jp/knowledge/mreview/201803-5.html
- 会計システム連携とは｜販売・経費・給与とつなぐ方法と注意点. https://www.asteria.com/jp/warp/blog/165665.html

`[VENDOR]`
- UiPath. *Studio — About Object Repository.* https://docs.uipath.com/studio/standalone/2023.4/user-guide/about-object-repository
- Protiviti. *Building Bot Boundaries: RPA Controls in SOX Systems.* https://blog.protiviti.com/2018/10/31/building-bot-boundaries-rpa-controls-in-sox-systems/
- AWS. *Customize business rules for intelligent document processing with human review.* https://aws.amazon.com/blogs/machine-learning/customize-business-rules-for-intelligent-document-processing-with-human-review-and-bi-visualization/

`[OSS]` Playwright (Apache-2.0) · Selenium (Apache-2.0) · python-docx, openpyxl, pydantic (MIT)

`[DATASET]` `build/dataset_b/segments_rich.jsonl`, `build/dataset_b/blocks.jsonl`,
`build/dataset_b/step2/`, `reports/STEP2_ANALYSIS.md`.

**Search limitation.** We found no source documenting the import/API capabilities of the specific
systems in Dataset B, and we did not look for one — they are a test environment. §4's three-bucket
separation exists precisely so that absence is not mistaken for evidence.
