/* Hover cards for links to term and author pages.
   Terms show their short definition; authors show nationality, medium, years and notable works.
   Data comes from assets/data/preview-terms.json and preview-authors.json (written by build.py),
   each loaded the first time a link of that kind is hovered. Mouse and keyboard only: on touch
   screens a tap just follows the link. */
(function () {
  var BASE = window.SITE_BASE || "/";
  var VER = ((document.currentScript && document.currentScript.src.match(/[?&]v=([^&]+)/)) || [])[1] || "";
  var KINDS = { terms: "terms", authors: "authors" };
  var data = {}, loading = {};
  var card = null, current = null, showTimer = null, hideTimer = null;
  var canHover = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  function load(kind) {
    if (data[kind]) return Promise.resolve(data[kind]);
    if (!loading[kind]) {
      loading[kind] = fetch(BASE + "assets/data/preview-" + kind + ".json?v=" + VER)
        .then(function (r) { return r.json(); })
        .then(function (d) { data[kind] = d; return d; })
        .catch(function () { data[kind] = {}; return data[kind]; });
    }
    return loading[kind];
  }

  // "terms/irony/" for a link to a term page, or null.
  function keyFor(a) {
    if (!a || !a.href || a.target === "_blank") return null;
    if (a.origin && a.origin !== location.origin) return null;
    var path = a.pathname || "";
    if (path.indexOf(BASE) !== 0) return null;
    var rel = path.slice(BASE.length);
    if (rel && rel.slice(-1) !== "/") rel += "/";
    var parts = rel.split("/");
    if (parts.length !== 3 || !KINDS[parts[0]] || !parts[1] || parts[1] === "browse") return null;
    if (path === location.pathname) return null; // a link to the page you're on
    if (a.closest("header, nav, .menu, .results, .full-results, [data-no-preview]")) return null;
    return rel;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function termHtml(d) {
    return '<p class="pv-kind">Term</p><p class="pv-title">' + esc(d[0]) + "</p>" +
      (d[1] ? '<p class="pv-text">' + esc(d[1]) + "</p>" : '<p class="pv-text pv-muted">No short definition yet.</p>');
  }

  function authorHtml(d) {
    var about = [d[1], d[2]].filter(Boolean).join(" · ");
    var works = d[4] || [];
    var list = works.map(function (w) {
      var t = w[2] ? "“" + esc(w[0]) + "”" : "<i>" + esc(w[0]) + "</i>";
      return "<li>" + t + (w[1] ? ' <span class="pv-muted">' + esc(w[1]) + "</span>" : "") + "</li>";
    }).join("");
    return '<p class="pv-kind">Author</p><p class="pv-title">' + esc(d[0]) + "</p>" +
      (about ? '<p class="pv-meta">' + esc(about) + "</p>" : "") +
      (d[3] ? '<p class="pv-meta">' + esc(d[3]) + "</p>" : "") +
      (list ? '<p class="pv-sub">Notable works</p><ul class="pv-works">' + list + "</ul>" +
        (d[5] ? '<p class="pv-muted pv-more">and ' + d[5] + " more</p>" : "") : "");
  }

  function ensureCard() {
    if (card) return card;
    card = document.createElement("div");
    card.className = "pv-card";
    card.setAttribute("role", "tooltip");
    card.id = "pv-card";
    card.hidden = true;
    document.body.appendChild(card);
    return card;
  }

  function place(a) {
    var r = a.getBoundingClientRect();
    var w = card.offsetWidth, h = card.offsetHeight, gap = 8;
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var left = Math.min(Math.max(8, r.left), vw - w - 8);
    var top = r.bottom + gap;
    if (top + h > vh - 8 && r.top - gap - h > 8) top = r.top - gap - h; // flip above when there's no room below
    card.style.left = left + window.scrollX + "px";
    card.style.top = top + window.scrollY + "px";
  }

  function show(a, key) {
    var kind = key.split("/")[0];
    load(kind).then(function (d) {
      if (current !== a) return;
      var rec = d[key];
      if (!rec) return;
      ensureCard();
      card.innerHTML = kind === "terms" ? termHtml(rec) : authorHtml(rec);
      card.className = "pv-card pv-" + kind;
      card.hidden = false;
      place(a);
      a.setAttribute("aria-describedby", "pv-card");
    });
  }

  function hide() {
    clearTimeout(showTimer);
    if (current) current.removeAttribute("aria-describedby");
    current = null;
    if (card) card.hidden = true;
  }

  function start(a, delay) {
    var key = keyFor(a);
    if (!key) return;
    clearTimeout(hideTimer);
    if (current === a) return;
    clearTimeout(showTimer);
    if (current) current.removeAttribute("aria-describedby");
    current = a;
    load(key.split("/")[0]); // start fetching while the delay runs
    showTimer = setTimeout(function () { show(a, key); }, delay);
  }

  function leave(a) {
    if (a !== current) return;
    clearTimeout(showTimer);
    hideTimer = setTimeout(hide, 120);
  }

  if (canHover) {
    document.addEventListener("mouseover", function (ev) {
      var a = ev.target.closest && ev.target.closest("a[href]");
      if (a) start(a, 350);
    });
    document.addEventListener("mouseout", function (ev) {
      var a = ev.target.closest && ev.target.closest("a[href]");
      if (a && !(ev.relatedTarget && a.contains(ev.relatedTarget))) leave(a);
    });
    document.addEventListener("mousedown", hide);
  }
  // Keyboard: show when a link gets focus from Tab (not from a click).
  document.addEventListener("focusin", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[href]");
    if (a && a.matches(":focus-visible")) start(a, 150);
  });
  document.addEventListener("focusout", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[href]");
    if (a) leave(a);
  });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") hide(); });
  window.addEventListener("scroll", function () { if (current && card && !card.hidden) place(current); }, { passive: true });
})();
