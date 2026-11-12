/*
 * Quick quiz (/study/quiz/): a short quiz drawn at random from the released test questions
 * (assets/data/qbank.json, written by quiz_bank in build.py).
 *
 * Filters: part, topic (set, period, reading list, or a term, author, work or poem passed in the
 * address as ?term=, ?author=, ?work=, ?poem=, ?set=, ?period=, ?list=), test years, number of
 * questions, and "only ones I missed before". A topic in the address starts a quiz right away.
 * A set topic uses only questions whose correct answer is one of the set's terms (q.ta,
 * from answer_terms in build.py), not every question that mentions one.
 *
 * Each answer is marked at once. Results are kept in localStorage "litcrit-quiz-v1"
 * ({question id: 1 right, 0 wrong}, the latest try) and synced to the account by auth.js.
 * "Missed before" means wrong on the latest quick-quiz try, or answered wrong on a scored practice test.
 */
(window.litcritReady || Promise.resolve()).then(function () {
  var root = document.querySelector("[data-qq]");
  if (!root) return;
  var form = root.querySelector("[data-qq-form]"), main = root.querySelector("[data-qq-main]");
  var countEl = root.querySelector("[data-qq-count]"), goBtn = root.querySelector("[data-qq-go]");
  var REC = "litcrit-quiz-v1";
  function load(k) { try { return JSON.parse(localStorage.getItem(k)) || {}; } catch (e) { return {}; } }
  function store(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function lines(s) { return esc(String(s || "").trim()).replace(/\n/g, "<br>"); }
  function shuffle(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; } return a; }

  goBtn.disabled = true;
  countEl.textContent = "Loading questions…";
  fetch(root.getAttribute("data-src")).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(start)
    .catch(function () { countEl.textContent = "The questions couldn’t be loaded. Refresh the page to try again."; });

  function start(bank) {
    var topicSel = form.elements.topic;
    var maxYear = Math.max.apply(null, bank.tests.map(function (t) { return t[2] || 0; }));
    var any = function (list, set) { for (var i = 0; i < list.length; i++) if (set[list[i]]) return true; return false; };
    var toSet = function (ids) { var o = {}; (ids || []).forEach(function (x) { o[x] = 1; }); return o; };
    function authorsOf(q) {
      var out = q.au.slice();
      q.po.forEach(function (p) { if (bank.poems[p]) out = out.concat(bank.poems[p][3]); });
      return out;
    }

    // A term, author, work or poem passed in the address becomes the first topic choice.
    var params = new URLSearchParams(location.search), autostart = false;
    var kinds = { term: ["terms", "This term"], author: ["authors", "This author"], work: ["works", "This work"], poem: ["poems", "This text"] };
    Object.keys(kinds).forEach(function (k) {
      var id = params.get(k);
      if (!id) return;
      var rec = (bank[kinds[k][0]] || {})[id];
      if (!rec) return;
      var o = document.createElement("option");
      o.value = k + ":" + id;
      var tmp = document.createElement("span"); tmp.innerHTML = rec[0];
      o.textContent = kinds[k][1] + ": " + tmp.textContent;
      topicSel.insertBefore(o, topicSel.options[1] || null);
      topicSel.value = o.value; autostart = true;
    });
    ["set", "period", "list"].forEach(function (k) {
      var id = params.get(k);
      if (id && topicSel.querySelector('option[value="' + k + ":" + id + '"]')) { topicSel.value = k + ":" + id; autostart = true; }
    });
    if (params.get("part")) { var r = form.querySelector('input[name=part][value="' + params.get("part") + '"]'); if (r) r.checked = true; }

    function matcher() {
      var part = (form.querySelector("input[name=part]:checked") || {}).value || "";
      var topic = topicSel.value, kind = topic.split(":")[0], id = topic.split(":")[1];
      var years = +form.elements.years.value || 0, missedOnly = form.elements.missed.checked;
      var terms, works, authors;
      if (kind === "set") terms = toSet((bank.sets[id] || [])[1]);
      if (kind === "list") { works = toSet((bank.lists[id] || [])[1]); authors = toSet((bank.lists[id] || [])[2]); }
      if (kind === "period") authors = toSet((bank.periods[id] || [])[1]);
      var missed = null, answers = {};
      if (missedOnly) {
        missed = {};
        var rec = load(REC), scores = load("litcrit-test-scores-v1");
        answers = load("litcrit-answers-v1");
        Object.keys(rec).forEach(function (k) { if (rec[k] === 0) missed[k] = 1; });
        Object.keys(scores).forEach(function (p) { (scores[p].qids || []).forEach(function (qid) { if (answers[qid] && !(qid in rec)) missed[qid] = "t"; }); });
      }
      return function (q) {
        if (part && String(q.p) !== part) return false;
        if (years && bank.tests[q.t][2] < maxYear - years + 1) return false;
        if (kind === "term" && q.tm.indexOf(id) < 0) return false;
        if (kind === "author" && authorsOf(q).indexOf(id) < 0) return false;
        if (kind === "work" && q.w.indexOf(id) < 0) return false;
        if (kind === "poem" && q.po.indexOf(id) < 0) return false;
        if (kind === "set" && !any(q.ta || [], terms)) return false; // correct answer is in the set
        if (kind === "period" && !any(authorsOf(q), authors)) return false;
        if (kind === "list" && !any(q.w, works) && !any(authorsOf(q), authors)) return false;
        if (missed) {
          if (!missed[q.i]) return false;
          // Answered on a scored test (and not tried in a quick quiz since): missed only if wrong there.
          if (missed[q.i] === "t" && q.a.indexOf(answers[q.i]) >= 0) return false;
        }
        return true;
      };
    }
    function pool() { var m = matcher(); return bank.q.filter(m); }
    function refreshCount() {
      var n = pool().length, want = +form.elements.n.value;
      countEl.textContent = n ? n.toLocaleString() + " question" + (n === 1 ? "" : "s") + " match." : "No questions match. Try a different part or topic.";
      goBtn.disabled = !n;
      goBtn.textContent = n ? "New quiz · " + Math.min(n, want) + " question" + (Math.min(n, want) === 1 ? "" : "s") : "New quiz";
    }
    form.addEventListener("change", refreshCount);
    refreshCount();

    // ---- one quiz
    var quiz = null;
    function begin(list) {
      quiz = { items: list, i: 0, right: 0, results: [] };
      show();
      if (window.matchMedia("(max-width: 760px)").matches) main.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var list = shuffle(pool()).slice(0, +form.elements.n.value);
      if (list.length) begin(list);
    });

    function sourceHtml(q) {
      var t = bank.tests[q.t];
      return 'From the <a href="' + esc(t[1]) + "#q-" + q.i + '">' + esc(t[0]) + "</a>" + (q.n ? ", question " + esc(q.n) : "") + ".";
    }
    function linksHtml(q) {
      var parts = [];
      q.po.forEach(function (p) { if (bank.poems[p]) parts.push('<a href="' + esc(bank.poems[p][1]) + '">' + esc(bank.poems[p][0]) + "</a>"); });
      q.w.forEach(function (w) { if (bank.works[w]) parts.push('<a href="' + esc(bank.works[w][1]) + '">' + bank.works[w][0] + "</a>"); });
      q.au.forEach(function (a) { if (bank.authors[a]) parts.push('<a href="' + esc(bank.authors[a][1]) + '">' + esc(bank.authors[a][0]) + "</a>"); });
      q.tm.forEach(function (t) { if (bank.terms[t]) parts.push('<a href="' + esc(bank.terms[t][1]) + '">' + esc(bank.terms[t][0]) + "</a>"); });
      return parts.length ? '<p class="qq-links">Look up: ' + parts.join(" · ") + "</p>" : "";
    }

    function show() {
      var q = quiz.items[quiz.i], n = quiz.items.length;
      var passages = q.po.map(function (p) {
        var x = bank.poems[p];
        if (!x) return "";
        return '<details class="qpassage" open><summary><span class="passage-label">Passage</span> <span class="qpassage-title">' + esc(x[0]) +
          "</span></summary>" + (x[2] ? '<div class="poem">' + lines(x[2]) + "</div>" : '<p class="muted">The text of this passage isn’t in the database yet.</p>') +
          '<p class="qpassage-link"><a href="' + esc(x[1]) + '">Open ' + esc(x[0]) + "</a></p></details>";
      }).join("");
      var choices = q.c.map(function (c, k) {
        var L = q.l[k];
        return '<li><button type="button" class="choice" data-letter="' + L + '"><span class="cletter">' + L +
          '</span><span class="ctext">' + esc(c) + '</span><span class="cmark" aria-hidden="true"></span></button></li>';
      }).join("");
      main.innerHTML =
        '<div class="qq-progress"><span>Question ' + (quiz.i + 1) + " of " + n + (q.p ? " · Part " + q.p : "") + "</span><span>" +
        quiz.right + " correct so far</span></div>" +
        '<div class="qq-track" aria-hidden="true"><span style="width:' + Math.round(100 * quiz.i / n) + '%"></span></div>' +
        passages +
        '<p class="prompt qq-prompt" tabindex="-1">' + lines(q.q) + "</p>" +
        '<ol class="plain choices">' + choices + "</ol>" +
        '<div class="qq-feedback" data-fb hidden></div>';
      main.querySelector(".qq-prompt").focus({ preventScroll: true });
    }

    main.addEventListener("click", function (ev) {
      var b = ev.target.closest(".choice");
      if (b && quiz && !b.disabled) return answer(b.getAttribute("data-letter"));
      if (ev.target.closest("[data-next]")) { quiz.i++; return quiz.i < quiz.items.length ? show() : results(); }
      if (ev.target.closest("[data-again]")) { refreshCount(); var l = shuffle(pool()).slice(0, +form.elements.n.value); if (l.length) begin(l); return; }
      if (ev.target.closest("[data-retry]")) { begin(shuffle(quiz.results.filter(function (r) { return !r.right; }).map(function (r) { return r.q; }))); }
    });

    function answer(letter) {
      var q = quiz.items[quiz.i], right = q.a.indexOf(letter) >= 0;
      if (right) quiz.right++;
      quiz.results.push({ q: q, right: right, picked: letter });
      var rec = load(REC); rec[q.i] = right ? 1 : 0; store(REC, rec);
      main.querySelectorAll(".choice").forEach(function (b) {
        var L = b.getAttribute("data-letter"), ok = q.a.indexOf(L) >= 0;
        b.disabled = true;
        b.classList.add(ok ? "right" : "wrong");
        if (L === letter) b.classList.add("picked");
        b.querySelector(".cmark").textContent = ok ? "✓" : (L === letter ? "✗" : "");
        b.setAttribute("aria-label", L + ". " + b.querySelector(".ctext").textContent + (ok ? " (correct answer)" : "") + (L === letter ? ", your choice" : ""));
      });
      var last = quiz.i === quiz.items.length - 1;
      var correctText = q.a.split("").map(function (L) { var k = q.l.indexOf(L); return L + ", " + esc(q.c[k]); }).join("; ");
      var fb = main.querySelector("[data-fb]");
      fb.innerHTML = "<p><strong>" + (right ? "Right." : "Not quite: the answer is " + correctText + ".") + "</strong> " + sourceHtml(q) + "</p>" +
        linksHtml(q) + '<button type="button" class="btn btn-study" data-next>' + (last ? "See results" : "Next question →") + "</button>";
      fb.hidden = false;
      fb.querySelector("[data-next]").focus({ preventScroll: true });
      fb.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    function results() {
      var n = quiz.items.length, missed = quiz.results.filter(function (r) { return !r.right; }).length;
      var rows = quiz.results.map(function (r, k) {
        return '<li class="' + (r.right ? "ok" : "no") + '"><span class="qq-mark" aria-hidden="true">' + (r.right ? "✓" : "✗") + "</span><span>" +
          '<span class="sr">' + (r.right ? "Right: " : "Missed: ") + "</span>" + esc(r.q.q.length > 140 ? r.q.q.slice(0, 137) + "…" : r.q.q) +
          ' <span class="muted">' + sourceHtml(r.q) + "</span></span></li>";
      }).join("");
      main.innerHTML = '<h2 class="qq-score" tabindex="-1">' + quiz.right + " of " + n + " correct</h2>" +
        '<div class="qq-track" aria-hidden="true"><span style="width:' + Math.round(100 * quiz.right / n) + '%"></span></div>' +
        '<div class="qq-actions"><button type="button" class="btn btn-study" data-again>New quiz</button>' +
        (missed ? '<button type="button" class="btn btn-soft" data-retry>Retry the ' + missed + " I missed</button>" : "") + "</div>" +
        '<ol class="plain qq-results">' + rows + "</ol>";
      main.querySelector(".qq-score").focus({ preventScroll: true });
      refreshCount();
    }

    if (autostart) {
      var list = shuffle(pool()).slice(0, +form.elements.n.value);
      if (list.length) begin(list);
    }
  }
});
