/* Agent prefill over a whole queue, with the before/after it produces.
 *
 * The operator's unit of pain is not one record, it is a hundred and twenty of them, each
 * needing a Word round trip. This file puts that on screen, then shows what the agent did and —
 * more importantly — the one thing it did not do.
 *
 * INVARIANTS, asserted in tests/test_procassist_queue_prefill.py:
 *   this file writes to no host field, sets no judgement, and fires no click. It renders
 *   status pills and caches the batch result under sessionStorage so opening a prepared row
 *   is instant.
 */
(function () {
  "use strict";

  var root = document.getElementById("queue-root");
  if (!root) { return; }

  var definitionId = root.dataset.definitionId;
  var route = root.dataset.route;
  var button = document.getElementById("prepare-all");
  var progress = document.getElementById("prepare-progress");
  var strip = document.getElementById("beforeafter");
  var CACHE_KEY = "procassist:batch:" + definitionId;

  var PILL = { OK: "✓", FLAG: "⚠", REQUIRES_REVIEW: "!", MISS: "?" };

  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function reducedMotion() {
    return window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function cellFor(recordId) {
    return document.querySelector('[data-agent-cell="' + recordId + '"]');
  }

  function paint(row) {
    var cell = cellFor(row.record_id);
    if (!cell) { return; }
    var doc = row.document_heading
      ? '<span class="q-doc">' + esc(row.document_heading) + "</span>"
      : "";
    var expected = row.expected_ja
      ? '<span class="q-expected">' + esc(row.expected_ja) + "</span>"
      : "";
    var draft = row.draft_ready
      ? '<span class="q-draft"><span class="ja">下書きあり</span>' +
        '<span class="en">draft ready</span></span>'
      : "";
    cell.innerHTML =
      '<span class="q-pill pa-' + esc(row.status) + '">' +
      '<span class="q-mark">' + (PILL[row.status] || "·") + "</span>" +
      esc(row.status) + "</span>" + expected + doc + draft;
    cell.parentElement.classList.add("resolved");
    if (!reducedMotion()) { cell.classList.add("settle"); }
  }

  function countUp(el, to, suffix) {
    if (reducedMotion()) { el.textContent = to + (suffix || ""); return; }
    var start = performance.now(), dur = 500;
    function frame(now) {
      var t = Math.min(1, (now - start) / dur);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(to * eased) + (suffix || "");
      if (t < 1) { requestAnimationFrame(frame); }
    }
    requestAnimationFrame(frame);
  }

  function renderStrip(summary, seconds) {
    var c = summary.counts;
    var a = summary.after;
    var breakdown = ["OK", "FLAG", "REQUIRES_REVIEW", "MISS"]
      .filter(function (k) { return c[k]; })
      .map(function (k) {
        return '<span class="ba-chip pa-' + k + '">' + esc(c[k]) + " " + esc(k) + "</span>";
      }).join("");

    strip.innerHTML =
      '<div class="ba-head">' +
        '<span class="ba-col-b">BEFORE</span>' +
        '<span class="ba-col-a">AFTER <span class="ba-sub">' + seconds.toFixed(1) +
        " s · " + esc(summary.n_records) + " records</span></span>" +
      "</div>" +
      row("根拠文書 resolved", "documents resolved", "0",
          '<span data-cu="' + a.documents_resolved + '">0</span>', breakdown) +
      row("下書き staged", "drafts staged", "0",
          '<span data-cu="' + a.drafts_staged + '">0</span>', "") +
      row("操作 avoided", "actions avoided", "0",
          '<span data-cu="' + a.actions_avoided_range[0] + '">0</span>–' +
          '<span data-cu="' + a.actions_avoided_range[1] + '">0</span>' +
          unit("アプリ切替", "app switches") +
          ' · <span data-cu="' + a.keystrokes_total + '">0</span>' +
          unit("打鍵", "keystrokes") +
          ' · <span data-cu="' + a.lookups_total + '">0</span>' +
          unit("参照", "look-ups"), "") +
      '<div class="ba-row ba-zero">' +
        '<span class="ba-label"><span class="ja">処分 taken</span>' +
        '<span class="en">dispositions taken</span></span>' +
        '<span class="ba-b">0</span><span class="ba-arrow">→</span>' +
        '<span class="ba-a">0</span>' +
        '<span class="ba-keep"><span class="ja">← 変わりません。意図的です。</span>' +
        '<span class="en">← unchanged, and deliberately</span></span>' +
      "</div>" +
      '<p class="ba-human"><span class="ja">処分は 0 件。判断は人間が行います。</span>' +
      '<span class="en">0 dispositions taken — the human decides.</span></p>' +
      '<p class="ba-caveat pa-en en">' + esc(summary.caveat_en) + "</p>";

    strip.hidden = false;
    Array.prototype.forEach.call(strip.querySelectorAll("[data-cu]"), function (el) {
      countUp(el, parseInt(el.getAttribute("data-cu"), 10), "");
    });
  }

  function unit(ja, en) {
    return ' <span class="ba-unit"><span class="ja">' + esc(ja) + "</span>" +
      '<span class="en">' + esc(en) + "</span></span>";
  }

  function row(labelJa, labelEn, before, after, extra) {
    return '<div class="ba-row">' +
      '<span class="ba-label"><span class="ja">' + esc(labelJa) + "</span>" +
      '<span class="en">' + esc(labelEn) + "</span></span>" +
      '<span class="ba-b">' + before + "</span>" +
      '<span class="ba-arrow">→</span>' +
      '<span class="ba-a">' + after + " " + extra + "</span></div>";
  }

  function cascade(rows, done) {
    var step = reducedMotion() ? 0 : 25;
    var i = 0;
    function next() {
      var budget = reducedMotion() ? rows.length : 8;   // paint in small batches, smoothly
      while (i < rows.length && budget-- > 0) {
        paint(rows[i]);
        i += 1;
      }
      progress.textContent = i + " / " + rows.length;
      if (i < rows.length) { setTimeout(next, step); } else { done(); }
    }
    next();
  }

  button.addEventListener("click", function () {
    button.disabled = true;
    progress.hidden = false;
    progress.textContent = "0 / ?";
    var t0 = performance.now();
    fetch("/v1/prepare_queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ definition_id: definitionId })
    }).then(function (r) { return r.json(); }).then(function (batch) {
      try {
        var byId = {};
        batch.rows.forEach(function (row) { byId[row.record_id] = row; });
        sessionStorage.setItem(CACHE_KEY, JSON.stringify(byId));
      } catch (e) { /* private mode: the detail page just re-prepares */ }
      document.body.classList.add("prepared");
      cascade(batch.rows, function () {
        renderStrip(batch.summary, (performance.now() - t0) / 1000);
        progress.textContent = batch.rows.length + " / " + batch.rows.length;
        button.disabled = false;
      });
    }).catch(function () {
      progress.textContent = "準備できませんでした / could not prepare";
      button.disabled = false;
    });
  });
}());
