/*
 * Timed mock test.
 *
 * Practice test pages: open with ?mock=1 to get the start screen. "Start the clock" clears any
 * earlier answers on the test and starts a 90-minute countdown. At 15 minutes left a warning
 * appears; at 0:00 the answers lock. The clock follows real time, so it keeps running if the
 * student leaves or reloads the page.
 *
 * Attempts: every press of "Start the clock" begins a new numbered attempt on that test. An attempt
 * ends when the student scores the test or presses Stop. "Clear my answers" during a mock test only
 * clears the answers: the clock keeps running and the attempt goes on (the attempt counts its clears).
 * Running out of time doesn't end the attempt: it stays open, locked, until it is scored or stopped.
 *
 * Essay (Part 4): when the test has an essay prompt, the start screen offers "Include the essay". As at the
 * contest, the essay must be finished within the same 90 minutes (ESSAY_EXTRA = 0). The essay section ([data-mock-essay]) appears after the questions with the editor from
 * essay.js, saved per attempt in litcrit-mock-essays-v1 under the attempt's ID. It locks with the answers when
 * time runs out, and when the attempt ends.
 *
 * Storage (synced to the student's account by auth.js):
 *   litcrit-mock-v1           { "/tests/<slug>/": {id, n, start, dur, warnSeen} }   the clock running on each test
 *   litcrit-mock-attempts-v1  { "<path>@<start>": {id, p, n, start, end, dur, used, how, answered, total, timeUp, clears, score, points, essay, essayWords} }
 *     how: "running" | "scored" | "stopped" ("cleared" on attempts saved before Nov 13, 2026)
 *
 * /study/mock/ (the chooser, [data-mock-pick]): pick a test, or let the site pick one not yet tried.
 */
function litcritMock(fn) {
  // Wait for every deferred script (quiz.js must set up the test first), then for saved progress (auth.js).
  var go = function () { (window.litcritReady || Promise.resolve()).then(fn); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
}
litcritMock(function () {
  var KEY = "litcrit-mock-v1", ATT = "litcrit-mock-attempts-v1", SCORES = "litcrit-test-scores-v1";
  var DUR = 90 * 60 * 1000, WARN = 15 * 60 * 1000;
  var ESSAY_EXTRA = 0;                // the essay gets no extra time: it is written within the same 90 minutes
  function load(key) { try { return JSON.parse(localStorage.getItem(key)) || {}; } catch (e) { return {}; } }
  function store(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) {} }
  function clock(ms) {
    var s = Math.max(0, Math.ceil(ms / 1000)), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
    return (h ? h + ":" + (m < 10 ? "0" : "") : "") + m + ":" + (r < 10 ? "0" : "") + r;
  }
  function words(ms) {
    var m = Math.round(ms / 60000), h = Math.floor(m / 60), r = m % 60;
    var hs = h ? h + " hour" + (h === 1 ? "" : "s") : "", rs = r ? r + " minute" + (r === 1 ? "" : "s") : "";
    return [hs, rs].filter(Boolean).join(" ") || "0 minutes";
  }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function attemptsFor(path) {
    var all = load(ATT);
    return Object.keys(all).map(function (k) { return all[k]; })
      .filter(function (a) { return a && a.p === path; })
      .sort(function (a, b) { return (a.n || 0) - (b.n || 0) || a.start - b.start; });
  }

  // ---------------------------------------------------------------- chooser page
  var picker = document.querySelector("[data-mock-pick]");
  if (picker) {
    var sel = picker.querySelector("select"), go = picker.querySelector("[data-mock-go]");
    var scores = load(SCORES);
    var pathOf = function (v) { return new URL(v, location.href).pathname; };
    sel.querySelectorAll("option[value]").forEach(function (o) {
      if (!o.value) return;
      var n = attemptsFor(pathOf(o.value)).length;
      if (n) o.textContent += " · " + n + " attempt" + (n === 1 ? "" : "s");
      else if (scores[pathOf(o.value)]) o.textContent += " · scored";
    });
    picker.querySelector("[data-mock-random]").addEventListener("click", function () {
      var opts = [].slice.call(sel.querySelectorAll("option[data-full]"));
      var fresh = opts.filter(function (o) { return !scores[pathOf(o.value)] && !attemptsFor(pathOf(o.value)).length; });
      var pool = fresh.length ? fresh : opts;
      if (!pool.length) return;
      sel.value = pool[Math.floor(Math.random() * pool.length)].value;
      sel.dispatchEvent(new Event("change"));
      sel.focus();
    });
    function sync() { go.classList.toggle("disabled", !sel.value); go.href = sel.value ? sel.value + "?mock=1" : "#"; }
    sel.addEventListener("change", sync);
    sync();
    return;
  }

  // ---------------------------------------------------------------- test pages
  var quiz = document.querySelector(".quiz");
  var bar = quiz && quiz.querySelector('[data-scorebar][data-test="1"]');
  if (!bar) return;
  var path = location.pathname;
  var params = new URLSearchParams(location.search);
  var s = load(KEY)[path] || null;
  var tick = null, warned = false, clockEl = null, noteEl = null, startBox = null, starting = false;
  var essayBox = document.querySelector("[data-mock-essay]"), essayEd = null;

  // Show this attempt's essay editor (each attempt has its own essay).
  function showEssay(id) {
    if (!essayBox || !window.litcritEssaySetup) return;
    var root = essayBox.querySelector("[data-essay]");
    if (essayEd && root.getAttribute("data-essay") === id) { essayBox.hidden = false; return; }
    if (essayEd) {   // a new attempt: start from a fresh copy of the editor
      var fresh = root.cloneNode(true);
      fresh.classList.remove("ready", "locked");
      fresh.querySelector("[data-essay-editor]").innerHTML = "";
      root.replaceWith(fresh); root = fresh;
    }
    root.setAttribute("data-essay", id);
    essayEd = window.litcritEssaySetup(root);
    essayBox.hidden = false;
  }
  function lockEssay(on) { if (essayEd) essayEd.lock(on); }

  function saveSession() { var all = load(KEY); if (s) all[path] = s; else delete all[path]; store(KEY, all); }
  function attempt() { return s ? load(ATT)[s.id] : null; }
  function saveAttempt(a) { var all = load(ATT); all[a.id || a.p + "@" + a.start] = a; store(ATT, all); }
  function left() { return s.start + s.dur - Date.now(); }
  function counts() {
    return { answered: quiz.querySelectorAll(".q:not([data-auto]).answered").length,
             total: quiz.querySelectorAll(".q:not([data-auto])").length };
  }
  function dropParam() {
    if (!params.has("mock")) return;
    params.delete("mock");
    var q = params.toString();
    history.replaceState(null, "", path + (q ? "?" + q : "") + location.hash);
  }

  // Close the current attempt (scored, cleared or stopped) and take the clock away.
  function closeAttempt(how, answered) {
    var a = attempt();
    if (a && a.how === "running") {
      var c = counts();
      a.how = how;
      a.end = Date.now();
      a.used = Math.min(a.dur, a.end - a.start);
      a.answered = answered == null ? c.answered : answered;
      a.total = c.total;
      if (left() <= 0) a.timeUp = true;
      if (a.essay && essayEd) a.essayWords = essayEd.words();
      if (how === "scored") {
        var sc = load(SCORES)[path];
        if (sc) { a.score = sc.score; a.points = sc.total; }
      }
      saveAttempt(a);
    }
    s = null; saveSession();
    if (tick) { clearInterval(tick); tick = null; }
    if (clockEl) { clockEl.remove(); clockEl = null; }
    document.body.classList.remove("mock-on");
    quiz.classList.remove("mock-locked");
    lockEssay(true);            // the essay stays on the page to read, but the attempt is over
    return a;
  }

  // Block new answers once time is up (runs before quiz.js's click handler).
  document.addEventListener("click", function (ev) {
    if (!quiz.classList.contains("mock-locked")) return;
    if (ev.target.closest(".quiz .choice")) { ev.preventDefault(); ev.stopPropagation(); }
  }, true);

  function note(html, kind) {
    if (!noteEl) {
      noteEl = document.createElement("div");
      noteEl.setAttribute("role", "status");
      quiz.insertAdjacentElement("beforebegin", noteEl);
    }
    noteEl.className = "mock-note" + (kind ? " " + kind : "");
    noteEl.innerHTML = html;
    noteEl.hidden = !html;
  }

  function buildClock() {
    clockEl = document.createElement("div");
    clockEl.className = "mock-clock";
    clockEl.innerHTML = '<span class="mc-label">Attempt ' + s.n + '</span> <strong class="mc-time" data-mc-time>' + clock(left()) +
      '</strong> <span class="mc-sub" data-mc-sub>left</span>' +
      (s.essay ? '<a class="mc-stop" href="#mock-essay">Essay</a>' : "") +
      '<button type="button" class="mc-stop" data-mc-stop>Stop</button>' +
      '<span class="sr-only" aria-live="assertive" data-mc-live></span>';
    document.body.appendChild(clockEl);
    document.body.classList.add("mock-on");
    clockEl.querySelector("[data-mc-stop]").addEventListener("click", function () {
      if (left() > 0 && !confirm("Stop this mock test attempt? Your answers stay on the page, but the clock goes away.")) return;
      var a = closeAttempt("stopped");
      note(a ? "Attempt " + a.n + " stopped" + (a.timeUp ? " after time ran out." : " after " + clock(a.used) + ".") +
           ' <a href="?mock=1" data-mock-again>Start a new attempt</a>' : "");
    });
  }

  function render() {
    var ms = left();
    if (!clockEl) buildClock();
    clockEl.querySelector("[data-mc-time]").textContent = clock(ms);
    if (ms <= 0) { timeUp(); return; }
    if (ms <= WARN) {
      clockEl.classList.add("warn");
      if (!warned) {
        warned = true;
        clockEl.querySelector("[data-mc-live]").textContent = "15 minutes left.";
        if (!s.warnSeen) {
          note('<strong>15 minutes left.</strong> Make sure every question has an answer: a blank scores 0, the same as a wrong guess. ' +
               '<button type="button" class="mock-dismiss" data-mock-dismiss>OK</button>', "warn");
          noteEl.querySelector("[data-mock-dismiss]").addEventListener("click", function () {
            if (s) { s.warnSeen = 1; saveSession(); }
            note("");
          });
        }
      }
    }
  }

  function timeUp() {
    if (tick) { clearInterval(tick); tick = null; }
    var a = attempt();
    if (a && !a.timeUp) { a.timeUp = true; saveAttempt(a); }
    clockEl.classList.add("over");
    clockEl.classList.remove("warn");
    clockEl.querySelector("[data-mc-time]").textContent = "Time’s up";
    clockEl.querySelector("[data-mc-sub]").textContent = "";
    clockEl.querySelector("[data-mc-stop]").textContent = "Close";
    clockEl.querySelector("[data-mc-live]").textContent = "Time’s up. Your answers are locked.";
    quiz.classList.add("mock-locked");
    lockEssay(true);
    var c = counts();
    note("<strong>Time’s up.</strong> Pencils down: your answers" + (s.essay ? " and essay are" : " are") + " locked. You answered " + c.answered + " of " + c.total +
         (s.essay && essayEd ? " and wrote " + essayEd.words() + " words" : "") +
         ". Press <b>Score test</b> in the score bar to see how you did.", "over");
  }

  // Scoring the test ends the attempt and records how long it took.
  new MutationObserver(function () {
    if (!s || !quiz.classList.contains("scored")) return;
    var a = closeAttempt("scored");
    if (!a) return;
    note("<strong>Attempt " + a.n + " finished</strong> in " + clock(a.used) +
         (a.used < a.dur ? ", with " + words(a.dur - a.used) + " to spare." : ", using the full " + words(a.dur) + ".") +
         (a.essay ? " Your essay (" + (a.essayWords || 0) + " words) is saved with this attempt." : "") +
         ' <a href="?mock=1" data-mock-again>Start a new attempt</a>', "done");
  }).observe(quiz, { attributes: true, attributeFilter: ["class"] });

  // "Clear my answers" during a mock test clears the answers only: the clock and the attempt carry on.
  quiz.addEventListener("litcrit:cleared", function () {
    if (starting || !s) return;
    var a = attempt();
    if (a && a.how === "running") { a.clears = (a.clears || 0) + 1; saveAttempt(a); }
  });

  function run() {
    dropParam();
    if (s.essay) showEssay(s.id);
    warned = left() <= WARN && !!s.warnSeen;
    render();
    if (left() > 0) tick = setInterval(render, 1000);
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden && tick) render(); });

  function historyHtml(list) {
    if (!list.length) return "";
    var rows = list.map(function (a) {
      var when = new Date(a.start).toLocaleDateString(undefined, { month: "short", day: "numeric" });
      var after = a.timeUp ? "time ran out" : clock(a.used);
      var what = a.how === "scored"
        ? (a.score != null ? "scored <b>" + a.score + "</b> / " + a.points : "scored") + (a.timeUp ? " after time ran out" : " in " + clock(a.used))
        : a.how === "cleared" ? "answers cleared after " + after + " (" + (a.answered || 0) + " answered)"
        : a.how === "stopped" ? "stopped after " + after + " (" + (a.answered || 0) + " answered)"
        : "in progress";
      if (a.essay) what += " · essay" + (a.how === "running" ? "" : ": " + (a.essayWords || 0) + " words");
      if (a.clears) what += " · answers cleared " + (a.clears === 1 ? "once" : a.clears + " times");
      return "<li>Attempt " + a.n + " · " + when + " · " + what + "</li>";
    }).join("");
    return '<div class="mock-history"><p class="eyebrow-sm">Your attempts on this test</p><ul class="plain">' + rows + "</ul></div>";
  }

  function startScreen() {
    if (startBox) return;
    var c = counts(), scored = quiz.classList.contains("scored");
    var past = attemptsFor(path), n = past.length + 1;
    var title = (document.querySelector("h1") || {}).textContent || "this test";
    startBox = document.createElement("section");
    startBox.className = "mock-start";
    startBox.setAttribute("aria-labelledby", "mock-start-h");
    startBox.innerHTML = '<p class="eyebrow-sm">Timed mock test' + (n > 1 ? " · attempt " + n : "") + "</p>" +
      '<h2 id="mock-start-h">' + esc(title) + "</h2>" +
      '<ul class="mock-rules">' +
      "<li><b>90 minutes</b> for all " + c.total + " questions" + (essayBox ? "" : ", like the real contest’s objective parts") + ".</li>" +
      "<li>A warning appears with <b>15 minutes left</b>.</li>" +
      "<li>No answers are shown until you score the test. At 0:00 your answers lock.</li>" +
      "<li>The clock keeps running if you leave or reload the page, so set aside the full time.</li>" +
      "<li>Each time you start the clock is a new attempt. Clearing your answers doesn’t stop the clock.</li></ul>" +
      (essayBox ? '<label class="mock-opt"><input type="checkbox" data-mock-withessay> <span><b>Include the essay</b> (Part 4). ' +
        "As at the contest, it gets no extra time: finish the questions and the essay within the 90 minutes. " +
        "The prompt and text appear after the questions.</span></label>" : "") +
      historyHtml(past) +
      ((c.answered || scored) ? '<p class="mock-clear">You’ve already answered ' + c.answered + " question" + (c.answered === 1 ? "" : "s") +
        " on this test" + (scored ? " and scored it" : "") + ". Starting clears " + (c.answered === 1 ? "that answer" : "those answers") +
        " so you begin fresh.</p>" : "") +
      '<div class="mock-actions"><button type="button" class="btn btn-study" data-mock-start>Start the clock' + (n > 1 ? ": attempt " + n : "") + "</button>" +
      '<a class="mock-cancel" href="' + path + '">Practice without a timer</a></div>';
    quiz.insertAdjacentElement("beforebegin", startBox);
    document.body.classList.add("mock-waiting");
    startBox.scrollIntoView({ block: "center" });
    startBox.querySelector(".mock-cancel").addEventListener("click", function (ev) {
      ev.preventDefault();
      dropParam();
      startBox.remove(); startBox = null;
      document.body.classList.remove("mock-waiting");
    });
    startBox.querySelector("[data-mock-start]").addEventListener("click", function () {
      starting = true;
      if (quiz.litcritClear) quiz.litcritClear();
      starting = false;
      note("");
      var now = Date.now(), num = attemptsFor(path).length + 1;
      var cb = startBox.querySelector("[data-mock-withessay]"), withEssay = !!(cb && cb.checked);
      var dur = DUR + (withEssay ? ESSAY_EXTRA : 0);
      s = { id: path + "@" + now, n: num, start: now, dur: dur, essay: withEssay ? 1 : 0 };
      saveSession();
      saveAttempt({ id: s.id, p: path, n: num, start: now, dur: dur, how: "running", total: counts().total, essay: withEssay ? 1 : 0 });
      if (!withEssay && essayBox) essayBox.hidden = true;
      startBox.remove(); startBox = null;
      document.body.classList.remove("mock-waiting");
      quiz.scrollIntoView({ block: "start" });
      run();
    });
  }

  // "Start a new attempt" links in notes: show the start screen without reloading.
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest("[data-mock-again]")) return;
    ev.preventDefault();
    note("");
    startScreen();
  });

  var open = attempt();
  if (s && open && open.how === "running") run();   // an attempt in progress, or one whose time ran out
  else {
    if (s) { s = null; saveSession(); }               // a leftover clock with no open attempt
    if (params.has("mock")) startScreen();
  }
});
