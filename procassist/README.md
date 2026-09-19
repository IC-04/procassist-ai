# ProcAssist — Step 3 vertical slice

A replica of three Dataset B screens with a ProcAssist panel mounted beside the record. The
panel names the governing regulation, shows the clause, evaluates it, and drafts the comment
the operator types — **with the judgement left empty**. A human chooses the disposition and a
human clicks the host's own submit button. The tool never does.

## Run it

```bash
.venv/bin/python -m procassist.api
```

Then open **<http://127.0.0.1:5132/payroll-items>** and press **▶ エージェントで一括準備**.

Serves one app on three ports, because `(origin, route)` is the module key in Dataset B:

| Queue | Open | Records | Demonstrates |
|---|---|---|---|
| M05 FI 請求書承認・経費精算 | <http://127.0.0.1:5133/payroll-items> | P6, 108 | **MISS** — no regulation governs an invoice amount |
| M01 HR 経費精算・給与変更 | <http://127.0.0.1:5132/payroll-items> | P1, 120 | **OK** / **FLAG** — 接待交際費規程 第２条 tiers |
| M07 FI 経費承認（管理職） | <http://127.0.0.1:5133/leave-applications> | P9, 24 | **REQUIRES_REVIEW** — 金額 is not on that screen |

## The ninety-second demo

1. **<http://127.0.0.1:5132/payroll-items>** — 120 raw records, nothing resolved.
2. **▶ エージェントで一括準備** — every row resolves in about half a second, gaining a status,
   the governing regulation and a staged draft. The strip above the table reads
   `0 → 23 documents · 0 → 120 drafts · 6–20 app switches · 3,497 keystrokes · 887 look-ups`
   and, last and deliberately, **`0 → 0 dispositions taken`**.
3. Click the **⚠ FLAG** row `P1-07106250-010` — the panel names 接待交際費規程, shows 第２条
   verbatim, and explains why ¥135,181 needs 社長承認.
4. **下書きを使う** fills the host field with the judgement slot *empty*; a chip completes it;
   you click 登録確定 yourself.
5. **エビデンス / Evidence** in the footer — what was measured, and what the system cannot do.

`日本語 · EN · 併記` in the page chrome switches language. The 規程 clause text stays Japanese
in every mode.

## The four cases

| Open | Verdict |
|---|---|
| `/payroll-items/P1-07089771-005` on **:5132** | `✓ OK` · 60,936円 → 役員承認, one tier matches |
| `/payroll-items/P1-07106250-010` on **:5132** | `⚠ FLAG` · 135,181円 → two tiers match, strictest 社長承認 |
| `/payroll-items/P6-07010448-004` on **:5133** | `? MISS` · no document named, no ranked fallback |
| `/leave-applications/P9-07084298-006` on **:5133** | `! REQUIRES_REVIEW` · no 金額 column, no draft offered |

On the FLAG record: press **下書きを使う** and `#pi-note` fills with
`経費精算確認済み。費目：接待交際費　金額：135,181円。。` — the judgement slot empty. Click the chip
and it completes to the string an operator actually typed in Dataset B. Then click **登録確定**
yourself; only then does `登録確定しました` appear.

## Optional: watch the retriever lose

```bash
PROCASSIST_CHALLENGER=1 .venv/bin/python -m procassist.api
```

Adds 「モデルで再検索 / try the retriever」 to the panel's document section: a local BM25 +
character-3-gram retriever over all 365 clauses, run beside the lookup table. On the FLAG
record it **disagrees** — it matches the record's surface text to the captured ledger and
preamble, not to 第２条. It is tagged `UNEVALUATED`, because the 148 labelled pairs behind the
table's 64.2% are not recoverable from the committed artifacts. Local only: no key, no
network, no model file.

## Read the audit trail

```bash
.venv/bin/python -c "from procassist.adapters.audit import AuditLog; a=AuditLog(); [print(r['seq'], r['event_type'], r['record_id'], '|', r['suggested'], '->', r['human_action']) for r in a.tail(3)]; print('chain_ok', a.verify_chain())"
```

## Test

```bash
.venv/bin/python -m pytest tests/test_procassist_*.py -q
```

The browser end-to-end suite and the demo recorder need Playwright, which is **not installed
here**, so both skip. To enable:

```bash
.venv/bin/pip install playwright && .venv/bin/playwright install chromium
```

## Layout

- `core/` — pure, no I/O: `definitions` `lookup` `rules` `completeness` `comment` `result` `engine`
- `adapters/` — `documents` `records` `defs` `audit`; `build/dataset_b/evidence/*` is **read-only**
- `replica/` `panel/` `api/` — Jinja2 + one JS file + FastAPI; no build step, no framework
- `challenger/` — the local retriever, off unless `PROCASSIST_CHALLENGER=1`
- `i18n/gloss_ja_en.json` · `measured/action_budget.json` — committed data: the JA→EN screen
  gloss, and the action budget measured once from telemetry
- `../definitions/*.toml` — **the artifact that executes.** Every rule the engine applies is a
  line in one of these three files, with its Dataset B evidence in a comment beside it. The
  tiers are deliberately *not* restated there: they are read from `documents.jsonl`, so the
  files and the corpus cannot drift apart.

## What it will not do

No confidence scores — four statuses only. The retriever's scores are labelled scores and
never reach a `PrepareResult`. No LLM, no embeddings, no vector store. No guessed
document when the lookup misses, and no fabricated amount when a screen does not show one. No
code path sets or clicks `btn-*-ok`; `tests/test_procassist_panel_invariants.py` reads
`panel/panel.js` and fails if one appears.

Records were captured repeatedly: 324 of 898 were seen in more than one ステータス. The detail
page shows the first observation and says so rather than picking one silently.

The **one policy knob** in the system is each queue's approval-authority ceiling, in
`definitions/*.toml`. On the HR queue it is a *declared* parameter tagged `[INF]` in the panel,
not a measurement: 接待交際費 settlements were observed there in both the 役員承認 and the
社長承認 band with no field distinguishing them. Change that one line and the OK/FLAG split
moves. A reviewer should not read it as measured.

No absolute time or cost claim is made anywhere. The impact calculator ships with its three
inputs empty because they are the client's numbers.

See `docs/DECISIONS.md` ADR-025.
