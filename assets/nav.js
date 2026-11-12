/*
 * The Reference and Study menus at the top of every page.
 * Mouse: the menu opens on hover (CSS) and a click goes to the Reference or Study page.
 * Tap (touch screens): toggles the menu. Keyboard: Enter opens it, Tab moves through it, Escape closes it. Without JavaScript the menu names are plain links
 * to the Reference and Study pages.
 */
(function () {
  var dds = document.querySelectorAll("[data-dd]");
  if (!dds.length) return;
  document.documentElement.classList.add("nav-js");
  var hover = matchMedia("(hover: hover) and (pointer: fine)");
  function close(except) {
    dds.forEach(function (dd) {
      if (dd === except) return;
      dd.classList.remove("open");
      dd.querySelector(".ddbtn").setAttribute("aria-expanded", "false");
    });
  }
  dds.forEach(function (dd) {
    var btn = dd.querySelector(".ddbtn");
    btn.setAttribute("role", "button");
    btn.addEventListener("click", function (ev) {
      if (hover.matches && ev.detail > 0) return;   // mouse click: follow the link
      ev.preventDefault();
      var open = !dd.classList.contains("open");
      close(dd);
      dd.classList.toggle("open", open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) { var first = dd.querySelector(".menu a"); if (first && ev.detail === 0) first.focus(); }
    });
    // Leaving a menu with the mouse closes one opened by a click.
    dd.addEventListener("mouseleave", function () {
      if (hover.matches && dd.classList.contains("open")) {
        dd.classList.remove("open"); btn.setAttribute("aria-expanded", "false");
      }
    });
    dd.addEventListener("focusout", function (ev) {
      if (!dd.contains(ev.relatedTarget)) { dd.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
    });
  });
  document.addEventListener("click", function (ev) { if (!ev.target.closest("[data-dd]")) close(); });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var openDd = document.querySelector("[data-dd].open");
    if (openDd) { close(); openDd.querySelector(".ddbtn").focus(); }
  });
})();
