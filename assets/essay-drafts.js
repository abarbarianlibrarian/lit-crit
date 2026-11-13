/*
 * Essay prompts page: marks each prompt the student has written an essay for (word count and date),
 * with a short summary above the list. Essays are saved by essay.js.
 */
(window.litcritReady || Promise.resolve()).then(function () {
  var KEY = "litcrit-essays-v1";
  var root = document.querySelector("[data-catalog]");
  var summary = document.querySelector("[data-my-progress]");
  if (!root) return;
  function load() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function pathOf(href) { try { return new URL(href, location.href).pathname; } catch (e) { return href; } }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function decorate() {
    var all = load(), byPath = {};
    Object.keys(all).forEach(function (id) { if (all[id] && all[id].url) byPath[all[id].url] = all[id]; });
    root.querySelectorAll("ul.catalog > li").forEach(function (li) {
      var link = li.querySelector(".ct a");
      if (!link) return;
      var d = byPath[pathOf(link.getAttribute("href"))];
      var old = li.querySelector(".my-essay");
      var tag = d ? d.updated + ":" + d.words : "";
      if (old && old.getAttribute("data-for") === tag) return;
      if (old) old.remove();
      li.classList.toggle("completed", !!d);
      if (!d) return;
      var box = document.createElement("span");
      box.className = "my-essay";
      box.setAttribute("data-for", tag);
      var when = new Date(d.updated).toLocaleDateString([], { month: "short", day: "numeric" });
      box.innerHTML = '<a href="' + esc(link.getAttribute("href")) + '#my-essay">Your essay</a> · ' +
        (d.words || 0).toLocaleString() + " words · " + esc(when);
      li.appendChild(box);
    });
    if (!summary) return;
    var n = Object.keys(all).length;
    if (!n) { summary.hidden = true; return; }
    var words = Object.keys(all).reduce(function (s, id) { return s + (all[id].words || 0); }, 0);
    summary.innerHTML = "<strong>Your essays</strong> " + n + " written · " + words.toLocaleString() + " words in all" +
      ' <span class="muted">(' + (window.litcritUser ? "saved to your account" : "saved in this browser") + ")</span>";
    summary.hidden = false;
  }

  // The list is drawn (and redrawn on every filter change) by catalog.js.
  var observer = new MutationObserver(function () { observer.disconnect(); decorate(); observe(); });
  function observe() { observer.observe(root, { childList: true, subtree: true }); }
  window.addEventListener("pageshow", function () { observer.disconnect(); decorate(); observe(); });
  decorate();
  observe();
});
