(function () {
  var qs = document.querySelectorAll(".q[data-correct]");
  if (!qs.length) return;
  document.documentElement.classList.add("quiz-ready");

  function answer(q, picked) {
    var correct = (q.getAttribute("data-correct") || "").split("").filter(Boolean);
    if (!correct.length) {                     // no answer key recorded for this question
      q.classList.add("answered");
      q.querySelectorAll(".choice").forEach(function (b) {
        b.disabled = true;
        if (b.getAttribute("data-letter") === picked) b.classList.add("picked");
      });
      q.querySelector(".qresult").innerHTML = "No answer is recorded for this question. " +
        '<button type="button" class="retry">Try again</button>';
      return;
    }
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
    var result = q.querySelector(".qresult");
    result.innerHTML = (right ? "<strong>Correct.</strong>" :
      "<strong>Not quite.</strong> The answer is " + correct.join(", ") + ".") +
      ' <button type="button" class="retry">Try again</button>';
  }

  function reset(q) {
    q.classList.remove("answered", "got-it", "missed");
    q.querySelectorAll(".choice").forEach(function (b) {
      b.classList.remove("right", "wrong", "picked");
      b.disabled = false;
      b.setAttribute("aria-pressed", "false");
      b.removeAttribute("aria-label");
      b.querySelector(".cmark").textContent = "";
    });
    q.querySelector(".qresult").innerHTML = "";
    var first = q.querySelector(".choice");
    if (first) first.focus();
  }

  document.addEventListener("click", function (ev) {
    var choice = ev.target.closest(".choice");
    if (choice) {
      var q = choice.closest(".q");
      if (!q.classList.contains("answered")) answer(q, choice.getAttribute("data-letter"));
      return;
    }
    var retry = ev.target.closest(".retry");
    if (retry) reset(retry.closest(".q"));
  });
})();
