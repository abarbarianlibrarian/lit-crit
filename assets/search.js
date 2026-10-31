(function () {
  var BASE = window.SITE_BASE || "/";
  var data = null, loading = null;

  function fold(s) {
    return (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function load() {
    if (data) return Promise.resolve(data);
    if (!loading) {
      loading = fetch(BASE + "assets/search.json")
        .then(function (r) { return r.json(); })
        .then(function (rows) {
          data = rows.map(function (r) {
            return { title: r[0], kind: r[1], url: BASE + r[2], extra: r[3] || "", key: fold(r[0]), alt: fold(r[4] || "") };
          });
          return data;
        });
    }
    return loading;
  }
  function score(item, q, words) {
    var k = item.key;
    if (k === q) return 0;
    if (k.indexOf(q) === 0) return 1;
    if ((" " + k).indexOf(" " + q) !== -1) return 2;
    if (item.alt && item.alt.indexOf(q) !== -1) return 3;
    for (var i = 0; i < words.length; i++) {
      if (k.indexOf(words[i]) === -1 && item.alt.indexOf(words[i]) === -1) return -1;
    }
    return 4;
  }
  function search(q, limit) {
    q = fold(q.trim());
    if (q.length < 2) return [];
    var words = q.split(/\s+/), hits = [];
    for (var i = 0; i < data.length; i++) {
      var s = score(data[i], q, words);
      if (s >= 0) hits.push([s, data[i].title.length, data[i]]);
    }
    hits.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return hits.slice(0, limit).map(function (h) { return h[2]; });
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function row(item) {
    return '<a href="' + esc(item.url) + '"><span class="kind">' + esc(item.kind) + '</span><span class="t">' +
      esc(item.title) + "</span>" + (item.extra ? '<span class="x">' + esc(item.extra) + "</span>" : "") + "</a>";
  }

  document.querySelectorAll("[data-search]").forEach(function (input) {
    var form = input.closest("form");
    var box = form.querySelector("[data-results]");
    var full = input.hasAttribute("data-full");
    var fullBox = document.querySelector("[data-full-results]");
    var sel = -1;

    function render() {
      load().then(function () {
        var q = input.value;
        if (full && fullBox) {
          var all = search(q, 200);
          fullBox.innerHTML = q.trim().length < 2 ? "" :
            (all.length ? all.map(row).join("") : '<p class="muted">Nothing matches “' + esc(q) + '”.</p>');
          return;
        }
        if (!box) return;
        var res = search(q, 12);
        sel = -1;
        if (q.trim().length < 2) { box.hidden = true; return; }
        box.innerHTML = res.length ? res.map(row).join("") : '<div class="none">No matches</div>';
        box.hidden = false;
      });
    }
    input.addEventListener("focus", load, { once: true });
    input.addEventListener("input", render);
    input.addEventListener("keydown", function (ev) {
      if (!box || box.hidden) return;
      var links = box.querySelectorAll("a");
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        sel = Math.max(-1, Math.min(links.length - 1, sel + (ev.key === "ArrowDown" ? 1 : -1)));
        links.forEach(function (a, i) { a.setAttribute("aria-selected", i === sel ? "true" : "false"); });
      } else if (ev.key === "Enter" && sel >= 0 && links[sel]) {
        ev.preventDefault();
        location.href = links[sel].href;
      } else if (ev.key === "Escape") {
        box.hidden = true;
      }
    });
    document.addEventListener("click", function (ev) { if (box && !form.contains(ev.target)) box.hidden = true; });

    if (full) {
      var q = new URLSearchParams(location.search).get("q") || "";
      input.value = q;
      if (q) render();
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        history.replaceState(null, "", "?q=" + encodeURIComponent(input.value));
        render();
      });
    }
  });
})();
