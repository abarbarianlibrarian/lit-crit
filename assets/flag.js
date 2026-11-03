/*
 * "Flag an error": lets visitors report incorrect information.
 *   - every detail page (a term, author, work, poem, test, prize, period, tag or essay prompt)
 *     gets a "Flag an error on this page" button under its content;
 *   - every practice question gets a small flag button.
 * Reports go to the Supabase Edge Function `flag`, which rate-limits them, saves them,
 * and adds them to the Airtable Requests table.
 */
(function () {
  var cfg = window.LITCRIT_AUTH || {};
  if (!cfg.url || !cfg.key) return;
  var ENDPOINT = cfg.url + "/functions/v1/flag";
  var KINDS = { terms: "Term", authors: "Author", works: "Work", poems: "Poem", tests: "Test",
                prizes: "Prize", periods: "Period", tags: "Tag", essays: "Essay prompt" };
  var CATEGORIES = ["Wrong answer key", "Typo or scanning error", "Incorrect information",
                    "Broken link or missing content", "Other"];

  var h1 = document.querySelector("main h1[data-record]");
  var base = window.SITE_BASE || "/";
  var section = location.pathname.slice(base.length).split("/")[0];
  var pageKind = KINDS[section] || "Page";
  var pageTitle = h1 ? h1.textContent.replace(/\s+/g, " ").trim() : document.title.split(" · ")[0];

  function session() {
    try { var s = JSON.parse(localStorage.getItem("litcrit-auth")); return s && s.access_token ? s : null; }
    catch (e) { return null; }
  }

  // ---- the dialog (built once, on first use)
  var dlg = null, current = null;
  function build() {
    dlg = document.createElement("dialog");
    dlg.className = "flag-dialog";
    dlg.innerHTML =
      '<form method="dialog" class="flag-form" novalidate>' +
      '<h2>Flag an error</h2>' +
      '<p class="flag-about"></p>' +
      '<label class="acct-field"><span>What kind of problem?</span><select name="category" required>' +
      '<option value="">Choose one…</option>' +
      CATEGORIES.map(function (c) { return '<option>' + c + '</option>'; }).join("") +
      '</select></label>' +
      '<label class="acct-field"><span>What’s wrong? What should it say?</span>' +
      '<textarea name="message" rows="4" maxlength="2000" required></textarea></label>' +
      '<label class="acct-field flag-email"><span>Your email (optional, in case there’s a question)</span>' +
      '<input name="email" type="email" autocomplete="email" maxlength="200"></label>' +
      '<label class="flag-hp" aria-hidden="true">Website <input name="website" tabindex="-1" autocomplete="off"></label>' +
      '<p class="acct-msg" role="status"></p>' +
      '<div class="flag-actions"><button type="submit" class="acct-btn">Send report</button>' +
      '<button type="button" class="linkish" data-flag-cancel>Cancel</button></div>' +
      '</form>';
    document.body.appendChild(dlg);
    var form = dlg.querySelector("form");
    dlg.querySelector("[data-flag-cancel]").addEventListener("click", function () { dlg.close(); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) dlg.close(); });
    form.addEventListener("input", function () { if (!form.querySelector('[type="submit"]').disabled) msg(""); });
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      send(form);
    });
  }
  function msg(text, ok) {
    var m = dlg.querySelector(".acct-msg");
    m.textContent = text || "";
    m.className = "acct-msg" + (ok ? " ok" : text ? " err" : "");
  }
  function open(target) {
    if (!dlg) build();
    current = target;
    var form = dlg.querySelector("form");
    form.reset();
    form.hidden = false;
    msg("");
    dlg.querySelector(".flag-about").textContent = target.item;
    if (target.category) form.category.value = target.category;
    var s = session();
    dlg.querySelector(".flag-email").hidden = !!s;
    form.querySelector('[type="submit"]').disabled = false;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    (target.category ? form.message : form.category).focus();
  }
  function send(form) {
    var category = form.category.value, message = form.message.value.trim();
    if (!category) return msg("Please choose what kind of problem it is.");
    if (message.length < 5) return msg("Please describe the problem in a few words.");
    var s = session();
    var btn = form.querySelector('[type="submit"]');
    btn.disabled = true;
    msg("Sending…", true);
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", apikey: cfg.key,
                 Authorization: "Bearer " + (s ? s.access_token : cfg.key) },
      body: JSON.stringify({
        category: category, message: message,
        item: current.item, item_id: current.id || "",
        url: location.origin + location.pathname + (current.anchor || ""),
        email: s ? "" : form.email.value.trim(), website: form.website.value
      })
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error || "Couldn't send the report. Please try again.");
      });
    }).then(function () {
      msg("Thank you! Your report was sent.", true);
      if (current.button) { current.button.classList.add("sent"); current.button.title = "Report sent"; }
      setTimeout(function () { if (dlg.open) dlg.close(); }, 1600);
    }).catch(function (e) {
      btn.disabled = false;
      msg(/fetch|network/i.test(e.message) ? "Couldn't reach the server. Check your connection and try again." : e.message);
    });
  }

  // ---- page-level button
  if (h1) {
    var main = document.querySelector("main");
    var bar = document.createElement("p");
    bar.className = "flag-page";
    bar.innerHTML = '<button type="button" class="flag-link"><span aria-hidden="true">⚑</span> Flag an error on this page</button>';
    main.appendChild(bar);
    var pb = bar.querySelector("button");
    pb.addEventListener("click", function () {
      open({ item: pageKind + ": " + pageTitle, id: h1.getAttribute("data-record"), button: pb });
    });
  }

  // ---- per-question buttons
  document.querySelectorAll(".q[data-qid]").forEach(function (q) {
    var num = q.querySelector(".qnum");
    var b = document.createElement("button");
    b.type = "button";
    b.className = "flag-q";
    b.title = "Flag an error in this question";
    b.setAttribute("aria-label", "Flag an error in this question");
    b.innerHTML = '<span aria-hidden="true">⚑</span>';
    q.appendChild(b);
    b.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var src = q.querySelector(".qsource");
      var where = src ? src.textContent.trim() : pageTitle;
      open({
        item: "Question " + (num ? num.textContent.trim() : "") + ", " + where,
        id: q.getAttribute("data-qid"),
        anchor: q.id ? "#" + q.id : "",
        button: b
      });
    });
  });
})();
