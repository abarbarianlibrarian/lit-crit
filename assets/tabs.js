(function () {
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tabs [role="tab"]'));
  if (!tabs.length) return;
  document.documentElement.classList.add("has-tabs");
  function show(id, focus) {
    var found = false;
    tabs.forEach(function (t) {
      var on = t.getAttribute("aria-controls") === id;
      found = found || on;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      var panel = document.getElementById(t.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
      if (on && focus) t.focus();
    });
    return found;
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function (ev) {
      ev.preventDefault();
      var id = t.getAttribute("aria-controls");
      show(id);
      history.replaceState(null, "", "#" + id);
    });
    t.addEventListener("keydown", function (ev) {
      var n = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
      if (!n) return;
      ev.preventDefault();
      var next = tabs[(i + n + tabs.length) % tabs.length];
      show(next.getAttribute("aria-controls"), true);
      history.replaceState(null, "", "#" + next.getAttribute("aria-controls"));
    });
  });
  var hash = decodeURIComponent(location.hash.slice(1));
  if (!hash || !show(hash)) show(tabs[0].getAttribute("aria-controls"));
})();
