/*
 * Study page (/study/): contest countdown, flashcards due, practice-test progress and
 * "Pick up where you left off". Everything comes from this browser's saved progress
 * (and, for signed-in visitors, their account: auth.js loads it before litcritReady).
 */
(window.litcritReady || Promise.resolve()).then(function () {
  var root = document.querySelector("[data-study]");
  if (!root) return;
  var cfg = JSON.parse(root.getAttribute("data-study"));
  function load(k) { try { return JSON.parse(localStorage.getItem(k)) || {}; } catch (e) { return {}; } }
  function $(sel) { return document.querySelector(sel); }
  function plural(n, w) { return n.toLocaleString() + " " + w + (n === 1 ? "" : "s"); }
  function dayNum(d) { return Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 864e5); }
  var today = dayNum(new Date());
  var base = window.SITE_BASE || "/";

  // ---- guest note
  var guest = $("[data-guest]");
  if (guest) guest.hidden = !!window.litcritUser;

  // ---- countdown to the next contest date
  var upcoming = cfg.dates.map(function (d) {
    var p = d[1].split("-"), when = new Date(+p[0], +p[1] - 1, +p[2]);
    return { name: d[0], when: when, days: dayNum(when) - today };
  }).filter(function (d) { return d.days >= 0; });
  var cd = $("[data-countdown]");
  if (!upcoming.length) { cd.hidden = true; }
  else {
    var next = upcoming[0];
    var fmt = function (d, long) {
      return d.toLocaleDateString(undefined, long ? { weekday: "short", month: "short", day: "numeric" } : { month: "short", day: "numeric" });
    };
    $("[data-cd-big]").textContent = next.days === 0 ? "Today" : plural(next.days, "day");
    $("[data-cd-sub]").textContent = next.name + " · " + fmt(next.when, true);
    $("[data-cd-list]").innerHTML = upcoming.slice(1).map(function (d) {
      return "<li><span>" + d.name + "</span><span>" + fmt(d.when) + "</span></li>";
    }).join("");
  }

  // ---- flashcards: filled in by flashcards.js (Today’s flashcards tile)

  // ---- practice tests
  var scores = load("litcrit-test-scores-v1"), list = Object.keys(scores).map(function (k) { return scores[k]; });
  if (list.length) {
    $("[data-ts-big]").textContent = list.length + " of " + cfg.tests;
    var avg = Math.round(list.reduce(function (s, x) { return s + 100 * x.score / x.total; }, 0) / list.length);
    var best = Math.max.apply(null, list.map(function (x) { return x.score; }));
    $("[data-ts-sub]").textContent = "Average score " + avg + " · best " + best + ". " +
      "Scored out of 100.";
  }

  // ---- the last practice test answered but not yet scored (saved by quiz.js)
  var last = load("litcrit-last-v1"), resume = $("[data-resume]");
  if (last.p && !scores[last.p] && last.a > 0) {
    resume.href = last.p;
    $("[data-resume-title]").textContent = last.t || "Your practice test";
    $("[data-resume-sub]").textContent = last.a + " of " + last.n + " answered · not scored yet";
    resume.hidden = false;
  }
});
