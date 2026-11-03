/*
 * Flashcards with spaced repetition, custom decks, and the "Add to flashcards" button.
 *
 * Card data comes from assets/cards/{t,a,w,p}.json (terms, authors, works, prizes), written by build.py:
 *   {record id: [front, back html, page path, reverse front?]}. A card's id is "<letter>:<record id>".
 * Deck pages carry a spec in .fc[data-deck]: {title, letters, ids, flip}. ids is a list of card ids,
 * null for every card of those letters, "due" for the review-everything page, or [] on the "My deck"
 * page (the deck comes from ?d=<deck id>).
 *
 * Schedule (localStorage "litcrit-cards-v1"): {card id: [due day, interval days, ease x100, reviews, lapses, first day]}.
 * A simplified SM-2, like Anki: Again brings the card back in a few cards; Good on a new card = 1 day;
 * after that each Good multiplies the interval by the ease (starting at 2.5); Hard and Again lower the ease.
 * Custom decks (localStorage "litcrit-decks-v1"): {deck id: {n: name, c: [card ids], t: created ms}}.
 * Both keys are saved to the student's account by auth.js when they are signed in.
 */
(function () {
  var BASE = window.SITE_BASE || "/";
  var PROG = "litcrit-cards-v1", DECKS = "litcrit-decks-v1", PREFS = "litcrit-cards-prefs-v1";
  var KIND = { t: "Term", a: "Author", w: "Work", p: "Prize" };
  var ASK = { t: "Define it", a: "Name their works", w: "Who wrote it?", p: "Who won?" };

  function load(k) { try { return JSON.parse(localStorage.getItem(k)) || {}; } catch (e) { return {}; } }
  function store(k, o) { try { localStorage.setItem(k, JSON.stringify(o)); } catch (e) {} }
  function today() { var d = new Date(); return Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 864e5); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function plural(n, word) { return n.toLocaleString() + " " + word + (n === 1 ? "" : "s"); }
  function onDom(fn) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); }

  // ---------------------------------------------------------------- card data
  var cache = {};
  function cards(letter) {
    if (!cache[letter]) {
      cache[letter] = fetch(BASE + "assets/cards/" + letter + ".json?v=" + (window.FC_V || ""))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .catch(function () { delete cache[letter]; return {}; });
    }
    return cache[letter];
  }
  function cardsFor(letters) {
    return Promise.all(letters.map(cards)).then(function (all) {
      var out = {};
      letters.forEach(function (l, i) { Object.keys(all[i]).forEach(function (id) { out[l + ":" + id] = all[i][id]; }); });
      return out;
    });
  }

  // ---------------------------------------------------------------- custom decks
  var Decks = {
    all: function () { return load(DECKS); },
    get: function (id) { return load(DECKS)[id] || null; },
    create: function (name) {
      var d = load(DECKS), id = "d" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      d[id] = { n: name, c: [], t: Date.now() };
      store(DECKS, d);
      return id;
    },
    rename: function (id, name) { var d = load(DECKS); if (d[id]) { d[id].n = name; store(DECKS, d); } },
    remove: function (id) { var d = load(DECKS); delete d[id]; store(DECKS, d); },
    toggle: function (id, card, on) {
      var d = load(DECKS);
      if (!d[id]) return;
      var c = d[id].c.filter(function (x) { return x !== card; });
      if (on) c.push(card);
      d[id].c = c;
      store(DECKS, d);
    },
    sorted: function () {
      var d = load(DECKS);
      return Object.keys(d).map(function (id) { return { id: id, deck: d[id] }; })
        .sort(function (x, y) { return (x.deck.n || "").localeCompare(y.deck.n || "", undefined, { sensitivity: "base" }); });
    }
  };
  function askName(def) {
    var n = window.prompt("Name for this deck:", def || "");
    n = (n || "").replace(/\s+/g, " ").trim().slice(0, 80);
    return n || null;
  }

  // ---------------------------------------------------------------- scheduling
  // state: [due, interval, ease x100, reviews, lapses, first day studied]
  function next(st, grade, fuzz) {
    var t = today();
    st = st ? st.slice() : [t, 0, 250, 0, 0, t];
    var iv = st[1], ef = st[2], again = false;
    if (grade === 1) {                                  // Again: relearn, back in a few cards
      if (iv > 0) { st[4] += 1; ef = Math.max(130, ef - 20); }
      iv = 0; again = 3;
    } else if (iv === 0) {                              // new or relearning
      if (grade === 2) { again = 6; }
      else iv = grade === 3 ? 1 : 4;
    } else if (grade === 2) {
      ef = Math.max(130, ef - 15); iv = Math.max(iv + 1, Math.round(iv * 1.2));
    } else if (grade === 3) {
      iv = Math.max(iv + 1, Math.round(iv * ef / 100));
    } else {
      ef = ef + 15; iv = Math.max(iv + 2, Math.round(iv * ef / 100 * 1.3));
    }
    if (fuzz && iv >= 4) iv = Math.round(iv * (0.95 + Math.random() * 0.1));
    iv = Math.min(iv, 365);
    st[0] = t + iv; st[1] = iv; st[2] = ef; st[3] += 1;
    return { st: st, again: again };
  }
  function ivLabel(r) {
    if (r.again) return "again soon";
    var d = r.st[1];
    if (d === 1) return "1 day";
    if (d < 30) return d + " days";
    if (d < 365) return Math.round(d / 30) + " mo";
    return "1 yr";
  }
  function dueLabel(day) {
    var d = day - today();
    if (d <= 0) return "today";
    if (d === 1) return "tomorrow";
    if (d < 14) return "in " + d + " days";
    return "on " + new Date((day * 864e5) + new Date().getTimezoneOffset() * 60000).toLocaleDateString(undefined, { month: "long", day: "numeric" });
  }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

  // ---------------------------------------------------------------- "Add to flashcards" button
  function addWidget(cardId, title, addLabel) {
    var box = el("div", "fc-add-box");
    var btn = el("button", "fc-add-btn");
    btn.type = "button"; btn.setAttribute("aria-expanded", "false");
    var pop = el("div", "fc-pop"); pop.hidden = true;
    box.appendChild(btn); box.appendChild(pop);

    function label() {
      var n = Decks.sorted().filter(function (x) { return x.deck.c.indexOf(cardId) >= 0; }).length;
      btn.textContent = n ? "✓ In " + plural(n, "deck") : (addLabel || "+ Add to flashcards");
      btn.classList.toggle("on", !!n);
    }
    function draw() {
      pop.textContent = "";
      pop.appendChild(el("p", "fc-pop-h", "Add " + (title ? "“" + title + "”" : "this card") + " to:"));
      var list = Decks.sorted();
      if (!list.length) pop.appendChild(el("p", "muted fc-pop-none", "You don't have any decks yet."));
      list.forEach(function (x) {
        var row = el("label", "fc-pop-row"), cb = el("input");
        cb.type = "checkbox"; cb.checked = x.deck.c.indexOf(cardId) >= 0;
        cb.addEventListener("change", function () { Decks.toggle(x.id, cardId, cb.checked); label(); });
        row.appendChild(cb);
        row.appendChild(el("span", "", x.deck.n));
        row.appendChild(el("span", "muted", " " + x.deck.c.length));
        pop.appendChild(row);
      });
      var form = el("form", "fc-pop-new"), inp = el("input"), go = el("button", "fc-btn small", "Create");
      inp.placeholder = "New deck name"; inp.maxLength = 80; inp.setAttribute("aria-label", "New deck name");
      go.type = "submit";
      form.appendChild(inp); form.appendChild(go);
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var name = inp.value.replace(/\s+/g, " ").trim();
        if (!name) { inp.focus(); return; }
        var id = Decks.create(name);
        Decks.toggle(id, cardId, true);
        label(); draw();
      });
      pop.appendChild(form);
      var a = el("a", "fc-pop-link", "My decks →"); a.href = BASE + "flashcards/";
      pop.appendChild(a);
    }
    function open(on) {
      pop.hidden = !on; btn.setAttribute("aria-expanded", on ? "true" : "false");
      if (on) { draw(); var first = pop.querySelector("input"); if (first && !Decks.sorted().length) first.focus(); }
    }
    btn.addEventListener("click", function (ev) { ev.stopPropagation(); open(pop.hidden); });
    pop.addEventListener("click", function (ev) { ev.stopPropagation(); });
    document.addEventListener("click", function () { if (!pop.hidden) open(false); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && !pop.hidden) { open(false); btn.focus(); } });
    window.addEventListener("storage", label);
    label();
    return box;
  }

  // ---------------------------------------------------------------- study screen
  function player(root) {
    var spec = JSON.parse(root.getAttribute("data-deck"));
    var params = new URLSearchParams(location.search);
    var mineId = Array.isArray(spec.ids) && !spec.ids.length ? params.get("d") : null;
    var mine = mineId ? Decks.get(mineId) : null;
    var prefs = load(PREFS);
    var flipKey = "flip:" + location.pathname;

    if (Array.isArray(spec.ids) && !spec.ids.length) {       // the "My deck" page
      var h1 = document.querySelector("main h1"), lede = document.querySelector("main .lede");
      if (!mine) {
        h1.textContent = "Deck not found";
        lede.textContent = "";
        var p = el("p", "", "This deck isn't in this browser or your account. ");
        var a = el("a", "", "See your decks"); a.href = BASE + "flashcards/"; p.appendChild(a);
        root.textContent = ""; root.appendChild(p);
        return;
      }
      document.title = mine.n + " · " + document.title.split(" · ").slice(1).join(" · ");
      h1.textContent = mine.n;
      lede.textContent = "";
      var tools = el("span", "fc-deck-tools");
      var ren = el("button", "fc-link", "Rename"), del = el("button", "fc-link", "Delete deck");
      ren.type = del.type = "button";
      ren.addEventListener("click", function () { var n = askName(mine.n); if (n) { Decks.rename(mineId, n); location.reload(); } });
      del.addEventListener("click", function () {
        if (window.confirm("Delete “" + mine.n + "”? Your progress on its cards is kept.")) { Decks.remove(mineId); location.href = BASE + "flashcards/"; }
      });
      tools.appendChild(ren); tools.appendChild(del);
      lede.appendChild(document.createTextNode(plural(mine.c.length, "card") + " · "));
      lede.appendChild(tools);
    }

    root.textContent = "";
    root.appendChild(el("p", "muted", "Loading cards…"));
    var letters = spec.letters;
    if (mine) letters = letters.filter(function (l) { return mine.c.some(function (c) { return c[0] === l; }); });
    if (spec.ids === "due") {
      var pr0 = load(PROG), t0 = today();
      letters = letters.filter(function (l) { return Object.keys(pr0).some(function (c) { return c[0] === l && pr0[c][0] <= t0; }); });
    }

    cardsFor(letters).then(function (data) {
      var ids;
      if (mine) ids = mine.c.slice();
      else if (spec.ids === "due") { var pr = load(PROG), t = today(); ids = Object.keys(pr).filter(function (c) { return pr[c][0] <= t; }); }
      else if (spec.ids) ids = spec.ids;
      else ids = Object.keys(data);
      ids = ids.filter(function (c) { return data[c]; });
      start(data, ids);
    });

    function start(data, ids) {
      var hasTerms = ids.some(function (c) { return c[0] === "t"; });
      var flipped = !!(spec.flip && hasTerms && prefs[flipKey]);
      var extraNew = 0, queue = [], cur = null, shown = false, cram = false, cramLeft = 0, reviewedToday = 0;

      root.textContent = "";
      var bar = el("div", "fc-bar");
      var counts = el("div", "fc-counts");
      var opts = el("div", "fc-opts");
      bar.appendChild(counts); bar.appendChild(opts);
      var stage = el("div", "fc-stage");
      var card = el("div", "fc-card"); card.tabIndex = 0; card.setAttribute("aria-live", "polite");
      var kind = el("p", "fc-kind"), front = el("div", "fc-front"), back = el("div", "fc-back");
      card.appendChild(kind); card.appendChild(front); card.appendChild(back);
      var actions = el("div", "fc-actions");
      var foot = el("div", "fc-foot");
      stage.appendChild(card); stage.appendChild(actions); stage.appendChild(foot);
      var done = el("div", "fc-done"); done.hidden = true;
      root.appendChild(bar); root.appendChild(stage); root.appendChild(done);

      // options: new cards per day, definition-first
      var lim = el("label", "fc-opt"), sel = el("select");
      [0, 10, 20, 30, 50, 100].forEach(function (n) { var o = el("option", "", String(n)); o.value = n; sel.appendChild(o); });
      sel.value = String(prefs.newPerDay != null ? prefs.newPerDay : 20);
      lim.appendChild(el("span", "", "New cards a day ")); lim.appendChild(sel);
      sel.addEventListener("change", function () { prefs = load(PREFS); prefs.newPerDay = +sel.value; store(PREFS, prefs); build(); });
      if (spec.ids !== "due") opts.appendChild(lim);
      if (spec.flip && hasTerms) {
        var fl = el("label", "fc-opt"), cb = el("input");
        cb.type = "checkbox"; cb.checked = flipped;
        fl.appendChild(cb); fl.appendChild(el("span", "", " " + spec.flip));
        cb.addEventListener("change", function () { flipped = cb.checked; prefs = load(PREFS); prefs[flipKey] = flipped; store(PREFS, prefs); if (cur) show(); });
        opts.appendChild(fl);
      }

      function build() {
        var pr = load(PROG), t = today(), limit = (prefs.newPerDay != null ? prefs.newPerDay : 20) + extraNew;
        var due = [], fresh = [], newToday = 0;
        ids.forEach(function (c) {
          var s = pr[c];
          if (!s) fresh.push(c);
          else {
            if (s[5] === t && s[3] > 0) newToday += 1;
            if (s[0] <= t) due.push(c);
          }
        });
        due.sort(function (x, y) { return pr[x][1] - pr[y][1] || pr[x][0] - pr[y][0] || hash(x) - hash(y); });
        fresh.sort(function (x, y) { return hash(x) - hash(y); });
        var allow = spec.ids === "due" ? 0 : Math.max(0, limit - newToday);
        var nw = fresh.slice(0, allow);
        queue = [];
        while (due.length || nw.length) {                  // a new card after every few reviews
          for (var i = 0; i < 3 && due.length; i++) queue.push(due.shift());
          if (nw.length) queue.push(nw.shift());
        }
        queue = queue.map(function (c) { return { id: c, learning: false }; });
        cram = false;
        advance();
      }

      function tally() {
        var pr = load(PROG), n = 0, l = 0, r = 0;
        queue.concat(cur ? [cur] : []).forEach(function (q) {
          if (q.learning) l++;
          else if (!pr[q.id]) n++;
          else r++;
        });
        counts.textContent = "";
        if (cram) { counts.appendChild(el("span", "fc-c", "Practice: " + cramLeft + " left")); return; }
        [["New", n, "new"], ["Learning", l, "learn"], ["Due", r, "due"]].forEach(function (x) {
          var s = el("span", "fc-c " + x[2]); s.appendChild(el("strong", "", String(x[1]))); s.appendChild(document.createTextNode(" " + x[0]));
          counts.appendChild(s);
        });
      }

      function advance() {
        cur = queue.shift() || null;
        if (!cur) return finish();
        stage.hidden = false; done.hidden = true;
        show();
      }

      function show() {
        var c = data[cur.id], letter = cur.id[0], rev = flipped && letter === "t" && c[3];
        shown = false;
        kind.textContent = rev ? "Definition · name the term" : KIND[letter] + " · " + ASK[letter];
        front.textContent = "";
        front.appendChild(el("p", rev ? "fc-q def" : "fc-q", rev ? c[3] : c[0]));
        back.innerHTML = rev ? "" : c[1];
        if (rev) back.appendChild(el("p", "fc-big", c[0]));
        var more = el("p", "fc-open"), a = el("a", "", "Open " + KIND[letter].toLowerCase() + " page ↗");
        a.href = BASE + c[2]; a.target = "_blank"; a.rel = "noopener";
        more.appendChild(a); back.appendChild(more);
        back.hidden = true; card.classList.remove("revealed");
        actions.textContent = "";
        var showBtn = el("button", "fc-btn primary", "Show answer");
        showBtn.type = "button";
        showBtn.addEventListener("click", reveal);
        actions.appendChild(showBtn);
        actions.appendChild(el("span", "fc-key", "Space"));
        foot.textContent = "";
        if (!mine) { var slot = addWidget(cur.id, c[0], "+ Add to my decks"); foot.appendChild(slot); }
        tally();
      }

      function reveal() {
        if (shown) return;
        shown = true;
        back.hidden = false; card.classList.add("revealed");
        actions.textContent = "";
        if (cram) {
          [["Missed it", 1], ["Got it", 3]].forEach(function (g, i) {
            var b = el("button", "fc-btn g" + g[1], g[0]); b.type = "button";
            b.appendChild(el("span", "fc-key", String(i + 1)));
            b.addEventListener("click", function () { cramGrade(g[1]); });
            actions.appendChild(b);
          });
          return;
        }
        var st = load(PROG)[cur.id];
        [["Again", 1], ["Hard", 2], ["Good", 3], ["Easy", 4]].forEach(function (g) {
          var b = el("button", "fc-btn g" + g[1]); b.type = "button";
          b.appendChild(el("span", "fc-g", g[0]));
          b.appendChild(el("span", "fc-iv", ivLabel(next(st, g[1], false))));
          b.appendChild(el("span", "fc-key", String(g[1])));
          b.addEventListener("click", function () { grade(g[1]); });
          actions.appendChild(b);
        });
        var first = actions.querySelector(".g3"); if (first) first.focus({ preventScroll: true });
      }

      function grade(g) {
        var pr = load(PROG), r = next(pr[cur.id], g, true);
        pr[cur.id] = r.st;
        store(PROG, pr);
        reviewedToday += 1;
        if (r.again) {
          cur.learning = true;
          queue.splice(Math.min(r.again, queue.length), 0, cur);
        }
        advance();
      }

      function cramGrade(g) {
        if (g === 1) queue.splice(Math.min(4, queue.length), 0, cur);
        else cramLeft -= 1;
        advance();
      }

      function finish() {
        stage.hidden = true; done.hidden = false; done.textContent = "";
        var pr = load(PROG), t = today(), fresh = 0, nextDay = null;
        ids.forEach(function (c) {
          var s = pr[c];
          if (!s) fresh++;
          else if (s[0] > t && (nextDay === null || s[0] < nextDay)) nextDay = s[0];
        });
        counts.textContent = "";
        if (cram) {
          done.appendChild(el("h2", "", "Practice round finished"));
          done.appendChild(el("p", "", "That didn't change your schedule."));
        } else if (!ids.length) {
          done.appendChild(el("h2", "", mine ? "This deck is empty" : "No cards here yet"));
          if (mine) done.appendChild(el("p", "", "Open any term, author, work or prize page and use “Add to flashcards” to put cards in this deck."));
        } else if (spec.ids === "due" && !reviewedToday) {
          done.appendChild(el("h2", "", "Nothing is due right now"));
          done.appendChild(el("p", "", nextDay ? "Your next card is due " + dueLabel(nextDay) + "." : "Study a deck to start your schedule."));
        } else {
          done.appendChild(el("h2", "", reviewedToday ? "Done for today" : "Nothing due in this deck right now"));
          var parts = [];
          if (reviewedToday) parts.push("You studied " + plural(reviewedToday, "card") + ".");
          if (nextDay) parts.push("The next card is due " + dueLabel(nextDay) + ".");
          if (parts.length) done.appendChild(el("p", "", parts.join(" ")));
        }
        var btns = el("p", "fc-done-btns");
        if (fresh && spec.ids !== "due") {
          var more = el("button", "fc-btn primary", "Learn " + Math.min(fresh, 10) + " more new card" + (Math.min(fresh, 10) === 1 ? "" : "s"));
          more.type = "button";
          more.addEventListener("click", function () { extraNew += 10; build(); });
          btns.appendChild(more);
        }
        if (ids.length) {
          var pc = el("button", "fc-btn", "Practice the whole deck");
          pc.type = "button";
          pc.title = "Go through every card in random order without changing your schedule";
          pc.addEventListener("click", function () {
            cram = true;
            queue = ids.slice().sort(function () { return Math.random() - 0.5; }).map(function (c) { return { id: c }; });
            cramLeft = queue.length;
            advance();
          });
          btns.appendChild(pc);
        }
        if (btns.childNodes.length) done.appendChild(btns);
        var back2 = el("p"), a = el("a", "", "← All flashcard decks"); a.href = BASE + "flashcards/";
        back2.appendChild(a); done.appendChild(back2);
      }

      document.addEventListener("keydown", function (ev) {
        if (stage.hidden || !cur || ev.metaKey || ev.ctrlKey || ev.altKey) return;
        var tag = (ev.target && ev.target.tagName) || "";
        if (/^(INPUT|SELECT|TEXTAREA)$/.test(tag)) return;
        if (!shown && (ev.key === " " || ev.key === "Enter")) { ev.preventDefault(); reveal(); return; }
        if (shown && /^[1-4]$/.test(ev.key)) {
          var g = +ev.key;
          if (cram) { if (g <= 2) { ev.preventDefault(); cramGrade(g === 1 ? 1 : 3); } }
          else { ev.preventDefault(); grade(g); }
        }
      });
      card.addEventListener("click", function (ev) { if (!shown && !(ev.target.closest && ev.target.closest("a"))) reveal(); });

      build();
      if (mine) cardList(data);
    }

    // A custom deck's card list, with remove buttons.
    function cardList(data) {
      var sec = el("section", "block fc-cardlist");
      sec.appendChild(el("h2", "", "Cards in this deck"));
      var ul = el("ul", "plain defs");
      mine.c.forEach(function (c) {
        var d = data[c];
        if (!d) return;
        var li = el("li"), a = el("a", "", d[0]);
        a.href = BASE + d[2];
        li.appendChild(a);
        li.appendChild(el("span", "muted", " · " + KIND[c[0]]));
        var rm = el("button", "fc-link fc-rm", "Remove"); rm.type = "button";
        rm.addEventListener("click", function () { Decks.toggle(mineId, c, false); li.remove(); });
        li.appendChild(rm);
        ul.appendChild(li);
      });
      sec.appendChild(ul);
      root.parentNode.appendChild(sec);
    }
  }

  // ---------------------------------------------------------------- Flashcards home page
  function home(root) {
    var pr = load(PROG), t = today();
    var due = Object.keys(pr).filter(function (c) { return pr[c][0] <= t; }).length;
    var dueLink = root.querySelector("[data-fc-due]");
    if (due) {
      dueLink.hidden = false;
      dueLink.textContent = "";
      dueLink.appendChild(el("strong", "", plural(due, "card")));
      dueLink.appendChild(document.createTextNode(" due today across all your decks · Review them →"));
    }
    var box = root.querySelector("[data-fc-mine]"), empty = root.querySelector("[data-fc-mine-empty]");
    function draw() {
      box.textContent = "";
      var list = Decks.sorted();
      empty.hidden = !!list.length;
      list.forEach(function (x) {
        var a = el("a", "fc-tile mine");
        a.href = BASE + "flashcards/my/?d=" + encodeURIComponent(x.id);
        a.appendChild(el("span", "fc-tile-t", x.deck.n));
        var n = x.deck.c.length, d = x.deck.c.filter(function (c) { return pr[c] && pr[c][0] <= t; }).length;
        var fresh = x.deck.c.filter(function (c) { return !pr[c]; }).length;
        a.appendChild(el("span", "fc-tile-m", plural(n, "card") + (d ? " · " + d + " due" : "") + (fresh ? " · " + fresh + " new" : "")));
        box.appendChild(a);
      });
    }
    root.querySelector("[data-fc-new]").addEventListener("click", function () {
      var n = askName("");
      if (!n) return;
      var id = Decks.create(n);
      location.href = BASE + "flashcards/my/?d=" + encodeURIComponent(id);
    });
    draw();
    var sync = document.querySelector("[data-fc-sync]");
    if (sync) {
      sync.textContent = "";
      if (window.litcritUser) sync.textContent = "Your schedule and decks are saved to your account.";
      else if (window.litcritAuth && window.litcritAuth.enabled) {
        sync.appendChild(document.createTextNode("Your schedule and decks are saved in this browser. "));
        var a = el("a", "", "Sign in"); a.href = BASE + "account/?next=" + encodeURIComponent(location.pathname);
        sync.appendChild(a);
        sync.appendChild(document.createTextNode(" to keep them on every device."));
      }
    }
  }

  // ---------------------------------------------------------------- start
  onDom(function () {
    (window.litcritReady || Promise.resolve()).then(function () {
      document.querySelectorAll("[data-add-card]").forEach(function (slot) {
        slot.appendChild(addWidget(slot.getAttribute("data-add-card"), slot.getAttribute("data-title")));
        slot.hidden = false;
      });
      document.querySelectorAll(".fc[data-deck]").forEach(player);
      var h = document.querySelector("[data-fc-home]");
      if (h) home(h);
    });
  });
})();
