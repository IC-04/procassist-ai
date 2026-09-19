/* ProcAssist side panel.
 *
 * Mounted inside the host's own detail page, beside the record — not on a page of its own.
 * It reads the record context from the DOM, calls POST /v1/prepare, and renders what came
 * back. It prepares; it does not decide and it does not act.
 *
 * ── HARD INVARIANTS, enforced here and asserted in tests/test_panel_invariants.py ──
 *   1. This file never programmatically fires a click, never constructs or dispatches a
 *      synthetic event, and never submits a form. The test greps this file for the literal
 *      names of those five APIs and fails if any of them appears.
 *   2. It never writes to the host's disposition control (btn-pi-ok / btn-la-ok): it does not
 *      set .disabled, .value or any attribute on it. It only *listens*, so that the human's
 *      own click can be written to the audit log.
 *   3. No judgement chip is preselected. `chosenJudgement` starts null and is only ever set
 *      inside a chip's click handler — that is, by a person.
 *   4. The only host element this file ever writes to is the note textarea, and only when the
 *      human presses [下書きを使う].
 */
(function () {
  "use strict";

  var host = document.getElementById("main");
  if (!host) { return; }

  var ctx = {
    recordId:     host.dataset.recordId,
    origin:       host.dataset.origin,
    route:        host.dataset.route,
    definitionId: host.dataset.definitionId,
    moduleId:     host.dataset.moduleId,
    noteId:       host.dataset.noteElementId,
    submitId:     host.dataset.submitElementId
  };

  var panel = document.getElementById("procassist-panel");
  var state = { result: null, chosenJudgement: null, draftUsed: false, baseText: "" };

  var STATUS_TEXT = {
    OK:              { mark: "✓", label: "OK" },
    FLAG:            { mark: "⚠", label: "FLAG" },
    REQUIRES_REVIEW: { mark: "!", label: "REQUIRES_REVIEW" },
    MISS:            { mark: "?", label: "MISS" }
  };

  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function post(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }

  function audit(eventType, humanAction, detail) {
    if (!state.result) { return Promise.resolve(); }
    return post("/v1/event", {
      trace_id:      state.result.trace_id,
      event_type:    eventType,
      record_id:     ctx.recordId,
      definition_id: ctx.definitionId,
      module_id:     ctx.moduleId,
      suggested:     suggestionSummary(),
      human_action:  humanAction || null,
      detail:        detail || {}
    });
  }

  function suggestionSummary() {
    if (!state.result) { return null; }
    var threshold = state.result.checks.filter(function (c) { return c.kind === "threshold"; })[0];
    return threshold && threshold.expected_ja
      ? state.result.status + ":" + threshold.expected_ja
      : state.result.status;
  }

  /* ── rendering ───────────────────────────────────────────────────────────────────────── */

  function renderStatus(r) {
    var s = STATUS_TEXT[r.status] || { mark: "·", label: r.status };
    return '<div class="pa-status pa-' + esc(r.status) + '">' +
      '<span class="pa-mark">' + s.mark + "</span>" +
      '<span class="pa-statuslabel">' + esc(s.label) + "</span>" +
      (r.population
        ? '<span class="pa-pop">' + esc(r.population.n_same_status) + " / " +
          esc(r.population.n_queue) + "</span>"
        : "") +
      '<span class="pa-trace mono">' + esc(r.trace_id) + "</span></div>" +
      (r.population
        ? '<p class="pa-popnote">ILLUSTRATIVE · このキューの ' + esc(r.population.n_queue) +
          " 件中 " + esc(r.population.n_same_status) + " 件が同じ判定（規程の対象は " +
          esc(r.population.n_governed) + " 件）</p>"
        : "");
  }

  function renderRecord(r) {
    var rows = Object.keys(r.record_fields).map(function (k) {
      return "<tr><th>" + esc(k) + "</th><td>" + esc(r.record_fields[k]) + "</td></tr>";
    }).join("");
    return section("レコード", "record",
      '<table class="pa-kv">' + rows + "</table>" +
      '<p class="pa-note">' + esc(r.module_id) + " · " + esc(r.module_name_ja) +
      " · <span class='mono'>" + esc(ctx.origin + ctx.route) + "</span></p>");
  }

  function renderDocument(r) {
    if (!r.document) {
      return section("規程", "document",
        '<p class="pa-miss-body">該当する規程は特定されていません。推測は行いません。</p>');
    }
    var d = r.document;
    var body =
      '<p class="pa-docname">' + esc(d.regulation_name_ja) + "</p>" +
      '<p class="pa-note">' + esc(d.clause_heading_ja) + " ・ 観測 " + esc(d.n_captures) +
      " キャプチャ</p>" +
      '<button type="button" class="pa-link" id="pa-viewsource">出典を表示（View source）</button>' +
      '<div class="pa-source" id="pa-source" hidden></div>';
    return section("規程（governing document）", "document", body);
  }

  function renderClause(r) {
    if (!r.clause) { return ""; }
    return section("条文（clause）", "clause",
      '<p class="pa-clauseheading">' + esc(r.clause.heading_ja) + "</p>" +
      '<blockquote class="pa-clause">' + esc(r.clause.text_ja) + "</blockquote>" +
      '<p class="pa-note mono">char_span ' + esc(r.clause.char_span[0]) + "–" +
      esc(r.clause.char_span[1]) + " / " + esc(r.clause.body_len) + "</p>");
  }

  function renderChecks(r) {
    var items = r.checks.map(function (c, i) {
      var s = STATUS_TEXT[c.status] || { mark: "·", label: c.status };
      var rows = "";
      if (c.expected_ja) { rows += '<tr><th>Expected</th><td>' + esc(c.expected_ja) + "</td></tr>"; }
      if (c.observed_ja) { rows += '<tr><th>Observed</th><td>' + esc(c.observed_ja) + "</td></tr>"; }
      if (c.why_ja)      { rows += '<tr><th>Why</th><td>' + esc(c.why_ja) + "</td></tr>"; }
      if (c.why_en)      { rows += '<tr><th></th><td class="pa-en">' + esc(c.why_en) + "</td></tr>"; }
      return '<li class="pa-check pa-' + esc(c.status) + '" data-check-id="' + esc(c.check_id) + '">' +
        '<div class="pa-checkhead"><span class="pa-mark">' + s.mark + "</span>" +
        "<strong>" + esc(c.label_ja) + "</strong>" +
        '<span class="pa-en">' + esc(c.label_en) + "</span></div>" +
        '<table class="pa-kv pa-why">' + rows + "</table>" +
        '<div class="pa-checkacts">' +
          '<button type="button" class="pa-chip pa-small" data-agree="' + i + '">同意</button>' +
          '<button type="button" class="pa-chip pa-small" data-dismiss="' + i + '">却下</button>' +
        "</div></li>";
    }).join("");
    return section("チェック（checks）", "checks", '<ul class="pa-checks">' + items + "</ul>");
  }

  function renderDraft(r) {
    if (!r.draft) {
      return section("コメント下書き", "draft",
        '<p class="pa-miss-body">このレコードの項目からは、観測されたコメント書式を再現できません。' +
        "下書きは提示しません。</p>");
    }
    var d = r.draft;
    var chips = d.judgement_options.map(function (o, i) {
      return '<button type="button" class="pa-chip pa-judgement" data-judgement="' + i + '">' +
        esc(o.text_ja) + '<span class="pa-n">観測 ' + esc(o.observed_n) + "</span></button>";
    }).join("");
    return section("コメント下書き（draft）", "draft",
      '<pre class="pa-draft" id="pa-drafttext">' + esc(d.text_ja) + "</pre>" +
      '<p class="pa-note">判断欄「' + esc(d.judgement_slot) +
      "」は空のままです。選ぶのは人です。</p>" +
      '<div class="pa-acts"><button type="button" class="pa-primary" id="pa-usedraft">' +
      "下書きを使う [Use draft]</button></div>" +
      '<p class="pa-note">判断（judgement）— 既定選択はありません</p>' +
      '<div class="pa-chips">' + chips + "</div>" +
      '<p class="pa-note pa-en">' + esc(d.evidence_note_en) + "</p>");
  }

  function section(title, id, body) {
    return '<section class="pa-section" id="pa-sec-' + id + '">' +
      "<h3>" + esc(title) + "</h3>" + body + "</section>";
  }

  function render() {
    var r = state.result;
    panel.innerHTML =
      '<div class="pa-head"><span class="pa-brand">ProcAssist</span>' +
      '<span class="pa-sub">prepares · does not decide</span></div>' +
      renderStatus(r) + renderRecord(r) + renderDocument(r) + renderClause(r) +
      renderChecks(r) + renderDraft(r);
    wire();
  }

  /* ── interaction. Every branch below is entered only by a human gesture. ─────────────── */

  function noteField() { return document.getElementById(ctx.noteId); }

  function composed() {
    var d = state.result.draft;
    if (!d) { return ""; }
    if (state.chosenJudgement === null) { return d.text_ja; }
    return d.template_ja.replace(/\{(\w+)\}/g, function (_, name) {
      if (name === d.judgement_slot) { return state.chosenJudgement; }
      return d.filled_slots[name] !== undefined ? d.filled_slots[name] : "";
    });
  }

  function refreshDraftText() {
    var pre = document.getElementById("pa-drafttext");
    if (pre) { pre.textContent = composed(); }
    if (state.draftUsed) {
      var field = noteField();
      if (field) { field.value = composed(); state.baseText = composed(); }
    }
  }

  function wire() {
    var use = document.getElementById("pa-usedraft");
    if (use) {
      use.addEventListener("click", function () {
        var field = noteField();
        if (!field) { return; }
        field.value = composed();          // the note textarea is the ONLY host element we write
        state.draftUsed = true;
        state.baseText = field.value;
        audit("draft_used", "pasted the draft into #" + ctx.noteId,
              { text_ja: field.value, judgement: state.chosenJudgement });
      });
    }

    Array.prototype.forEach.call(panel.querySelectorAll("[data-judgement]"), function (btn) {
      btn.addEventListener("click", function () {
        var i = parseInt(btn.getAttribute("data-judgement"), 10);
        var option = state.result.draft.judgement_options[i];
        state.chosenJudgement = option.text_ja;      // set here, by a person, and nowhere else
        Array.prototype.forEach.call(panel.querySelectorAll("[data-judgement]"), function (b) {
          b.classList.toggle("chosen", b === btn);
        });
        refreshDraftText();
        audit("judgement_chosen", option.text_ja,
              { observed_n: option.observed_n, text_ja: composed() });
      });
    });

    Array.prototype.forEach.call(panel.querySelectorAll("[data-agree]"), function (btn) {
      btn.addEventListener("click", function () {
        var c = state.result.checks[parseInt(btn.getAttribute("data-agree"), 10)];
        btn.classList.add("chosen");
        audit("check_agreed", c.check_id, { status: c.status, expected_ja: c.expected_ja });
      });
    });
    Array.prototype.forEach.call(panel.querySelectorAll("[data-dismiss]"), function (btn) {
      btn.addEventListener("click", function () {
        var c = state.result.checks[parseInt(btn.getAttribute("data-dismiss"), 10)];
        btn.classList.add("chosen");
        audit("check_dismissed", c.check_id, { status: c.status, expected_ja: c.expected_ja });
      });
    });

    var view = document.getElementById("pa-viewsource");
    if (view) {
      view.addEventListener("click", function () {
        var box = document.getElementById("pa-source");
        var d = state.result.document;
        if (!box || !d) { return; }
        if (!box.hidden) { box.hidden = true; return; }
        fetch("/v1/source/" + d.document_id + "/" + state.result.clause.clause_id)
          .then(function (r) { return r.json(); })
          .then(function (src) {
            box.innerHTML =
              '<p class="pa-note">document_id（本文のsha256。文書の識別子ではありません）</p>' +
              '<p class="mono pa-id">' + esc(d.document_id) + "</p>" +
              '<p class="pa-note">同一条文を持つ document_id：' +
              esc(d.sibling_document_ids.length) + " 件</p>" +
              '<p class="pa-note">Word タイトル（キャプチャ時点）</p><ul class="pa-list">' +
              d.title_aliases.map(function (t) { return "<li>" + esc(t) + "</li>"; }).join("") +
              "</ul>" +
              '<p class="pa-note">capture_ids</p><p class="mono pa-id">' +
              esc(src.capture_ids.join(" ")) + "</p>" +
              '<p class="pa-note">session_ids</p><p class="mono pa-id">' +
              esc(src.session_ids.join(" ")) + "</p>" +
              '<p class="pa-note">本文（前後 400 字）</p>' +
              '<pre class="pa-context">' + esc(src.context_ja) + "</pre>";
            box.hidden = false;
            audit("source_viewed", "opened " + d.document_id.slice(0, 12), {});
          });
      });
    }
  }

  /* The host's own disposition control. We attach a *listener* and nothing else: this file
     never writes to it and never fires it. The human clicks it; we record that they did. */
  function watchHostDisposition() {
    var control = document.getElementById(ctx.submitId);
    if (!control) { return; }
    control.addEventListener("click", function () {
      var field = noteField();
      var text = field ? field.value : "";
      var edited = state.draftUsed && text !== state.baseText;
      if (edited) {
        audit("draft_edited", "edited the draft before submitting", { text_ja: text });
      }
      audit("host_submitted", "clicked #" + ctx.submitId, {
        text_ja: text,
        draft_used: state.draftUsed,
        judgement: state.chosenJudgement
      });
      var toast = document.getElementById("toast");
      if (toast) { toast.hidden = false; }
    });
  }

  post("/v1/prepare", { record_id: ctx.recordId, origin: ctx.origin, route: ctx.route })
    .then(function (result) {
      state.result = result;
      render();
      watchHostDisposition();
    })
    .catch(function (err) {
      panel.innerHTML = '<div class="pa-head"><span class="pa-brand">ProcAssist</span></div>' +
        '<p class="pa-miss-body">準備できませんでした: ' + esc(err) + "</p>";
    });
}());
