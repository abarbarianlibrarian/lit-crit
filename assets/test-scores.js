/*
 * Tests page: shows this browser's score for each completed test, with a Reset button,
 * and a short summary above the list. Scores are saved by quiz.js when a test is scored.
 */
// Signed-in visitors: wait until their saved progress has been loaded (auth.js).
(window.litcritReady || Promise.resolve()).then(function () {
  var SCORES = "litcrit-test-scores-v1", ANSWERS = "litcrit-answers-v1", SCORED = "litcrit-scored-v1";
  function load(key) { try { return JSON.parse(localStorage.getItem(key)) || {}; } catch (e) { return {}; } }
  function store(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) {} }

  var root = document.querySelector("[data-catalog]");
  var summary = document.querySelector("[data-my-progress]");
  if (!root) return;

  function pathOf(href) {
    try { return new URL(href, location.href).pathname; } catch (e) { return href; }
  }

  function renderSummary(scores) {
    if (!summary) return;
    var list = Object.keys(scores).map(function (k) { return scores[k]; });
    if (!list.length) { summary.hidden = true; return; }
    var avg = Math.round(list.reduce(function (s, x) { return s + 100 * x.score / x.total; }, 0) / list.length);
    var best = Math.max.apply(null, list.map(function (x) { return x.score; }));
    summary.innerHTML = "<strong>Your progress</strong> " + list.length + " test" + (list.length === 1 ? "" : "s") +
      " completed · average score " + avg + " · best " + best +
      ' <span class="muted">(' + (window.litcritUser ? "saved to your account" : "saved in this browser") + ')</span>';
    summary.hidden = false;
  }

  function decorate() {
    var scores = load(SCORES);
    root.querySelectorAll("ul.catalog > li").forEach(function (li) {
      var link = li.querySelector(".ct a");
      if (!link) return;
      var path = pathOf(link.getAttribute("href"));
      var old = li.querySelector(".my-score");
      var entry = scores[path];
      if (!entry) { if (old) old.remove(); li.classList.remove("completed"); return; }
      if (old && old.getAttribute("data-for") === String(entry.when) + entry.score) return;
      if (old) old.remove();
      var box = document.createElement("span");
      box.className = "my-score";
      box.setAttribute("data-for", String(entry.when) + entry.score);
      box.innerHTML = '<span class="ms-score"><strong>' + entry.score + "</strong> / " + entry.total + "</span>" +
        '<span class="ms-acc">' + entry.right + " of " + entry.graded + " correct</span>" +
        '<button type="button" class="ms-reset">Reset</button>';
      box.querySelector(".ms-reset").addEventListener("click", function () {
        if (!confirm("Reset " + link.textContent + "? Your answers and score for it will be cleared.")) return;
        var all = load(SCORES), e = all[path];
        if (e) {
          var answers = load(ANSWERS);
          (e.qids || []).forEach(function (id) { delete answers[id]; });
          store(ANSWERS, answers);
          var scored = load(SCORED);
          delete scored[e.key || path + "#0"];
          store(SCORED, scored);
          delete all[path];
          store(SCORES, all);
        }
        decorate();
      });
      li.classList.add("completed");
      li.appendChild(box);
    });
    renderSummary(scores);
  }

  // The list is drawn (and redrawn on every filter change) by catalog.js.
  var observer = new MutationObserver(function () { observer.disconnect(); decorate(); observe(); });
  function observe() { observer.observe(root, { childList: true, subtree: true }); }
  window.addEventListener("pageshow", function () { observer.disconnect(); decorate(); observe(); });
  decorate();
  observe();
});
