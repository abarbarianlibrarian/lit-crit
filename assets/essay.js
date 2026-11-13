/*
 * Essay prompt pages: a rich-text editor for the student's essay.
 *
 * Drafts are kept in localStorage under "litcrit-essays-v1" as
 *   { <essay prompt record ID>: { html, words, updated (ms), title, url } }
 * auth.js syncs that key to the student's account like the rest of their progress,
 * so signed-in students get their essays on any device. Guests keep them in this browser.
 *
 * Only simple formatting is kept: paragraphs, line breaks, bold, italic, underline.
 * window.litcritEssaySetup(root) sets up one editor and returns {lock(on), words(), flush()}.
 */
function litcritEssaySetup(root) {
  // data-essay-store: another localStorage key (mock test essays use "litcrit-mock-essays-v1", one per attempt).
  var KEY = root.getAttribute("data-essay-store") || "litcrit-essays-v1";
  var MAX = 100000;                  // characters of stored HTML per essay (a long essay is ~20,000)
  var id = root.getAttribute("data-essay");
  var ed = root.querySelector("[data-essay-editor]");
  var wordsEl = root.querySelector("[data-essay-words]");
  var statusEl = root.querySelector("[data-essay-status]");
  var guestNote = root.querySelector("[data-essay-guest]");
  var BASE = window.SITE_BASE || "/";

  function load() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function store(all) {
    try { localStorage.setItem(KEY, JSON.stringify(all)); return true; } catch (e) { return false; }
  }

  // ---- keep only the formatting we allow
  var KEEP = { P: "p", BR: "br", B: "strong", STRONG: "strong", I: "em", EM: "em", U: "u" };
  var BLOCK = { DIV: 1, P: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1, LI: 1, BLOCKQUOTE: 1, PRE: 1 };
  var DROP = { SCRIPT: 1, STYLE: 1, IFRAME: 1, OBJECT: 1, EMBED: 1, TEMPLATE: 1, SVG: 1, MATH: 1, IMG: 1, VIDEO: 1, AUDIO: 1 };
  function clean(html) {
    var doc = new DOMParser().parseFromString("<body>" + (html || ""), "text/html");
    function walk(node, out) {
      node.childNodes.forEach(function (n) {
        if (n.nodeType === 3) { out.appendChild(document.createTextNode(n.nodeValue)); return; }
        if (n.nodeType !== 1 || DROP[n.nodeName]) return;
        var tag = BLOCK[n.nodeName] ? "p" : KEEP[n.nodeName];
        if (tag === "p" && out.nodeName !== "DIV") {        // no paragraphs inside paragraphs or bold/italic
          walk(n, out); out.appendChild(document.createElement("br")); return;
        }
        if (!tag) { walk(n, out); return; }                 // unknown tags: keep their text
        var el = document.createElement(tag);
        out.appendChild(el);
        if (tag !== "br") walk(n, el);
      });
      return out;
    }
    var box = walk(doc.body, document.createElement("div"));
    // Loose text and inline tags at the top level go into paragraphs.
    var final = document.createElement("div"), para = null;
    Array.prototype.slice.call(box.childNodes).forEach(function (n) {
      if (n.nodeName === "P") { para = null; final.appendChild(n); return; }
      if (!para) { para = document.createElement("p"); final.appendChild(para); }
      para.appendChild(n);
    });
    final.querySelectorAll("p").forEach(function (p) {
      while (p.lastChild && p.lastChild.nodeName === "BR" && p.childNodes.length > 1) p.removeChild(p.lastChild);
      if (!p.textContent.trim() && !p.querySelector("br")) p.appendChild(document.createElement("br"));
    });
    return final.innerHTML;
  }
  function plain() {
    return Array.prototype.map.call(ed.querySelectorAll("p"), function (p) { return p.innerText.replace(/\s+$/, ""); })
      .join("\n\n").trim() || ed.innerText.trim();
  }
  function countWords() {
    var m = (ed.innerText || "").match(/[A-Za-z0-9À-ɏ]+(?:['’\-][A-Za-z0-9À-ɏ]+)*/g);
    return m ? m.length : 0;
  }
  function isEmpty() { return !(ed.innerText || "").trim(); }

  // ---- status line
  var savedAt = null, state = "";
  function fmtTime(ms) {
    var d = new Date(ms), now = new Date();
    var t = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    return d.toDateString() === now.toDateString() ? t : d.toLocaleDateString([], { month: "short", day: "numeric" }) + ", " + t;
  }
  function drawStatus() {
    var signed = !!window.litcritUser, msg;
    if (state === "toolong") msg = "Too long to save. Shorten the essay to keep your changes.";
    else if (state === "full") msg = "Couldn't save: this browser's storage is full.";
    else if (state === "typing") msg = "Saving…";
    else if (!savedAt) msg = signed ? "Your essay saves to your account as you type." : "Your essay saves in this browser as you type.";
    else if (signed && state === "saving") msg = "Saving to your account…";
    else if (signed && state === "offline") msg = "Saved in this browser; not saved to your account yet (offline).";
    else msg = (signed ? "Saved to your account" : "Saved in this browser") + " · " + fmtTime(savedAt);
    statusEl.textContent = msg;
    statusEl.setAttribute("data-state", state || "idle");
    if (guestNote) guestNote.hidden = signed;
    ed.classList.toggle("empty", isEmpty());
    wordsEl.textContent = countWords().toLocaleString() + (countWords() === 1 ? " word" : " words");
  }
  // auth.js reports how syncing to the account is going.
  window.addEventListener("litcrit-sync", function (ev) {
    if (state === "typing" || state === "toolong" || state === "full") return;
    state = ev.detail; drawStatus();
  });

  // ---- saving
  var timer = null;
  function save() {
    clearTimeout(timer); timer = null;
    var all = load();
    if (isEmpty()) {
      if (all[id]) { delete all[id]; store(all); }
      savedAt = null; state = ""; drawStatus(); return;
    }
    var html = clean(ed.innerHTML);
    if (html.length > MAX) { state = "toolong"; drawStatus(); return; }
    var now = Date.now();
    all[id] = { html: html, words: countWords(), updated: now,
                title: root.getAttribute("data-title") || document.title, url: location.pathname };
    if (!store(all)) { state = "full"; drawStatus(); return; }
    savedAt = now; state = window.litcritUser ? "saving" : ""; drawStatus();
  }
  function later() {
    state = "typing"; drawStatus();
    clearTimeout(timer);
    timer = setTimeout(save, 900);
  }
  window.addEventListener("pagehide", function () { if (timer) save(); });
  document.addEventListener("visibilitychange", function () { if (document.hidden && timer) save(); });

  // ---- start
  try { document.execCommand("defaultParagraphSeparator", false, "p"); } catch (e) {}
  var draft = load()[id];
  ed.innerHTML = draft && draft.html ? clean(draft.html) : "<p><br></p>";
  if (draft) savedAt = draft.updated;
  ed.contentEditable = "true";
  root.classList.add("ready");
  drawStatus();

  ed.addEventListener("input", function () {
    // Typing into an emptied editor can leave bare text: put it back in a paragraph (keeps the caret).
    var bare = Array.prototype.some.call(ed.childNodes, function (n) { return n.nodeType === 3 && n.nodeValue.trim(); });
    if (bare) { try { document.execCommand("formatBlock", false, "p"); } catch (e) {} }
    later();
  });

  // Pasting: bring in the words and simple formatting only.
  ed.addEventListener("paste", function (ev) {
    var cd = ev.clipboardData; if (!cd) return;
    ev.preventDefault();
    var html = cd.getData("text/html"), text = cd.getData("text/plain");
    var safe;
    if (html) safe = clean(html);
    else {
      var esc = function (s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); };
      var paras = text.replace(/\r\n?/g, "\n").split(/\n{2,}/);
      safe = paras.length > 1 ? paras.map(function (p) { return "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>"; }).join("")
                              : esc(text).replace(/\n/g, "<br>");
    }
    document.execCommand("insertHTML", false, safe);
  });
  ed.addEventListener("drop", function (ev) { ev.preventDefault(); });

  // ---- toolbar
  var buttons = root.querySelectorAll("[data-cmd]");
  buttons.forEach(function (b) {
    b.addEventListener("mousedown", function (ev) { ev.preventDefault(); });   // keep the selection
    b.addEventListener("click", function () {
      ed.focus();
      document.execCommand(b.getAttribute("data-cmd"), false, null);
      syncButtons(); later();
    });
  });
  function syncButtons() {
    var sel = window.getSelection();
    var inside = sel && sel.anchorNode && ed.contains(sel.anchorNode);
    buttons.forEach(function (b) {
      var on = false;
      if (inside) { try { on = document.queryCommandState(b.getAttribute("data-cmd")); } catch (e) {} }
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  document.addEventListener("selectionchange", syncButtons);

  var copyBtn = root.querySelector("[data-essay-copy]");
  copyBtn.addEventListener("click", function () {
    var text = plain();
    if (!text) return;
    var done = function () { copyBtn.textContent = "Copied"; setTimeout(function () { copyBtn.textContent = "Copy text"; }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () {});
    else {
      var r = document.createRange(); r.selectNodeContents(ed);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      try { document.execCommand("copy"); done(); } catch (e) {}
    }
  });
  root.querySelector("[data-essay-clear]").addEventListener("click", function () {
    if (isEmpty()) return;
    if (!confirm("Delete this essay? This can't be undone.")) return;
    ed.innerHTML = "<p><br></p>";
    save();
  });

  // Another tab changed this essay: show its version unless the student is typing here.
  window.addEventListener("storage", function (ev) {
    if (ev.key !== KEY || document.activeElement === ed || timer) return;
    var d = load()[id];
    ed.innerHTML = d && d.html ? clean(d.html) : "<p><br></p>";
    savedAt = d ? d.updated : null; drawStatus();
  });
  return { lock: function (on) { save(); ed.contentEditable = on ? "false" : "true"; root.classList.toggle("locked", !!on); },
           words: countWords, flush: save };
}
window.litcritEssaySetup = litcritEssaySetup;
// Essay prompt pages: set up the editor once saved progress has loaded. Mock test essays ([data-essay-lazy]) are set up by mock.js.
(window.litcritReady || Promise.resolve()).then(function () {
  document.querySelectorAll("[data-essay]:not([data-essay-lazy])").forEach(litcritEssaySetup);
});
