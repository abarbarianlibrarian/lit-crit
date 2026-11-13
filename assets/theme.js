/* Light and dark mode. The header button cycles Match device → Light → Dark.
   The choice is kept in localStorage (litcrit-theme-v1: "light" or "dark"; no value = match device)
   and applied as data-theme on <html> by a small script in each page's <head>, before the page draws. */
(function () {
  var KEY = "litcrit-theme-v1";
  var ORDER = ["auto", "light", "dark"];
  var NAMES = { auto: "match device", light: "light", dark: "dark" };
  var root = document.documentElement;

  function current() {
    var t = root.getAttribute("data-theme");
    return t === "light" || t === "dark" ? t : "auto";
  }
  function apply(t) {
    if (t === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", t);
    try { if (t === "auto") localStorage.removeItem(KEY); else localStorage.setItem(KEY, t); } catch (e) {}
    label();
  }
  function label() {
    var t = current(), next = ORDER[(ORDER.indexOf(t) + 1) % ORDER.length];
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      b.setAttribute("data-mode", t);
      var text = "Color theme: " + NAMES[t] + ". Switch to " + NAMES[next];
      b.setAttribute("aria-label", text);
      b.title = text;
    });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-theme-toggle]");
    if (!b) return;
    apply(ORDER[(ORDER.indexOf(current()) + 1) % ORDER.length]);
  });
  // Another tab changed the theme
  window.addEventListener("storage", function (e) {
    if (e.key !== KEY) return;
    var t = e.newValue === "light" || e.newValue === "dark" ? e.newValue : "auto";
    if (t === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", t);
    label();
  });
  label();
})();
