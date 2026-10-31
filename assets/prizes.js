(function () {
  var form = document.querySelector("[data-prize-filters]");
  if (!form) return;
  form.hidden = false;

  var CONTESTS = ["Invitational A", "Invitational B", "District", "Region", "State"];
  var f = form.elements;
  var status = form.querySelector("[data-shown]");
  var natWrap = form.querySelector("[data-nat-wrap]");
  var workSort = form.querySelector("[data-pulitzer-only]");

  function fold(s) {
    return (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function activePanel() {
    var panels = document.querySelectorAll(".tabpanel");
    for (var i = 0; i < panels.length; i++) if (!panels[i].hidden) return panels[i];
    return panels[0];
  }
  function rowsOf(panel) {
    return Array.prototype.slice.call(panel.querySelectorAll("li[data-year]"));
  }
  function fillSelect(select, values, keep) {
    var first = select.options[0].outerHTML;
    select.innerHTML = first + values.map(function (v) {
      return '<option value="' + v.replace(/"/g, "&quot;") + '">' + v.replace(/</g, "&lt;") + "</option>";
    }).join("");
    select.value = values.indexOf(keep) >= 0 ? keep : "";
  }

  // Rebuild the choices that depend on which prize tab is open.
  function setupPanel() {
    var panel = activePanel(), rows = rowsOf(panel);
    var nats = {}, tested = {}, allTests = false;
    rows.forEach(function (r) {
      (r.dataset.nat || "").split("|").forEach(function (n) { if (n) nats[n] = 1; });
      (r.dataset.tested || "").split("|").forEach(function (t) {
        if (t === "All Tests") allTests = true; else if (t) tested[t] = 1;
      });
    });
    var contestList = allTests ? CONTESTS.slice() : CONTESTS.filter(function (c) { return tested[c]; });
    Object.keys(tested).forEach(function (t) { if (contestList.indexOf(t) < 0) contestList.push(t); });
    fillSelect(f.tested, contestList, f.tested.value);
    f.tested.parentNode.hidden = contestList.length === 0;
    var natList = Object.keys(nats).sort();
    fillSelect(f.nat, natList, f.nat.value);
    natWrap.hidden = natList.length < 2;
    var pulitzer = panel.querySelector("ul").dataset.kind === "pulitzer";
    workSort.hidden = workSort.disabled = !pulitzer;
    if (!pulitzer && f.sort.value === "work") f.sort.value = "new";
  }

  function apply(save) {
    var panel = activePanel(), list = panel.querySelector("ul"), rows = rowsOf(panel);
    var q = fold(f.q.value.trim()), tested = f.tested.value, nat = f.nat.value;
    var from = parseInt(f.from.value, 10), to = parseInt(f.to.value, 10);
    var hideNone = f.hidenone.checked, sort = f.sort.value, shown = 0;

    rows.forEach(function (r) {
      var y = parseInt(r.dataset.year, 10), none = r.hasAttribute("data-none");
      var t = (r.dataset.tested || "").split("|");
      var ok = true;
      if (q && (none || r.dataset.text.indexOf(q) < 0)) ok = false;
      if (tested && t.indexOf(tested) < 0 && t.indexOf("All Tests") < 0) ok = false;
      if (nat && (r.dataset.nat || "").split("|").indexOf(nat) < 0) ok = false;
      if (!isNaN(from) && y < from) ok = false;
      if (!isNaN(to) && y > to) ok = false;
      if (hideNone && none) ok = false;
      r.hidden = !ok;
      if (ok) shown++;
    });

    var key = { author: "author", work: "work" }[sort];
    rows.sort(function (a, b) {
      var ya = +a.dataset.year, yb = +b.dataset.year;
      if (key) {
        var ka = a.dataset[key], kb = b.dataset[key];
        if (!ka !== !kb) return ka ? -1 : 1;           // "No Award" rows go last
        return ka < kb ? -1 : ka > kb ? 1 : yb - ya;
      }
      return sort === "old" ? ya - yb : yb - ya;
    });
    rows.forEach(function (r) { list.appendChild(r); });

    panel.querySelector(".empty").hidden = shown > 0;
    status.textContent = "Showing " + shown + " of " + rows.length;

    if (save) {
      var params = new URLSearchParams();
      ["q", "tested", "nat", "from", "to", "sort"].forEach(function (k) {
        if (f[k].value && !(k === "sort" && f[k].value === "new")) params.set(k, f[k].value);
      });
      if (hideNone) params.set("hidenone", "1");
      var qs = params.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    }
  }

  // Restore filters from the address, so a filtered view can be shared.
  var params = new URLSearchParams(location.search);
  ["q", "from", "to", "sort"].forEach(function (k) { if (params.get(k)) f[k].value = params.get(k); });
  f.hidenone.checked = params.get("hidenone") === "1";
  setupPanel();
  if (params.get("tested")) f.tested.value = params.get("tested");
  if (params.get("nat")) f.nat.value = params.get("nat");
  apply(false);

  form.addEventListener("input", function () { apply(true); });
  form.addEventListener("change", function () { apply(true); });
  form.querySelector("[data-reset]").addEventListener("click", function () {
    form.reset();
    apply(true);
  });
  document.querySelectorAll('.tabs [role="tab"]').forEach(function (t) {
    t.addEventListener("click", function () { setTimeout(function () { setupPanel(); apply(true); }, 0); });
    t.addEventListener("keydown", function () { setTimeout(function () { setupPanel(); apply(true); }, 0); });
  });
})();
