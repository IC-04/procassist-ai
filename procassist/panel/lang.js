/* JA · EN · 併記 — a display toggle, not a translation feature.
 *
 * The engine already emits every claim in both languages, so switching language is a class on
 * <html> and a stylesheet rule. Screen vocabulary with no *_en on the engine side is glossed
 * from procassist/i18n/gloss_ja_en.json, fetched once and applied to elements that declare
 * data-gloss. Regulation text is never touched here: its reference gloss is rendered by the
 * panel, beneath the Japanese, with its own not-authoritative label.
 */
(function () {
  "use strict";
  var KEY = "procassist:lang";
  var root = document.documentElement;

  function current() {
    try { return localStorage.getItem(KEY) || "ja"; } catch (e) { return "ja"; }
  }

  function apply(mode) {
    root.setAttribute("data-lang", mode);
    try { localStorage.setItem(KEY, mode); } catch (e) { /* private mode: session only */ }
    Array.prototype.forEach.call(document.querySelectorAll(".langtoggle button"),
      function (b) { b.classList.toggle("on", b.dataset.lang === mode); });
  }

  Array.prototype.forEach.call(document.querySelectorAll(".langtoggle button"),
    function (b) { b.addEventListener("click", function () { apply(b.dataset.lang); }); });
  apply(current());

  /* Gloss the screen's own vocabulary. Ids, names, dates and amounts carry no data-gloss
     attribute and are therefore never touched. */
  fetch("/v1/gloss").then(function (r) { return r.json(); }).then(function (g) {
    window.__procassistGloss = g;
    var terms = g.terms || {};
    Array.prototype.forEach.call(document.querySelectorAll("[data-gloss]"), function (el) {
      var en = terms[el.dataset.gloss !== "" ? el.dataset.gloss : el.textContent.trim()];
      if (!en || el.querySelector(".en")) { return; }
      var ja = el.textContent;
      el.textContent = "";
      var s1 = document.createElement("span"); s1.className = "ja"; s1.textContent = ja;
      var s2 = document.createElement("span"); s2.className = "en"; s2.textContent = en;
      el.appendChild(s1); el.appendChild(s2);
    });
  }).catch(function () { /* the page stays Japanese, which is the authoritative view */ });
}());
