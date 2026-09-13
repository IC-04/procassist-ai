# WORK_LOG

Append-only. One entry per working session. This is a **graded deliverable**
(`README.md` Deliverables §4): it must record what was tried, what failed, decisions taken,
and how generative AI was used.

Newest entries at the bottom.

---

## Template

```markdown
### YYYY-MM-DD · Phase N · <session title>

**Goal**
**Did**
**Result**            numbers, not adjectives
**Problems**          including things that did not work
**Decisions**         link to ADR if architectural
**Generative AI use** what was used, for what, how verified
**Next**
**Time spent**
```

---

### 2026-09-12 · Phase 0 (pre) · Perception layer bootstrap

**Goal** Build the deterministic perception + TEKG layer and see whether the representation
is rich enough to support contextual reasoning.

**Did** Implemented `procmine/{normalise,blocks,tekg,context,cli}.py`. Ran against
`dataset_b` (15 sessions, 20,477 events).

**Result**
- 7,408 raw context-state changes → **1,782 activity blocks** (11.5 events/block,
  2,771 micro-excursions absorbed, 119 blocks/session).
- TEKG edges: `same_surface_as` 2150, `returns_to` 2150, `same_field_as` 940,
  `same_system_as` 235, `same_route_as` 182, `shared_value_with` 74, `dataflow_to` 35.
- Reasoner payload ≈ 1.7k tokens at `window=5`.

**Problems**
- Degenerate tail: many 1-event / 0-second blocks survive absorption; 63 blocks have an empty
  surface key. Median is 4 events/block, which is lower than intended.
- 1,767 ungated windows × 1.7k tokens ≈ 3M tokens for B alone → the ambiguity gate is
  mandatory, not optional.
- `dataset_a/` is not on disk. Phase 1 is blocked.

**Decisions** ADR-002 (provenance demoted), ADR-004 (block is the reasoning unit),
ADR-005 (TEKG is evidence/explanation, not inference).

**Generative AI use** Claude (chat) for architecture, spec authoring and the initial
implementation of the perception layer. All numbers above were produced by running the code,
not asserted by the model.

**Next** Phase 0: stabilise repo, fix the block tail, then Gate G0.

**Time spent** ~3 h
