/*
 * Search, filter and sort for a section's listing page.
 * The page provides <div data-catalog data-src="…json" data-config='{…}'>.
 * Each row: n name, u link, i title style ("i" italic / "q" quoted), s subtitle,
 * l [[label, [[text, url, style], …]], …] linked lists, m right-hand note,
 * f {filterKey: [values]}, k {sortKey: value}, x search text, id anchor, ext external link.
 */
(function () {
  var root = document.querySelector("[data-catalog]");
  if (!root) return;
  var cfg = JSON.parse(root.getAttribute("data-config"));
  var PAGE = 150;
  var rows = [], shownLimit = PAGE, pendingId = null;

  function fold(s) {
    return (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function title(text, style) {
    var t = esc(text);
    return style === "i" ? "<i>" + t + "</i>" : style === "q" ? "“" + t + "”" : t;
  }
  function link(text, url, style, ext) {
    if (!url) return title(text, style);
    return '<a href="' + esc(url) + '"' + (ext ? ' target="_blank" rel="noopener"' : "") + ">" +
      title(text, style) + (ext ? " ↗" : "") + "</a>";
  }

  // ---- controls
  var form = document.createElement("form");
  form.className = "filters";
  form.setAttribute("role", "search");
  form.onsubmit = function () { return false; };
  var html = '<label class="f-search"><span>Search</span><input type="search" name="q" placeholder="' +
    esc(cfg.placeholder || "Search") + '"></label>';
  (cfg.filters || []).forEach(function (f) {
    html += '<label data-filter="' + f.key + '"><span>' + esc(f.label) + '</span><select name="f_' + f.key +
      '"><option value="">' + esc(f.all || "All") + "</option></select></label>";
  });
  if (cfg.range) {
    html += '<label class="f-year"><span>' + esc(cfg.range.label) + ' from</span><input type="number" name="from" inputmode="numeric"></label>' +
      '<label class="f-year"><span>to</span><input type="number" name="to" inputmode="numeric"></label>';
  }
  html += '<label><span>Sort</span><select name="sort">' + cfg.sorts.map(function (s, i) {
    return '<option value="' + i + '">' + esc(s.label) + "</option>";
  }).join("") + "</select></label>";
  (cfg.checks || []).forEach(function (c) {
    html += '<label class="f-check"><input type="checkbox" name="c_' + c.key + '"> ' + esc(c.label) + "</label>";
  });
  html += '<button type="button" class="f-toggle" data-toggle aria-expanded="false">Filters and sorting</button>';
  html += '<p class="f-status"><span data-shown>Loading…</span> <button type="button" data-reset>Clear filters</button></p>';
  form.innerHTML = html;
  var list = document.createElement("ul");
  list.className = "plain catalog " + (cfg.layout || "");
  var more = document.createElement("button");
  more.type = "button";
  more.className = "show-more";
  more.hidden = true;
  var empty = document.createElement("p");
  empty.className = "muted empty";
  empty.hidden = true;
  empty.textContent = "Nothing matches these filters.";
  var fallback = root.querySelector("[data-fallback]");
  root.insertBefore(form, root.firstChild);
  root.appendChild(list);
  root.appendChild(empty);
  root.appendChild(more);
  var el = form.elements;

  function fillFilters() {
    (cfg.filters || []).forEach(function (f) {
      var counts = {};
      rows.forEach(function (r) {
        ((r.f && r.f[f.key]) || []).forEach(function (v) { counts[v] = (counts[v] || 0) + 1; });
      });
      var values = Object.keys(counts);
      if (f.order === "desc") values.sort().reverse();
      else if (f.order === "count") values.sort(function (a, b) { return counts[b] - counts[a] || (a < b ? -1 : 1); });
      else values.sort(function (a, b) { return a.localeCompare(b); });
      var sel = el["f_" + f.key];
      sel.innerHTML = '<option value="">' + esc(f.all || "All") + "</option>" + values.map(function (v) {
        return '<option value="' + esc(v) + '">' + esc(v) + " (" + counts[v] + ")</option>";
      }).join("");
      form.querySelector('[data-filter="' + f.key + '"]').hidden = values.length < 2;
    });
  }

  function current() {
    var q = fold(el.q.value.trim());
    var words = q ? q.split(/\s+/) : [];
    var from = cfg.range ? parseInt(el.from.value, 10) : NaN;
    var to = cfg.range ? parseInt(el.to.value, 10) : NaN;
    var picks = (cfg.filters || []).map(function (f) { return [f.key, el["f_" + f.key].value]; })
      .filter(function (p) { return p[1]; });
    var checks = (cfg.checks || []).filter(function (c) { return el["c_" + c.key].checked; });
    var out = rows.filter(function (r) {
      for (var i = 0; i < words.length; i++) if (r.x.indexOf(words[i]) < 0) return false;
      for (var j = 0; j < picks.length; j++) {
        if (((r.f && r.f[picks[j][0]]) || []).indexOf(picks[j][1]) < 0) return false;
      }
      for (var c = 0; c < checks.length; c++) if (!(r.f && r.f[checks[c].key] && r.f[checks[c].key].length)) return false;
      if (!isNaN(from) || !isNaN(to)) {
        var y = r.k && r.k[cfg.range.key];
        if (y == null || y === "") return false;
        if (!isNaN(from) && y < from) return false;
        if (!isNaN(to) && y > to) return false;
      }
      return true;
    });
    var s = cfg.sorts[+el.sort.value] || cfg.sorts[0];
    var keys = s.keys || [s.key];
    out.sort(function (a, b) {
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i], desc = k.charAt(0) === "-";
        if (desc) k = k.slice(1);
        var va = a.k[k], vb = b.k[k];
        var na = va == null || va === "", nb = vb == null || vb === "";
        if (na !== nb) return na ? 1 : -1;             // blanks always last
        if (na) continue;
        if (va < vb) return desc ? 1 : -1;
        if (va > vb) return desc ? -1 : 1;
      }
      return 0;
    });
    return out;
  }

  function rowHtml(r) {
    var main = '<span class="ct">' + link(r.n, r.u, r.i, r.ext) + "</span>";
    if (r.s) main += ' <span class="cs">' + esc(r.s) + "</span>";
    if (r.l) {
      main += '<span class="cl">' + r.l.map(function (g) {
        return '<span class="cg"><span class="clabel">' + esc(g[0]) + "</span> " +
          (g[1].length ? g[1].map(function (x) { return link(x[0], x[1], x[2]); }).join(", ") : "—") + "</span>";
      }).join("") + "</span>";
    }
    return "<li" + (r.id ? ' id="' + esc(r.id) + '"' : "") + '><div class="cmain">' + main + "</div>" +
      (r.m ? '<span class="cm">' + esc(r.m) + "</span>" : "") + "</li>";
  }

  function render(save) {
    var out = current();
    if (pendingId) {
      for (var i = 0; i < out.length; i++) if (out[i].id === pendingId && i >= shownLimit) shownLimit = i + 1;
    }
    list.innerHTML = out.slice(0, shownLimit).map(rowHtml).join("");
    empty.hidden = out.length > 0;
    more.hidden = out.length <= shownLimit;
    more.textContent = "Show " + Math.min(PAGE, out.length - shownLimit) + " more";
    form.querySelector("[data-shown]").textContent =
      "Showing " + Math.min(out.length, shownLimit).toLocaleString() + " of " + out.length.toLocaleString() +
      (out.length !== rows.length ? " (" + rows.length.toLocaleString() + " in all)" : "");
    if (save) {
      var p = new URLSearchParams();
      Array.prototype.forEach.call(el, function (input) {
        if (!input.name) return;
        if (input.type === "checkbox") { if (input.checked) p.set(input.name, "1"); }
        else if (input.value && !(input.name === "sort" && input.value === "0")) p.set(input.name, input.value);
      });
      var qs = p.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    }
  }

  function restore() {
    var p = new URLSearchParams(location.search);
    Array.prototype.forEach.call(el, function (input) {
      if (!input.name || !p.has(input.name)) return;
      if (input.type === "checkbox") input.checked = p.get(input.name) === "1";
      else input.value = p.get(input.name);
    });
  }

  form.addEventListener("input", function () { shownLimit = PAGE; render(true); });
  form.addEventListener("change", function () { shownLimit = PAGE; render(true); });
  form.querySelector("[data-reset]").addEventListener("click", function () {
    form.reset(); shownLimit = PAGE; render(true);
  });
  more.addEventListener("click", function () { shownLimit += PAGE; render(false); });
  form.querySelector("[data-toggle]").addEventListener("click", function () {
    var open = form.classList.toggle("open");
    this.setAttribute("aria-expanded", open ? "true" : "false");
  });

  fetch(root.getAttribute("data-src"))
    .then(function (r) { return r.json(); })
    .then(function (data) {
      rows = data;
      fillFilters();
      restore();
      // A link to an anchor (e.g. a reading list year) must be on the page.
      if (location.hash) pendingId = decodeURIComponent(location.hash.slice(1));
      if (fallback) fallback.hidden = true;
      render(false);
      if (location.hash) {
        var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
        if (target) { target.classList.add("target"); target.scrollIntoView(); }
        pendingId = null;
      }
    })
    .catch(function () {
      form.querySelector("[data-shown]").textContent = "Couldn’t load the list.";
    });
})();
