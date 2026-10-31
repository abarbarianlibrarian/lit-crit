/*
 * Practice questions, test-style:
 *   - picking a choice only selects it; it can be changed until "Confirm answer" is pressed;
 *   - a confirmed question locks and collapses to a one-line summary (click to expand);
 *   - nothing is graded and no score is shown until every question in the set is confirmed,
 *     then every question is marked right or wrong, its links appear, and the score bar shows the score.
 * Part 1 questions are worth 1 point, Parts 2 and 3 are worth 2. Redacted questions score automatically.
 * Confirmed answers are remembered in this browser (localStorage) on every page they appear.
 */
(function () {
  var quizzes = document.querySelectorAll(".quiz");
  if (!quizzes.length) return;
  document.documentElement.classList.add("quiz-ready");

  // ---- remembering answers
  var KEY = "litcrit-answers-v1";
  function loadSaved() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function saveAnswer(id, letter) {
    try { var all = loadSaved(); all[id] = letter; localStorage.setItem(KEY, JSON.stringify(all)); } catch (e) {}
  }
  function forget(ids) {
    try {
      var all = loadSaved();
      ids.forEach(function (id) { delete all[id]; });
      localStorage.setItem(KEY, JSON.stringify(all));
    } catch (e) {}
  }

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
  function choiceText(q, letter) {
    var b = q.querySelector('.choice[data-letter="' + letter + '"] .ctext');
    return b ? b.textContent : "";
  }

  // ---- per-question setup: confirm button and the collapsed summary line
  function prepare(q) {
    if (q.hasAttribute("data-auto") || q.querySelector(".confirm")) return;
    var list = q.querySelector(".choices");
    if (!list) return;
    var confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "confirm";
    confirm.textContent = "Confirm answer";
    confirm.disabled = true;
    list.insertAdjacentElement("afterend", confirm);
    var sum = document.createElement("button");
    sum.type = "button";
    sum.className = "qsum";
    sum.setAttribute("aria-expanded", "false");
    q.querySelector(".qbody").insertAdjacentElement("afterbegin", sum);
  }

  function select(q, letter) {
    q.querySelectorAll(".choice").forEach(function (b) {
      var on = b.getAttribute("data-letter") === letter;
      b.classList.toggle("selected", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    q.setAttribute("data-selected", letter);
    q.querySelector(".confirm").disabled = false;
  }

  function summary(q) {
    var sum = q.querySelector(".qsum");
    if (!sum) return;
    var letter = q.getAttribute("data-answer");
    var prompt = q.querySelector(".prompt").textContent.replace(/\s+/g, " ").trim();
    if (prompt.length > 110) prompt = prompt.slice(0, 107).replace(/\s+\S*$/, "") + "…";
    var num = q.querySelector(".qnum").textContent.trim();
    var mark = "";
    if (q.classList.contains("graded")) mark = q.classList.contains("got-it") ? "✓" : "✗";
    sum.innerHTML =
      (num ? '<span class="qs-num">' + num + "</span>" : "") +
      '<span class="qs-prompt"></span>' +
      '<span class="qs-answer">Your answer: <strong>' + letter + ".</strong> <span></span></span>" +
      (mark ? '<span class="qs-mark" aria-label="' + (mark === "✓" ? "correct" : "incorrect") + '">' + mark + "</span>" : "") +
      '<span class="qs-toggle" aria-hidden="true"></span>';
    sum.querySelector(".qs-prompt").textContent = prompt;
    sum.querySelector(".qs-answer span").textContent = choiceText(q, letter);
  }

  function confirmAnswer(q, letter, restoring) {
    q.setAttribute("data-answer", letter);
    q.classList.add("answered", "collapsed");
    q.classList.remove("expanded");
    q.querySelectorAll(".choice").forEach(function (b) {
      var on = b.getAttribute("data-letter") === letter;
      b.classList.toggle("selected", on);
      b.classList.toggle("picked", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.disabled = true;
    });
    var c = q.querySelector(".confirm");
    if (c) c.hidden = true;
    summary(q);
    if (!restoring) saveAnswer(q.getAttribute("data-qid"), letter);
  }

  function grade(q) {
    if (q.hasAttribute("data-auto") || !q.classList.contains("answered")) return;
    var picked = q.getAttribute("data-answer"), correct = correctOf(q);
    var right = correct.indexOf(picked) >= 0;
    q.classList.add("graded", right ? "got-it" : "missed");
    q.querySelectorAll(".choice").forEach(function (b) {
      var letter = b.getAttribute("data-letter");
      var isRight = correct.indexOf(letter) >= 0;
      b.classList.add(isRight ? "right" : "wrong");
      b.querySelector(".cmark").textContent = isRight ? "✓" : "✗";
      b.setAttribute("aria-label", letter + ". " + b.querySelector(".ctext").textContent +
        (isRight ? " (correct answer)" : " (incorrect)") + (letter === picked ? ", your choice" : ""));
    });
    var p = points(q), word = p === 1 ? " point" : " points";
    q.querySelector(".qresult").innerHTML = right
      ? "<strong>Correct.</strong> +" + p + word
      : "<strong>Not quite.</strong> The answer is " + correct.join(", ") + ". 0 of " + p + word;
    summary(q);
  }

  function update(quiz) {
    var bar = quiz.querySelector("[data-scorebar]");
    var qs = quiz.querySelectorAll(".q");
    var total = 0, earned = 0, lost = 0, answered = 0, right = 0, graded = 0, confirmed = 0;
    qs.forEach(function (q) {
      var p = points(q);
      total += p;
      if (q.hasAttribute("data-auto")) { earned += p; answered++; return; }
      if (!q.classList.contains("answered")) return;
      answered++; confirmed++;
      if (q.classList.contains("graded")) {
        graded++;
        if (q.classList.contains("got-it")) { earned += p; right++; } else lost += p;
      }
    });
    var done = answered === qs.length;
    if (done && !quiz.classList.contains("revealed")) {
      quiz.classList.add("revealed");
      qs.forEach(grade);
      return update(quiz);
    }
    if (!bar) return;
    bar.classList.toggle("revealed", done);
    bar.classList.toggle("done", done);
    bar.querySelector("[data-sb-score]").textContent = earned;
    bar.querySelector("[data-sb-answered]").textContent = done
      ? "All " + qs.length + " answered"
      : answered + " of " + qs.length + " answered · your score appears when every question is confirmed";
    bar.querySelector("[data-sb-acc]").textContent = done && graded
      ? right + " of " + graded + " correct (" + Math.round(100 * right / graded) + "%)" : "";
    bar.querySelector("[data-sb-right]").style.width = (100 * (done ? earned : answered / qs.length * total) / total) + "%";
    bar.querySelector("[data-sb-wrong]").style.width = (done ? 100 * lost / total : 0) + "%";
    bar.querySelector("[data-sb-clear]").hidden = confirmed === 0;
  }

  function clearQuiz(quiz) {
    var ids = [];
    quiz.querySelectorAll(".q.answered").forEach(function (q) {
      ids.push(q.getAttribute("data-qid"));
      q.classList.remove("answered", "graded", "got-it", "missed", "collapsed", "expanded");
      q.removeAttribute("data-answer");
      q.removeAttribute("data-selected");
      q.querySelector(".qresult").innerHTML = "";
      q.querySelectorAll(".choice").forEach(function (b) {
        b.classList.remove("right", "wrong", "picked", "selected");
        b.disabled = false;
        b.setAttribute("aria-pressed", "false");
        b.removeAttribute("aria-label");
        b.querySelector(".cmark").textContent = "";
      });
      var c = q.querySelector(".confirm");
      if (c) { c.hidden = false; c.disabled = true; }
      var s = q.querySelector(".qsum");
      if (s) s.innerHTML = "";
    });
    quiz.classList.remove("revealed");
    forget(ids);
    update(quiz);
  }

  // ---- start up: prepare questions and restore remembered answers
  var saved = loadSaved();
  quizzes.forEach(function (quiz) {
    quiz.querySelectorAll(".q").forEach(prepare);
    quiz.querySelectorAll(".q:not([data-auto])").forEach(function (q) {
      var letter = saved[q.getAttribute("data-qid")];
      if (letter && q.querySelector('.choice[data-letter="' + letter + '"]')) confirmAnswer(q, letter, true);
    });
    var bar = quiz.querySelector("[data-scorebar]");
    if (bar) {
      bar.hidden = false;
      bar.querySelector("[data-sb-clear]").addEventListener("click", function () {
        if (confirm("Clear your answers to the questions on this page? You can then answer them again.")) clearQuiz(quiz);
      });
    }
    update(quiz);
  });

  document.addEventListener("click", function (ev) {
    var choice = ev.target.closest(".choice");
    if (choice) {
      var q = choice.closest(".q");
      if (!q.classList.contains("answered")) select(q, choice.getAttribute("data-letter"));
      return;
    }
    var conf = ev.target.closest(".confirm");
    if (conf) {
      var cq = conf.closest(".q"), letter = cq.getAttribute("data-selected");
      if (letter && !cq.classList.contains("answered")) {
        confirmAnswer(cq, letter, false);
        update(cq.closest(".quiz"));
        cq.querySelector(".qsum").focus();
      }
      return;
    }
    var sum = ev.target.closest(".qsum");
    if (sum) {
      var sq = sum.closest(".q");
      var open = sq.classList.toggle("expanded");
      sq.classList.toggle("collapsed", !open);
      sum.setAttribute("aria-expanded", open ? "true" : "false");
    }
  });
})();
