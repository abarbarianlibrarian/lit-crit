/*
 * Practice questions: pick one answer per question (no second tries until the page is reloaded).
 * Each .quiz block has a score bar: Part 1 questions are worth 1 point, Parts 2 and 3 are worth 2.
 * Redacted questions, and any with no recorded answer, score their points automatically.
 */
(function () {
  var quizzes = document.querySelectorAll(".quiz");
  if (!quizzes.length) return;
  document.documentElement.classList.add("quiz-ready");

  // Keep the score bar just under the sticky site header.
  function setOffset() {
    var top = document.querySelector(".top");
    var sticky = top && getComputedStyle(top).position === "sticky";
    document.documentElement.style.setProperty("--quiz-top", (sticky ? top.offsetHeight : 0) + "px");
  }
  setOffset();
  window.addEventListener("resize", setOffset);

  function points(q) { return parseInt(q.getAttribute("data-points"), 10) || 1; }

  function update(quiz) {
    var bar = quiz.querySelector("[data-scorebar]");
    if (!bar) return;
    var qs = quiz.querySelectorAll(".q");
    var total = 0, earned = 0, lost = 0, answered = 0, right = 0, graded = 0;
    qs.forEach(function (q) {
      var p = points(q);
      total += p;
      if (q.hasAttribute("data-auto")) { earned += p; answered++; return; }
      if (!q.classList.contains("answered")) return;
      answered++; graded++;
      if (q.classList.contains("got-it")) { earned += p; right++; } else lost += p;
    });
    bar.querySelector("[data-sb-score]").textContent = earned;
    bar.querySelector("[data-sb-answered]").textContent = answered + " of " + qs.length + " answered";
    bar.querySelector("[data-sb-acc]").textContent = graded
      ? right + " of " + graded + " correct (" + Math.round(100 * right / graded) + "%)" : "";
    bar.querySelector("[data-sb-right]").style.width = (100 * earned / total) + "%";
    bar.querySelector("[data-sb-wrong]").style.width = (100 * lost / total) + "%";
    bar.classList.toggle("done", answered === qs.length);
  }

  function answer(q, picked) {
    var correct = (q.getAttribute("data-correct") || "").split("").filter(Boolean);
    var right = correct.indexOf(picked) >= 0;
    q.classList.add("answered", right ? "got-it" : "missed");
    q.querySelectorAll(".choice").forEach(function (b) {
      var letter = b.getAttribute("data-letter");
      var isRight = correct.indexOf(letter) >= 0;
      b.classList.add(isRight ? "right" : "wrong");
      if (letter === picked) b.classList.add("picked");
      b.setAttribute("aria-pressed", letter === picked ? "true" : "false");
      b.disabled = true;
      b.querySelector(".cmark").textContent = isRight ? "✓" : "✗";
      b.setAttribute("aria-label", letter + ". " + b.querySelector(".ctext").textContent +
        (isRight ? " (correct answer)" : " (incorrect)") + (letter === picked ? ", your choice" : ""));
    });
    var p = points(q), word = p === 1 ? " point" : " points";
    q.querySelector(".qresult").innerHTML = right
      ? "<strong>Correct.</strong> +" + p + word
      : "<strong>Not quite.</strong> The answer is " + correct.join(", ") + ". 0 of " + p + word;
    update(q.closest(".quiz"));
  }

  quizzes.forEach(function (quiz) {
    var bar = quiz.querySelector("[data-scorebar]");
    if (bar) bar.hidden = false;
    update(quiz);
  });

  document.addEventListener("click", function (ev) {
    var choice = ev.target.closest(".choice");
    if (!choice) return;
    var q = choice.closest(".q");
    if (!q.classList.contains("answered")) answer(q, choice.getAttribute("data-letter"));
  });
})();
