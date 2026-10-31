/*
 * Practice questions:
 *   - clicking a choice selects it; the selection can be changed freely;
 *   - the score bar's "Score test" button grades every question on the page at once:
 *     each choice is marked right or wrong, links appear, and the bar shows the score;
 *     after scoring, answers are locked until "Clear my answers";
 *   - unanswered questions score 0; redacted questions score their points automatically.
 * Part 1 questions are worth 1 point, Parts 2 and 3 are worth 2.
 * Selections, and whether a page has been scored, are remembered in this browser (localStorage).
 */
(function () {
  var quizzes = document.querySelectorAll(".quiz");
  if (!quizzes.length) return;
  document.documentElement.classList.add("quiz-ready");

  // ---- remembering answers and scored pages
  var KEY = "litcrit-answers-v1", SCORED = "litcrit-scored-v1", SCORES = "litcrit-test-scores-v1";
  function load(key) {
    try { return JSON.parse(localStorage.getItem(key)) || {}; } catch (e) { return {}; }
  }
  function store(key, obj) {
    try { localStorage.setItem(key, JSON.stringify(obj)); } catch (e) {}
  }
  function saveAnswer(id, letter) { var a = load(KEY); a[id] = letter; store(KEY, a); }
  function forget(ids) { var a = load(KEY); ids.forEach(function (id) { delete a[id]; }); store(KEY, a); }
  function quizKey(quiz, i) { return location.pathname + "#" + i; }
  function setScored(key, on) { var s = load(SCORED); if (on) s[key] = 1; else delete s[key]; store(SCORED, s); }

  // ---- keep the score bar just under the sticky site header
  function setOffset() {
    var top = document.querySelector(".top");
    var sticky = top && getComputedStyle(top).position === "sticky";
    document.documentElement.style.setProperty("--quiz-top", (sticky ? top.offsetHeight : 0) + "px");
  }
  setOffset();
  window.addEventListener("resize", setOffset);

  function points(q) { return parseInt(q.getAttribute("data-points"), 10) || 1; }
  function correctOf(q) { return (q.getAttribute("data-correct") || "").split("").filter(Boolean); }

  function select(q, letter, restoring) {
    q.querySelectorAll(".choice").forEach(function (b) {
      var on = b.getAttribute("data-letter") === letter;
      b.classList.toggle("selected", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    q.setAttribute("data-answer", letter);
    q.classList.add("answered");
    if (!restoring) saveAnswer(q.getAttribute("data-qid"), letter);
  }

  function grade(q) {
    if (q.hasAttribute("data-auto")) return;
    var picked = q.getAttribute("data-answer") || "", correct = correctOf(q);
    var right = !!picked && correct.indexOf(picked) >= 0;
    q.classList.add("graded", right ? "got-it" : "missed");
    q.querySelectorAll(".choice").forEach(function (b) {
      var letter = b.getAttribute("data-letter");
      var isRight = correct.indexOf(letter) >= 0;
      b.classList.add(isRight ? "right" : "wrong");
      if (letter === picked) b.classList.add("picked");
      b.disabled = true;
      b.querySelector(".cmark").textContent = isRight ? "✓" : "✗";
      b.setAttribute("aria-label", letter + ". " + b.querySelector(".ctext").textContent +
        (isRight ? " (correct answer)" : " (incorrect)") + (letter === picked ? ", your choice" : ""));
    });
    var p = points(q), word = p === 1 ? " point" : " points";
    q.querySelector(".qresult").innerHTML = right
      ? "<strong>Correct.</strong> +" + p + word
      : picked
        ? "<strong>Not quite.</strong> The answer is " + correct.join(", ") + ". 0 of " + p + word
        : "<strong>Not answered.</strong> The answer is " + correct.join(", ") + ". 0 of " + p + word;
  }

  function update(quiz) {
    var bar = quiz.querySelector("[data-scorebar]");
    if (!bar) return;
    var qs = quiz.querySelectorAll(".q");
    var scored = quiz.classList.contains("scored");
    var total = 0, earned = 0, lost = 0, answered = 0, right = 0, graded = 0;
    qs.forEach(function (q) {
      var p = points(q);
      total += p;
      if (q.hasAttribute("data-auto")) { earned += p; answered++; return; }
      if (q.classList.contains("answered")) answered++;
      if (q.classList.contains("graded")) {
        graded++;
        if (q.classList.contains("got-it")) { earned += p; right++; } else lost += p;
      }
    });
    bar.classList.toggle("revealed", scored);
    bar.classList.toggle("done", scored);
    bar.querySelector("[data-sb-score]").textContent = earned;
    bar.querySelector("[data-sb-answered]").textContent = answered + " of " + qs.length + " answered";
    bar.querySelector("[data-sb-acc]").textContent = scored && graded
      ? right + " of " + graded + " correct (" + Math.round(100 * right / graded) + "%)" : "";
    bar.querySelector("[data-sb-right]").style.width = (100 * (scored ? earned / total : answered / qs.length)) + "%";
    bar.querySelector("[data-sb-wrong]").style.width = (scored ? 100 * lost / total : 0) + "%";
    bar.querySelector("[data-sb-go]").hidden = scored;
    bar.querySelector("[data-sb-clear]").hidden = !scored && answered === quiz.querySelectorAll(".q[data-auto]").length;
  }

  // A scored test's result is kept for the Tests page (score and the questions to reset).
  function recordTest(quiz) {
    var bar = quiz.querySelector("[data-scorebar]");
    if (!bar || bar.getAttribute("data-test") !== "1") return;
    var earned = 0, total = 0, right = 0, graded = 0, qids = [];
    quiz.querySelectorAll(".q").forEach(function (q) {
      var p = points(q);
      total += p;
      if (q.hasAttribute("data-auto")) { earned += p; return; }
      qids.push(q.getAttribute("data-qid"));
      graded++;
      if (q.classList.contains("got-it")) { earned += p; right++; }
    });
    var all = load(SCORES), prev = all[location.pathname];
    all[location.pathname] = { score: earned, total: total, right: right, graded: graded, qids: qids,
                               key: quiz.getAttribute("data-key"), when: prev && prev.when || Date.now() };
    store(SCORES, all);
  }

  function scoreQuiz(quiz, restoring) {
    quiz.classList.add("scored");
    quiz.querySelectorAll(".q").forEach(grade);
    if (!restoring) setScored(quiz.getAttribute("data-key"), true);
    recordTest(quiz);
    update(quiz);
  }

  function clearQuiz(quiz) {
    var ids = [];
    quiz.querySelectorAll(".q:not([data-auto])").forEach(function (q) {
      if (q.classList.contains("answered")) ids.push(q.getAttribute("data-qid"));
      q.classList.remove("answered", "graded", "got-it", "missed");
      q.removeAttribute("data-answer");
      q.querySelector(".qresult").innerHTML = "";
      q.querySelectorAll(".choice").forEach(function (b) {
        b.classList.remove("right", "wrong", "picked", "selected");
        b.disabled = false;
        b.setAttribute("aria-pressed", "false");
        b.removeAttribute("aria-label");
        b.querySelector(".cmark").textContent = "";
      });
    });
    quiz.classList.remove("scored");
    setScored(quiz.getAttribute("data-key"), false);
    var scores = load(SCORES);
    if (scores[location.pathname] && scores[location.pathname].key === quiz.getAttribute("data-key")) {
      delete scores[location.pathname];
      store(SCORES, scores);
    }
    forget(ids);
    update(quiz);
  }

  // ---- start up
  var saved = load(KEY), scoredPages = load(SCORED);
  quizzes.forEach(function (quiz, i) {
    quiz.setAttribute("data-key", quizKey(quiz, i));
    quiz.querySelectorAll(".q:not([data-auto])").forEach(function (q) {
      var letter = saved[q.getAttribute("data-qid")];
      if (letter && q.querySelector('.choice[data-letter="' + letter + '"]')) select(q, letter, true);
    });
    var bar = quiz.querySelector("[data-scorebar]");
    if (bar) {
      var go = document.createElement("button");
      go.type = "button";
      go.className = "sb-go";
      go.setAttribute("data-sb-go", "");
      go.textContent = bar.getAttribute("data-test") === "1" ? "Score test" : "Score answers";
      bar.querySelector("[data-sb-clear]").insertAdjacentElement("beforebegin", go);
      go.addEventListener("click", function () {
        var left = quiz.querySelectorAll(".q:not([data-auto]):not(.answered)").length;
        if (left && !confirm(left + (left === 1 ? " question is" : " questions are") +
            " unanswered and will score 0. Score anyway?")) return;
        scoreQuiz(quiz, false);
      });
      bar.querySelector("[data-sb-clear]").addEventListener("click", function () {
        if (confirm("Clear your answers to the questions on this page? You can then answer them again.")) clearQuiz(quiz);
      });
      bar.hidden = false;
    }
    if (scoredPages[quiz.getAttribute("data-key")]) scoreQuiz(quiz, true);
    else update(quiz);
  });

  document.addEventListener("click", function (ev) {
    var choice = ev.target.closest(".choice");
    if (!choice) return;
    var q = choice.closest(".q"), quiz = q.closest(".quiz");
    if (quiz.classList.contains("scored")) return;
    select(q, choice.getAttribute("data-letter"), false);
    update(quiz);
  });
})();
