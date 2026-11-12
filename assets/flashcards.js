/*
 * Flashcards: a Leitner system with three boxes (Study daily, weekly, monthly) plus Mastered.
 *
 * Card data comes from assets/cards/{t,a,w,p}.json (terms, authors, works, prizes), written by build.py:
 *   {record id: [front, back html, page path, definition (terms only)]}. A card's id is "<letter>:<record id>".
 * assets/cards/meta.json holds the site's sets (tags) with their term cards, ready-made deck titles,
 * test appearances for terms and authors, and the most-tested terms and authors.
 *
 * Saved in this browser (and in the student's account by auth.js when signed in):
 *   litcrit-fc-cards-v2  {card id: [box, streak, last day studied, place in line, source, added ms]}
 *                        box 0 = waiting in line, 1 = Study daily, 2 = weekly, 3 = monthly, 4 = mastered
 *   litcrit-fc-cats-v2   {category id: {n: name, c: [card ids], t: created ms}}
 *   litcrit-fc-meta-v2   settings, streak, pause, and today's counts
 *
 * Rules (the "streak" rule):
 *   Daily:   Got it on 3 different days in a row → Weekly.   Every Daily card is due every day.
 *   Weekly:  Got it in 2 weeks in a row → Monthly.            Due once each week (Monday–Sunday).
 *   Monthly: Got it once more → Mastered (never due again).  Due once each calendar month.
 *   Missed it, in any box → back to Daily, streak starts over.
 *   Got it on a card that isn't due is practice and changes nothing.
 * Weekly and monthly cards are spread out: today's share is what's left ÷ days left in the week or month.
 * New cards wait in line and join Study daily a few a day (paused while Daily is over the student's limit).
 * Study streak: a day counts when the student finishes the Daily cards due that day. Weekends never break it,
 * and neither does a day with no cards in Study daily at all (that day doesn't add to it either).
 * Day numbers are days since 1970-01-01 in the visitor's own time zone.
 */
(function () {
  "use strict";
  var BASE = window.SITE_BASE || "/";
  var CK = "litcrit-fc-cards-v2", GK = "litcrit-fc-cats-v2", MK = "litcrit-fc-meta-v2";
  var OLD_PROG = "litcrit-cards-v1", OLD_DECKS = "litcrit-decks-v1", OLD_PREFS = "litcrit-cards-prefs-v1";
  var KIND = { t: "Term", a: "Author", w: "Work", p: "Prize" };
  var KINDS = { t: "Terms", a: "Authors", w: "Works", p: "Prizes" };
  var ASK = { t: "Define it", a: "Name their works", w: "Who wrote it?", p: "Who won?" };
  var BOX = ["Waiting", "Study daily", "Study weekly", "Study monthly", "Mastered"];
  var SHORT = ["Waiting", "Daily", "Weekly", "Monthly", "Mastered"];
  var NEED = [0, 3, 2, 1, 0];
  var ALLB = "012345";   // study filter: every box, the waiting line, and cards not in the flashcards
  var UNIT = ["", "days", "weeks", "month", ""];
  var FLAME = '<svg class="fc-flame" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5c.8 3.4 4.9 5.6 4.9 10.6A4.9 4.9 0 0 1 12 18a4.9 4.9 0 0 1-4.9-4.9c0-2.3 1.2-3.8 2.6-4.9.3 1.7 1.1 2.8 2.6 3.3-.6-3.1-1-6.1-.3-9z" fill="#f08a2c" stroke="#c2410c" stroke-width="1.4" stroke-linejoin="round"/><path d="M12 17.9a3.2 3.2 0 0 1-3.2-3.2c0-1.6 1.2-2.5 1.9-3.4.3 1 .9 1.6 1.7 1.9.2-.9.1-1.8.6-2.6 1.2 1 2.2 2.3 2.2 4.1a3.2 3.2 0 0 1-3.2 3.2z" fill="#ffc857"/></svg>';
  var GEAR = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>';

  // ---------------------------------------------------------------- small helpers
  function raw(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function load(k) { try { return JSON.parse(raw(k)) || {}; } catch (e) { return {}; } }
  function store(k, o) { try { localStorage.setItem(k, JSON.stringify(o)); } catch (e) {} }
  function today() { var d = new Date(); return Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 864e5); }
  function ymd(day) { var d = new Date(day * 864e5); return [d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()]; }
  function dow(day) { return ((day + 3) % 7 + 7) % 7; }                 // 0 = Monday
  function week(day) { return Math.floor((day + 3) / 7); }
  function month(day) { var a = ymd(day); return a[0] * 12 + a[1]; }
  function weekend(day) { return dow(day) >= 5; }
  function daysLeftWeek(day) { return 7 - dow(day); }
  function daysLeftMonth(day) { var a = ymd(day); return new Date(Date.UTC(a[0], a[1] + 1, 0)).getUTCDate() - a[2] + 1; }
  function dateLabel(day, opts) { var a = ymd(day); return new Date(a[0], a[1], a[2]).toLocaleDateString(undefined, opts || { month: "long", day: "numeric" }); }
  function monthName(day) { return dateLabel(day, { month: "long" }); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function plural(n, w, ws) { return n.toLocaleString() + " " + (n === 1 ? w : (ws || w + "s")); }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function onDom(fn) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); }
  function $(root, sel) { return root.querySelector(sel); }
  function $$(root, sel) { return Array.prototype.slice.call(root.querySelectorAll(sel)); }
  function clampInt(v, lo, hi, def) { v = parseInt(v, 10); if (isNaN(v)) return def; return Math.max(lo, Math.min(hi, v)); }
  function url(path, q) {
    var s = Object.keys(q || {}).filter(function (k) { return q[k] !== "" && q[k] != null; })
      .map(function (k) { return k + "=" + encodeURIComponent(q[k]); }).join("&");
    return BASE + path + (s ? "?" + s : "");
  }
  function signedIn() { return !!window.litcritUser; }

  // ---------------------------------------------------------------- saved state
  var S = {
    cards: function () { return load(CK); },
    saveCards: function (c) { store(CK, c); },
    cats: function () { return load(GK); },
    saveCats: function (c) { store(GK, c); },
    meta: function () {
      var m = load(MK);
      if (m.perDay == null) m.perDay = 10;
      if (m.cap == null) m.cap = 40;
      if (m.capOn == null) m.capOn = true;
      if (m.defFirst == null) m.defFirst = true;
      m.streak = m.streak || { n: 0, best: 0, last: null, days: [] };
      return m;
    },
    saveMeta: function (m) { store(MK, m); }
  };

  // Bring over the old spaced-repetition schedule and decks once.
  function migrate() {
    if (raw(CK) !== null) return;
    var old = load(OLD_PROG), decks = load(OLD_DECKS), prefs = load(OLD_PREFS);
    if (!Object.keys(old).length && !Object.keys(decks).length) return;
    var c = {}, t = today(), ord = 0, now = Date.now();
    Object.keys(old).forEach(function (id) {
      var s = old[id] || [], iv = s[1] || 0, box = iv >= 30 ? 3 : iv >= 7 ? 2 : 1;
      c[id] = [box, 0, Math.min((s[0] || t) - iv, t - 1), 0, "old", now];
    });
    var cats = {};
    Object.keys(decks).forEach(function (k) {
      var d = decks[k]; if (!d || !Array.isArray(d.c)) return;
      cats[k] = { n: d.n || "My deck", c: d.c.slice(), t: d.t || now };
      d.c.forEach(function (id) { if (!c[id]) c[id] = [0, 0, null, ++ord, "old", now]; });
    });
    S.saveCards(c);
    if (Object.keys(cats).length) S.saveCats(cats);
    var m = S.meta();
    if (prefs.newPerDay != null) m.perDay = Math.min(50, prefs.newPerDay);
    S.saveMeta(m);
  }

  // ---------------------------------------------------------------- rules
  function isDue(st, t) {
    if (!st) return false;
    var b = st[0], l = st[2];
    if (b === 1) return l == null || l < t;
    if (b === 2) return l == null || week(l) < week(t);
    if (b === 3) return l == null || month(l) < month(t);
    return false;
  }
  function byOrder(c) { return function (x, y) { return (c[x][3] || 0) - (c[y][3] || 0) || hash(x) - hash(y); }; }
  function waitingIds(c) { return Object.keys(c).filter(function (id) { return c[id][0] === 0; }).sort(byOrder(c)); }
  function countBox(c, b) { var n = 0; for (var id in c) if (c[id][0] === b) n++; return n; }
  function dailyDue(c, t) { var n = 0; for (var id in c) if (c[id][0] === 1 && isDue(c[id], t)) n++; return n; }

  // Let new cards join Study daily: up to perDay a day, never past the student's Daily limit.
  function intro() {
    var m = S.meta(), t = today();
    if (m.paused != null) return 0;
    var c = S.cards(), before = JSON.stringify([m.introDay, m.emptyFrom, m.neutral]);
    if (m.introDay !== t) { m.introDay = t; m.introN = 0; }
    syncEmpty(c, m, t);
    if (JSON.stringify([m.introDay, m.emptyFrom, m.neutral]) !== before) S.saveMeta(m);
    var wait = waitingIds(c);
    if (!wait.length) return 0;
    var room = (m.perDay || 0) - (m.introN || 0);
    if (m.capOn) room = Math.min(room, Math.max(0, (m.cap || 0) - countBox(c, 1)));
    if (room <= 0) return 0;
    var go = wait.slice(0, room);
    go.forEach(function (id) { c[id][0] = 1; c[id][1] = 0; c[id][2] = null; });
    S.saveCards(c);
    m.introN = (m.introN || 0) + go.length;
    syncEmpty(c, m, t);
    S.saveMeta(m);
    return go.length;
  }

  // Add cards. where: "end" or "front" of the waiting line, or "daily" to start today.
  function addCards(ids, src, where) {
    var c = S.cards(), lo = Infinity, hi = -Infinity, n = 0, now = Date.now();
    Object.keys(c).forEach(function (id) { if (c[id][0] === 0) { lo = Math.min(lo, c[id][3] || 0); hi = Math.max(hi, c[id][3] || 0); } });
    if (!isFinite(lo)) { lo = 0; hi = 0; }
    var list = where === "front" ? ids.slice().reverse() : ids;
    list.forEach(function (id) {
      if (c[id]) {
        if (where === "daily" && c[id][0] === 0) { c[id][0] = 1; c[id][1] = 0; c[id][2] = null; n++; }
        return;
      }
      n++;
      if (where === "daily") c[id] = [1, 0, null, 0, src || "", now];
      else c[id] = [0, 0, null, where === "front" ? --lo : ++hi, src || "", now];
    });
    saveCards(c);
    if (where !== "daily") intro();
    return n;
  }
  function moveToDaily(ids) {
    var c = S.cards(), n = 0;
    ids.forEach(function (id) { if (c[id] && c[id][0] === 0) { c[id][0] = 1; c[id][1] = 0; c[id][2] = null; n++; } });
    saveCards(c);
    return n;
  }
  // Categories are independent of the boxes: removing a card from the flashcards leaves it in its categories.
  function removeCards(ids) {
    var c = S.cards();
    ids.forEach(function (id) { delete c[id]; });
    saveCards(c);
  }

  // Days with no cards at all in Study daily neither break nor add to the streak.
  // m.emptyFrom: the day Study daily last became empty (still empty); m.neutral: earlier [from, to] spans.
  function syncEmpty(c, m, t) {
    var n = countBox(c, 1);
    if (!n) { if (m.emptyFrom == null) m.emptyFrom = t; }
    else if (m.emptyFrom != null) {
      if (t - 1 >= m.emptyFrom) m.neutral = (m.neutral || []).concat([[m.emptyFrom, t - 1]]).slice(-20);
      m.emptyFrom = null;
    }
  }
  function saveCards(c) {
    S.saveCards(c);
    var m = S.meta(), before = JSON.stringify([m.emptyFrom, m.neutral]);
    syncEmpty(c, m, today());
    if (JSON.stringify([m.emptyFrom, m.neutral]) !== before) S.saveMeta(m);
  }
  function neutralDay(m, d) {
    if (m.emptyFrom != null && d >= m.emptyFrom) return true;
    return (m.neutral || []).some(function (r) { return d >= r[0] && d <= r[1]; });
  }
  function dailyEmpty(m) { return m.emptyFrom != null; }
  function gapOK(a, b, m) {
    if (b - a > 400) return false;
    for (var d = a + 1; d < b; d++) if (!weekend(d) && !neutralDay(m, d)) return false;
    return true;
  }
  function markDay(m, t) {
    var s = m.streak;
    if (s.last === t) return false;
    s.n = s.last != null && gapOK(s.last, t, m) ? (s.n || 0) + 1 : 1;
    s.last = t;
    s.best = Math.max(s.best || 0, s.n);
    s.days = (s.days || []).concat([t]).slice(-30);
    return true;
  }
  function curStreak(m) {
    var s = m.streak, t = m.paused != null ? m.paused : today();
    if (s.last == null) return 0;
    return s.last === t || gapOK(s.last, t, m) ? s.n : 0;
  }

  // Grade a card in the student's flashcards. Returns {from, to, counted, due} or null.
  function grade(id, got) {
    var c = S.cards(), st = c[id], m = S.meta(), t = today();
    if (!st || st[0] === 0) return null;
    var from = st[0], due = isDue(st, t), res = { from: from, to: from, counted: false, due: due, marked: false };
    if (from === 1) m.dailyDay = t;
    if (due && (from === 2 || from === 3)) {
      if (m.doneDay !== t) { m.doneDay = t; m.doneW = 0; m.doneM = 0; }
      if (from === 2) m.doneW = (m.doneW || 0) + 1; else m.doneM = (m.doneM || 0) + 1;
    }
    if (!got) { st[0] = 1; st[1] = 0; st[2] = t; res.to = 1; res.counted = true; }
    else if (due) {
      st[1] += 1; st[2] = t; res.counted = true;
      if (st[1] >= NEED[from]) { st[0] = from + 1; st[1] = 0; }
      res.to = st[0];
    } else if (from === 4) { st[2] = t; }
    c[id] = st;
    S.saveCards(c);
    syncEmpty(c, m, t);
    if (m.dailyDay === t && dailyDue(c, t) === 0) res.marked = markDay(m, t);
    S.saveMeta(m);
    return res;
  }
  function outcome(st, got, t) {
    if (!st || st[0] === 0) return "";
    var b = st[0];
    if (!got) return b === 1 ? "streak starts over" : "back to Daily";
    if (b === 4) return "stays mastered";
    if (!isDue(st, t)) return "not due: no change";
    if (st[1] + 1 >= NEED[b]) return "moves to " + (b === 3 ? "Mastered" : SHORT[b + 1]);
    return "right " + (st[1] + 1) + " of " + NEED[b] + " " + UNIT[b];
  }

  function pause() { var m = S.meta(); if (m.paused == null) { m.paused = today(); S.saveMeta(m); } }
  function resume() {
    var m = S.meta(), t = today();
    if (m.paused == null) return;
    var sh = t - m.paused;
    if (sh > 0) {
      var c = S.cards();
      Object.keys(c).forEach(function (id) { if (c[id][2] != null) c[id][2] += sh; });
      S.saveCards(c);
      if (m.streak.last != null) m.streak.last += sh;
      m.streak.days = (m.streak.days || []).map(function (d) { return d + sh; });
      if (m.emptyFrom != null) m.emptyFrom += sh;
      m.neutral = (m.neutral || []).map(function (r) { return [r[0] + sh, r[1] + sh]; });
    }
    m.paused = null; m.doneDay = null;
    S.saveMeta(m);
  }

  // Today's cards: every due Daily card plus today's share of the due Weekly and Monthly cards.
  function plan(c, m, t) {
    var p = { daily: [], w: [], m: [], tw: 0, tm: 0 };
    if (m.paused != null) return p;
    Object.keys(c).forEach(function (id) {
      var st = c[id];
      if (!isDue(st, t)) return;
      (st[0] === 1 ? p.daily : st[0] === 2 ? p.w : p.m).push(id);
    });
    var older = function (x, y) { return (c[x][2] == null ? -1e9 : c[x][2]) - (c[y][2] == null ? -1e9 : c[y][2]) || hash(x) - hash(y); };
    p.w.sort(older); p.m.sort(older);
    var dw = m.doneDay === t ? m.doneW || 0 : 0, dm = m.doneDay === t ? m.doneM || 0 : 0;
    p.tw = Math.max(0, Math.min(p.w.length, Math.ceil((p.w.length + dw) / daysLeftWeek(t)) - dw));
    p.tm = Math.max(0, Math.min(p.m.length, Math.ceil((p.m.length + dm) / daysLeftMonth(t)) - dm));
    p.today = p.daily.concat(p.w.slice(0, p.tw), p.m.slice(0, p.tm));
    p.more = p.w.slice(p.tw).concat(p.m.slice(p.tm));
    return p;
  }
  function boxStats(c, t) {
    var s = { 1: [0, 0], 2: [0, 0], 3: [0, 0], 4: 0, 0: 0 };     // [total, due]
    Object.keys(c).forEach(function (id) {
      var b = c[id][0];
      if (b === 0 || b === 4) { s[b]++; return; }
      s[b][0]++; if (isDue(c[id], t)) s[b][1]++;
    });
    return s;
  }

  // ---------------------------------------------------------------- categories
  var Cats = {
    sorted: function () {
      var g = S.cats();
      return Object.keys(g).map(function (id) { return { id: id, cat: g[id] }; })
        .sort(function (x, y) { return (x.cat.n || "").localeCompare(y.cat.n || "", undefined, { sensitivity: "base" }); });
    },
    create: function (name) {
      var g = S.cats(), id = "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
      g[id] = { n: name, c: [], t: Date.now() };
      S.saveCats(g);
      return id;
    },
    byName: function (name) {
      var hit = Cats.sorted().filter(function (x) { return x.cat.n.toLowerCase() === name.toLowerCase(); })[0];
      return hit ? hit.id : Cats.create(name);
    },
    rename: function (id, name) { var g = S.cats(); if (g[id]) { g[id].n = name; S.saveCats(g); } },
    remove: function (id) { var g = S.cats(); delete g[id]; S.saveCats(g); },
    set: function (id, card, on) {
      var g = S.cats();
      if (!g[id]) return;
      var c = g[id].c.filter(function (x) { return x !== card; });
      if (on) c.push(card);
      g[id].c = c;
      S.saveCats(g);
    },
    addMany: function (id, cards) {
      var g = S.cats(); if (!g[id]) return;
      var have = {}; g[id].c.forEach(function (x) { have[x] = 1; });
      cards.forEach(function (x) { if (!have[x]) { g[id].c.push(x); have[x] = 1; } });
      S.saveCats(g);
    },
    of: function (card) { return Cats.sorted().filter(function (x) { return x.cat.c.indexOf(card) >= 0; }); }
  };
  function askName(def) {
    var n = window.prompt("Name for this set:", def || "");
    n = (n || "").replace(/\s+/g, " ").trim().slice(0, 80);
    return n || null;
  }

  // ---------------------------------------------------------------- site data
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
  function lettersOf(ids) { var o = {}; ids.forEach(function (id) { o[id[0]] = 1; }); return "tawp".split("").filter(function (l) { return o[l]; }); }
  var metaP = null;
  function siteMeta() {
    if (!metaP) {
      metaP = fetch(BASE + "assets/cards/meta.json?v=" + (window.FC_V || ""))
        .then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; })
        .then(function (d) {
          d.sets = d.sets || {}; d.decks = d.decks || {}; d.apps = d.apps || {}; d.top = d.top || { t: [], a: [] };
          d.setsOf = {}; d.core = d.core || [];
          var core = {}; d.core.forEach(function (s) { core[s] = 1; });
          Object.keys(d.sets).forEach(function (s) {
            if (core[s]) return;   // built-in sets (All Terms, …) aren't shown as chips on cards
            d.sets[s][1].forEach(function (id) { (d.setsOf[id] = d.setsOf[id] || []).push(s); });
          });
          return d;
        });
    }
    return metaP;
  }
  function srcLabel(src, sm) {
    if (!src) return "Added";
    var k = src.split(":")[0], v = src.slice(k.length + 1);
    if (k === "set") return "Set: " + ((sm.sets[v] || [v])[0]);
    if (k === "deck") return sm.decks[v] || "A ready-made deck";
    if (k === "cat") { var g = S.cats()[v]; return g ? g.n : "A custom set"; }
    return { page: "Added from its page", top: "Most-tested", old: "Your old decks", add: "Added from this list" }[k] || "Added";
  }

  // ---------------------------------------------------------------- pieces of UI
  function dotsHtml(st) {
    if (!st || st[0] < 1 || st[0] > 3) return "";
    var need = NEED[st[0]], s = "";
    for (var i = 0; i < need; i++) s += '<span class="fc-dot' + (i < st[1] ? " on" : "") + '"></span>';
    return '<span class="fc-dots" role="img" aria-label="right ' + st[1] + " of " + need + " " + UNIT[st[0]] + '">' + s + "</span>";
  }
  function boxChip(st) {
    if (!st) return '<span class="fc-boxchip out">Not in your flashcards</span>';
    if (st[0] === 0) return '<span class="fc-boxchip out">Waiting to start</span>';
    return '<span class="fc-boxchip b' + st[0] + '">' + BOX[st[0]] + dotsHtml(st) + "</span>";
  }
  function weekDots(m) {
    var t = m.paused != null ? m.paused : today(), mon = t - dow(t), done = {}, names = ["M", "T", "W", "Th", "F", "Sa", "Su"];
    (m.streak.days || []).forEach(function (d) { done[d] = 1; });
    var parts = [], said = [];
    for (var i = 0; i < 7; i++) {
      var d = mon + i, cls = done[d] ? "done" : d === t ? (neutralDay(m, d) ? "rest now" : "now") : i >= 5 ? "opt" : d <= t && neutralDay(m, d) ? "rest" : d < t ? "miss" : "todo";
      parts.push('<span class="fc-wd ' + cls + '"><span>' + (done[d] ? "✓" : /rest/.test(cls) ? "–" : "") + "</span>" + names[i] + "</span>");
      if (done[d]) said.push(names[i]);
    }
    return '<span class="fc-week" role="img" aria-label="This week: ' + (said.length ? "studied " + said.join(", ") : "nothing yet") +
      '; weekends are optional">' + parts.join("") + "</span>";
  }
  function streakBadge(m) {
    var n = curStreak(m);
    return '<div class="fc-streak">' + FLAME +
      '<span class="fc-streak-n"><b>' + n + '</b> day streak<small>' + (dailyEmpty(m) && m.paused == null ? "Paused until you add daily cards" : m.streak.best ? "Best: " + plural(m.streak.best, "day") : "Finish your daily cards to start one") + "</small></span>" +
      weekDots(m) + "</div>";
  }

  // A category picker: checkboxes for every category plus "new category". onChange(cardId) after any change.
  function catPicker(cardId, onChange) {
    var box = document.createElement("div");
    box.className = "fc-catpick";
    function draw() {
      var list = Cats.sorted();
      box.innerHTML = '<p class="fc-pop-h">My custom sets</p>' +
        (list.length ? "" : '<p class="muted fc-pop-none">No custom sets yet.</p>') +
        list.map(function (x) {
          return '<label class="fc-pop-row"><input type="checkbox" data-cat="' + esc(x.id) + '"' + (x.cat.c.indexOf(cardId) >= 0 ? " checked" : "") +
            "> <span>" + esc(x.cat.n) + '</span><span class="muted">' + x.cat.c.length + "</span></label>";
        }).join("") +
        '<form class="fc-pop-new"><input maxlength="80" placeholder="New set" aria-label="New set name"><button class="fc-btn small" type="submit">Add</button></form>';
    }
    box.addEventListener("change", function (ev) {
      var cb = ev.target.closest("[data-cat]"); if (!cb) return;
      Cats.set(cb.getAttribute("data-cat"), cardId, cb.checked);
      draw(); onChange && onChange();
    });
    box.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var inp = $(box, "input:not([type])"), name = inp.value.replace(/\s+/g, " ").trim().slice(0, 80);
      if (!name) { inp.focus(); return; }
      var id = Cats.create(name);
      Cats.set(id, cardId, true);
      draw(); onChange && onChange();
      var again = $(box, "input:not([type])"); if (again) again.focus();
    });
    draw();
    return box;
  }

  // A popover anchored to a button. Returns {open(bool), pop}.
  function popover(btn, pop, onclose) {
    pop.hidden = true;
    function open(on) {
      var was = !pop.hidden;
      pop.hidden = !on; btn.setAttribute("aria-expanded", on ? "true" : "false");
      if (on) {
        pop.style.left = ""; pop.style.right = "";
        var r = pop.getBoundingClientRect();
        if (r.right > document.documentElement.clientWidth - 8) { pop.style.left = "auto"; pop.style.right = "0"; }
      }
      if (was && !on && onclose) onclose();
    }
    function outside() { if (!pop.isConnected) { document.removeEventListener("click", outside); document.removeEventListener("keydown", key); return; } if (!pop.hidden) open(false); }
    function key(ev) { if (!pop.isConnected) return outside(); if (ev.key === "Escape" && !pop.hidden) { open(false); btn.focus(); } }
    btn.setAttribute("aria-expanded", "false");
    btn.addEventListener("click", function (ev) { ev.stopPropagation(); open(pop.hidden); if (!pop.hidden && pop.onopen) pop.onopen(); });
    pop.addEventListener("click", function (ev) { ev.stopPropagation(); });
    document.addEventListener("click", outside);
    document.addEventListener("keydown", key);
    return { open: open };
  }

  // ---------------------------------------------------------------- "Add to flashcards" on record pages
  function addWidget(cardId, title) {
    var wrap = document.createElement("div");
    wrap.className = "fc-add-box";
    var btn = document.createElement("button");
    btn.type = "button"; btn.className = "fc-add-btn";
    var pop = document.createElement("div");
    pop.className = "fc-pop";
    wrap.appendChild(btn); wrap.appendChild(pop);
    function label() {
      var st = S.cards()[cardId];
      btn.textContent = st ? "✓ In my flashcards ▾" : "+ Add to flashcards";
      btn.classList.toggle("on", !!st);
    }
    var head = document.createElement("div"), foot = document.createElement("p");
    head.className = "fc-pop-status"; foot.className = "fc-pop-foot";
    function draw() {
      pop.innerHTML = "";
      pop.appendChild(head);
      pop.appendChild(catPicker(cardId, function () { label(); drawHead(); }));
      pop.appendChild(foot);
      drawHead();
    }
    function drawHead() {
      var st = S.cards()[cardId], t = today();
      if (!st) {
        head.innerHTML = '<p class="fc-pop-h">' + esc(title ? "“" + title + "”" : "This card") + " isn’t in your flashcards yet.</p>" +
          '<p class="fc-pop-btns"><button type="button" class="fc-btn small primary" data-do="end">Add to the waiting line</button>' +
          '<button type="button" class="fc-btn small" data-do="daily">Start it today</button></p>';
      } else if (st[0] === 0) {
        var line = waitingIds(S.cards()), pos = line.indexOf(cardId) + 1;
        head.innerHTML = '<p class="fc-pop-h">Waiting to start · number ' + pos + ' in line</p>' +
          '<p class="fc-pop-btns"><button type="button" class="fc-btn small" data-do="daily">Start it today</button></p>';
      } else {
        head.innerHTML = '<p class="fc-pop-h">In ' + BOX[st[0]] + (st[0] <= 3 && st[0] >= 1 ? " · right " + st[1] + " of " + NEED[st[0]] + " " + UNIT[st[0]] : "") +
          (isDue(st, t) ? " · due now" : "") + "</p>";
      }
      foot.innerHTML = '<a href="' + BASE + 'flashcards/">My flashcards →</a>' + (st ? '<button type="button" class="fc-link warn" data-do="remove">Remove card</button>' : "");
    }
    pop.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-do]"); if (!b) return;
      var what = b.getAttribute("data-do");
      if (what === "remove") {
        if (!window.confirm("Remove this card from your flashcards? Its progress is lost.")) return;
        removeCards([cardId]);
      } else addCards([cardId], "page", what);
      label(); draw();
    });
    pop.onopen = draw;
    popover(btn, pop);
    window.addEventListener("storage", label);
    label();
    return wrap;
  }

  // "Add all" on set pages and ready-made deck pages.
  function addAll(slot) {
    var spec = JSON.parse(slot.getAttribute("data-fc-addall"));
    function go(ids) {
      function draw(msg) {
        var c = S.cards(), have = ids.filter(function (id) { return c[id]; }).length, left = ids.length - have;
        slot.innerHTML = "";
        var p = document.createElement("div");
        p.className = "fc-addall";
        if (!ids.length) { p.innerHTML = '<span class="muted">No cards here yet.</span>'; slot.appendChild(p); return; }
        p.innerHTML = (left ? '<button type="button" class="btn btn-study btn-sm" data-add>+ Add ' + (have ? "the other " + left : "all " + ids.length) +
            " card" + (left === 1 ? "" : "s") + " to my flashcards</button>" : "") +
          '<span class="fc-addall-note">' + (msg ? msg :
            !left ? "✓ All " + plural(ids.length, "card") + " are in your flashcards." :
            have ? plural(have, "card") + " already in your flashcards; " + left + " will join the waiting line." :
            "They join the waiting line and start a few a day.") + "</span>";
        slot.appendChild(p);
        var b = $(p, "[data-add]");
        if (b) b.addEventListener("click", function () {
          var n = addCards(ids, spec.src || "add", "end"), m = S.meta();
          draw("Added " + plural(n, "card") + ". New cards join Study daily " + m.perDay + " a day. " +
            '<a href="' + BASE + 'flashcards/waiting/">See the waiting line</a>');
        });
      }
      draw();
    }
    if (spec.ids) go(spec.ids);
    else cardsFor(spec.letters).then(function (d) { go(Object.keys(d)); });
  }

  // ---------------------------------------------------------------- study screen
  // The cards in the chosen custom sets (cats) and site sets: in any of them (union), or in all of them (intersection).
  function scopeOf(cats, sets, all, sm) {
    if (!cats.length && !sets.length) return null;
    var g = S.cats(), groups = [];
    cats.forEach(function (k) { if (g[k]) groups.push(g[k].c); });
    sets.forEach(function (x) { if (sm.sets[x]) groups.push(sm.sets[x][1]); });
    var count = {}, o = {};
    groups.forEach(function (ids) {
      var seen = {};
      ids.forEach(function (id) { if (!seen[id]) { seen[id] = 1; count[id] = (count[id] || 0) + 1; } });
    });
    Object.keys(count).forEach(function (id) { if (!all || count[id] === groups.length) o[id] = 1; });
    return o;
  }
  // Test appearances filter: at least `min` (blank or 0 = any). Prizes have no count, so a minimum leaves them out.
  function appsOK(id, min, sm) {
    if (!min || isNaN(min)) return true;
    if (id[0] === "p") return false;
    return (sm.apps[id] || 0) >= min;
  }
  function readFilter(q) {
    var list = function (k) { return (q.get(k) || "").split(",").filter(Boolean); };
    var b = (q.get("b") || "123").split("").map(Number).filter(function (x) { return x >= 0 && x <= 5; });
    return { c: list("c"), s: list("s"), all: q.get("m") === "all", b: b.length ? b : [1, 2, 3], d: q.get("d") === "1",
             k: (q.get("k") || "tawp").split("").filter(function (l) { return KIND[l]; }), a: q.get("a") == null || q.get("a") === "" ? null : +q.get("a") };
  }
  function filterIds(c, f, sm, t) {
    var scope = scopeOf(f.c, f.s, f.all, sm);
    // Box 0 is the waiting line and 5 means "not in my flashcards" (only from a chosen set or category).
    // Cards outside the four boxes are practice: grading them changes nothing, and "due only" doesn't apply.
    var ids = Object.keys(c);
    if (scope && f.b.indexOf(5) >= 0) Object.keys(scope).forEach(function (id) { if (!c[id]) ids.push(id); });
    return ids.filter(function (id) {
      var st = c[id], b = st ? st[0] : 5;
      if (f.b.indexOf(b) < 0) return false;
      if (scope && !scope[id]) return false;
      if (f.k.indexOf(id[0]) < 0) return false;
      if (!appsOK(id, f.a, sm)) return false;
      if (f.d && b >= 1 && b <= 4 && !isDue(st, t)) return false;
      return true;
    });
  }
  function scopeNames(f, sm) {
    var g = S.cats(), names = [];
    f.c.forEach(function (k) { if (g[k]) names.push(g[k].n); });
    f.s.forEach(function (s) { if (sm.sets[s]) names.push(sm.sets[s][0]); });
    return names;
  }
  function joinNames(a) { return a.length <= 1 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; }

  function player(root) {
    var spec = JSON.parse(root.getAttribute("data-deck"));
    var q = new URLSearchParams(location.search);
    root.innerHTML = '<p class="muted">Loading cards…</p>';
    intro();
    siteMeta().then(function (sm) {
      var c = S.cards(), m = S.meta(), t = today();
      if (spec.mode === "source") return source(sm);
      if (m.paused != null) return pausedNote();
      if (spec.mode === "today") {
        var p = plan(c, m, t), more = q.get("more") === "1";
        var ids = (more ? p.more : p.today).slice().sort(function (x, y) { return hash(x + t) - hash(y + t); });
        session(ids, { label: more ? "More weekly and monthly cards" : "Today’s cards", today: true, sm: sm });
      } else {
        var f = readFilter(q), names = scopeNames(f, sm);
        var ids2 = filterIds(c, f, sm, t).sort(function (x, y) { return hash(x + t) - hash(y + t); });
        var h1 = document.querySelector("main h1");
        if (h1 && names.length) h1.textContent = joinNames(names);
        session(ids2, { label: names.length ? (f.all && names.length > 1 ? "In all of " : "") + joinNames(names) : "Your flashcards", sm: sm, filter: f });
      }
    });

    function pausedNote() {
      root.innerHTML = '<div class="fc-paused-note"><p><b>Your flashcards are paused for the off-season.</b> Resume to study; your boxes and streak pick up where you left off.</p>' +
        '<p><button type="button" class="btn btn-study" data-resume>Resume and study</button> <a href="' + BASE + 'flashcards/">Back to flashcards</a></p></div>';
      $(root, "[data-resume]").addEventListener("click", function () { resume(); location.reload(); });
    }

    // A ready-made deck or set: add it, or practice it without changing anything.
    function source(sm) {
      var getIds = spec.ids ? Promise.resolve(spec.ids) : cardsFor(spec.letters).then(function (d) { return Object.keys(d); });
      getIds.then(function (ids) {
        root.innerHTML = "";
        var slot = document.createElement("div");
        slot.setAttribute("data-fc-addall", JSON.stringify({ ids: ids, src: spec.src }));
        root.appendChild(slot);
        addAll(slot);
        var pr = document.createElement("p");
        pr.className = "fc-practice-line";
        pr.innerHTML = '<button type="button" class="fc-btn" data-practice>Practice these now</button> <span class="muted">Go through them in random order. This doesn’t change your boxes.</span>';
        root.appendChild(pr);
        $(pr, "[data-practice]").addEventListener("click", function () {
          var list = ids.slice().sort(function () { return Math.random() - 0.5; }).slice(0, 50);
          root.innerHTML = "";
          var stage = document.createElement("div");
          root.appendChild(stage);
          session(list, { label: "Practice", cram: true, sm: sm, into: stage, all: ids });
        });
      });
    }

    function session(ids, o) {
      var host = o.into || root;
      if (!ids.length) return empty(o);
      host.innerHTML = '<p class="muted">Loading cards…</p>';
      cardsFor(lettersOf(ids)).then(function (data) {
        ids = ids.filter(function (id) { return data[id]; });
        if (!ids.length) return empty(o);
        run(ids, data, o, host);
      });
    }

    function empty(o) {
      var c = S.cards(), p = plan(c, S.meta(), today());
      var msg = o.today ? (Object.keys(c).length ? "Nothing left for today." : "You don’t have any flashcards yet.") : "No cards match.";
      var noScope = o.filter && o.filter.b.indexOf(5) >= 0 && !o.filter.c.length && !o.filter.s.length;
      root.innerHTML = '<div class="fc-done"><h2>' + msg + "</h2>" +
        (o.today && p.more.length && !q.get("more") ? '<p>You can get ahead: ' + plural(p.more.length, "more weekly or monthly card", "more weekly or monthly cards") + " are due this week or month.</p>" +
          '<p class="fc-done-btns"><a class="btn btn-study" href="' + url("flashcards/review/", { more: 1 }) + '">Keep going</a></p>' : "") +
        (o.filter && o.filter.d ? '<p class="fc-done-btns"><a class="fc-btn" href="' + location.pathname + location.search.replace(/([?&])d=1/, "$1d=0") + '">Study them even though they aren’t due</a></p>' : "") +
        (noScope ? '<p>To study cards that aren’t in your flashcards, pick a set first.</p>' : "") +
        '<p><a href="' + BASE + 'flashcards/">← Flashcards</a></p></div>';
    }

    function run(ids, data, o, host) {
      var m = S.meta(), defFirst = m.defFirst;
      var queue = ids.map(function (id) { return { id: id, again: false }; });
      var total = queue.length, done = 0, cur = null, shown = false;
      var tally = { got: 0, missed: 0, moves: {}, stay: 0, practice: 0, outside: 0, missedIds: [], marked: false };
      var hasTerms = ids.some(function (id) { return id[0] === "t"; });

      host.innerHTML =
        '<div class="fc-top"><div class="fc-prog"><div class="fc-prog-t"><span>' + esc(o.label) + '</span><span data-count></span></div>' +
        '<div class="fc-meter"><div data-meter></div></div></div>' +
        (hasTerms ? '<label class="fc-opt"><input type="checkbox" data-deffirst' + (defFirst ? " checked" : "") + "> Definition first</label>" : "") + "</div>" +
        '<div class="fc-col" data-stage>' +
        '<p class="fc-toast" aria-live="polite" data-toast></p>' +
        '<article class="fc-card" tabindex="0"><div class="fc-card-head"><span class="fc-kind" data-kind></span><span data-chip></span></div>' +
        '<div class="fc-front" data-front></div><div class="fc-back" data-back hidden></div>' +
        '<p class="fc-open"><a data-open target="_blank" rel="noopener"></a></p></article>' +
        '<div class="fc-actions" data-actions></div>' +
        '<p class="fc-honest muted" data-honest hidden>Be honest: only “Got it” if you knew it before you looked.</p>' +
        '<div class="fc-cats" data-cats></div></div>' +
        '<div class="fc-done" data-done hidden></div>';
      var R = function (k) { return $(host, "[data-" + k + "]"); };
      var card = $(host, ".fc-card");
      var dfb = R("deffirst");
      if (dfb) dfb.addEventListener("change", function () {
        defFirst = dfb.checked; var mm = S.meta(); mm.defFirst = defFirst; S.saveMeta(mm); if (cur) show();
      });

      function advance() {
        cur = queue.shift() || null;
        if (!cur) return finish();
        show();
      }
      function show() {
        var d = data[cur.id], L = cur.id[0], rev = defFirst && L === "t" && d[3], st = S.cards()[cur.id];
        shown = false;
        R("count").textContent = Math.min(done + 1, total) + " of " + total + (cur.again ? " · again" : "");
        R("meter").style.width = Math.round(100 * done / total) + "%";
        R("kind").textContent = rev ? "Definition · Name the term" : KIND[L] + " · " + ASK[L];
        R("chip").innerHTML = o.cram ? '<span class="fc-boxchip out">Practice</span>' : boxChip(st);
        R("front").innerHTML = rev ? '<p class="fc-q def">' + esc(d[3]) + "</p>" : '<p class="fc-q">' + esc(d[0]) + "</p>";
        R("back").innerHTML = rev ? '<p class="fc-q fc-ans">' + esc(d[0]) + "</p>" : d[1];
        R("back").hidden = true;
        card.classList.remove("revealed");
        var a = R("open"); a.href = BASE + d[2]; a.textContent = "Open " + KIND[L].toLowerCase() + " page ↗";
        R("actions").innerHTML = '<button type="button" class="fc-btn primary fc-show">Show answer <span class="fc-key">Space</span></button>';
        $(R("actions"), "button").addEventListener("click", reveal);
        R("honest").hidden = true;
        drawCats();
      }
      function reveal() {
        if (shown || !cur) return;
        shown = true;
        R("back").hidden = false; card.classList.add("revealed");
        var st = S.cards()[cur.id], t = today(), sched = !o.cram && !cur.again && st && st[0] > 0;
        R("actions").innerHTML =
          '<button type="button" class="fc-grade miss" data-g="0">Missed it<small>' + (sched ? esc(outcome(st, false, t)) + " · " : "") + 'key 1</small></button>' +
          '<button type="button" class="fc-grade got" data-g="1">Got it<small>' + (sched ? esc(outcome(st, true, t)) + " · " : "") + 'key 2</small></button>';
        $$(R("actions"), "[data-g]").forEach(function (b) { b.addEventListener("click", function () { answer(b.getAttribute("data-g") === "1"); }); });
        R("honest").hidden = false;
        var g = $(R("actions"), ".got"); if (g) g.focus({ preventScroll: true });
      }
      function answer(got) {
        if (!shown || !cur) return;
        var id = cur.id, msg = "";
        if (!cur.again) { done += 1; got ? tally.got++ : tally.missed++; }
        if (!got && !cur.again) tally.missedIds.push(id);
        if (!o.cram && !cur.again) {
          var res = grade(id, got);
          if (res) {
            if (res.marked) tally.marked = true;
            if (res.to !== res.from) {
              var k = res.to < res.from || !got ? "down" : res.from + ">" + res.to;
              if (!got && res.from === 1) k = "missed1";
              tally.moves[k] = (tally.moves[k] || 0) + 1;
              msg = got ? "Moved to " + BOX[res.to] + "." : "Back to Study daily.";
            } else if (!got) { tally.moves.missed1 = (tally.moves.missed1 || 0) + 1; msg = "Streak starts over."; }
            else if (res.counted) { tally.stay++; msg = "Right " + S.cards()[id][1] + " of " + NEED[res.to] + " " + UNIT[res.to] + "."; }
            else tally.practice++;
          } else tally.outside++;
        }
        R("toast").textContent = msg;
        if (!got) queue.splice(Math.min(4, queue.length), 0, { id: id, again: true });
        advance();
      }

      // Categories at the bottom of the card: remove from yours, add with the picker. Sets can't be removed.
      function drawCats() {
        var box = R("cats"), id = cur.id, st = S.cards()[id];
        box.innerHTML = "";
        var html = (st ? "" : '<button type="button" class="fc-tag add" data-addbank>+ Add to my flashcards</button>') + '<span class="fc-cats-h">Sets</span>';
        Cats.of(id).forEach(function (x) {
          html += '<button type="button" class="fc-tag" data-rm="' + esc(x.id) + '" aria-label="Remove from ' + esc(x.cat.n) + '">' + esc(x.cat.n) + ' <span aria-hidden="true">×</span></button>';
        });
        (o.sm.setsOf[id] || []).slice().sort(function (x, y) { return o.sm.sets[x][0].localeCompare(o.sm.sets[y][0]); }).forEach(function (s) {
          html += '<span class="fc-tag set" title="Sets come from the site and can’t be removed">Set: ' + esc(o.sm.sets[s][0]) + "</span>";
        });
        html += '<span class="fc-add-box"><button type="button" class="fc-tag add" data-pick>+ Custom set</button><span class="fc-pop up" data-pop></span></span>';
        box.innerHTML = html;
        $$(box, "[data-rm]").forEach(function (b) {
          b.addEventListener("click", function () { Cats.set(b.getAttribute("data-rm"), id, false); drawCats(); });
        });
        var ab = $(box, "[data-addbank]");
        if (ab) ab.addEventListener("click", function () { addCards([id], o.all ? "add" : "page", "end"); drawCats(); });
        var pop = R("pop");
        pop.appendChild(catPicker(id, function () {}));
        popover($(box, "[data-pick]"), pop, function () { if (cur && cur.id === id) drawCats(); });
        pop.onopen = function () { var i = $(pop, "input:not([type])"); if (i && !Cats.sorted().length) i.focus(); };
      }

      function finish() {
        R("stage").hidden = true;
        $(host, ".fc-top").hidden = true;
        var d = R("done"), c = S.cards(), mm = S.meta(), t = today(), p = plan(c, mm, t);
        var mv = tally.moves, rows = [
          ["Daily → <b>Weekly</b>", mv["1>2"], "up"], ["Weekly → <b>Monthly</b>", mv["2>3"], "up"],
          ["Monthly → <b>Mastered</b>", mv["3>4"], "up"], ["Building a streak, staying put", tally.stay, ""],
          ["Missed → back to <b>Daily</b>", (mv.down || 0) + (mv.missed1 || 0), "down"]
        ].filter(function (r) { return r[1]; });
        var html;
        if (o.cram) {
          html = "<h2>Practice round finished</h2><p>You got " + tally.got + " of " + (tally.got + tally.missed) + ". That didn’t change your boxes.</p>";
        } else {
          html = "<h2>" + (o.today && !p.today.length ? "Done for today" : "Session finished") + "</h2>" +
            "<p>You studied " + plural(tally.got + tally.missed, "card") + ": " + tally.got + " got it, " + tally.missed + " missed.</p>";
          if (rows.length) html += '<div class="fc-moves"><p class="fc-moves-h">Where your cards went</p>' + rows.map(function (r) {
            return '<p><span>' + r[0] + '</span><span class="' + r[2] + '">' + plural(r[1], "card") + (r[2] === "up" ? " ↑" : r[2] === "down" ? " ↓" : "") + "</span></p>";
          }).join("") + "</div>";
          if (tally.outside) html += '<p class="muted">' + plural(tally.outside, "card was", "cards were") + " outside your boxes, so " + (tally.outside === 1 ? "it was" : "they were") + " practice only.</p>";
          if (tally.marked) html += '<p class="fc-streak-won">' + FLAME + " <span><b>" + curStreak(mm) + "-day streak!</b> Daily cards finished for today.</span></p>";
          var bs = boxStats(c, t);
          var bits = [];
          if (bs[2][0]) bits.push("<b>This week:</b> " + (bs[2][0] - bs[2][1]) + " of " + bs[2][0] + " weekly cards done");
          if (bs[3][0]) bits.push("<b>" + monthName(t) + ":</b> " + (bs[3][0] - bs[3][1]) + " of " + bs[3][0] + " monthly cards done");
          if (bits.length) html += '<p class="fc-period">' + bits.join(". ") + ".</p>";
        }
        html += '<p class="fc-done-btns">';
        if (!o.cram && p.today.length && o.today) html += '<a class="btn btn-study" href="' + url("flashcards/review/") + '">Study the rest of today’s ' + plural(p.today.length, "card") + "</a>";
        else if (!o.cram && p.more.length) html += '<a class="btn btn-study" href="' + url("flashcards/review/", { more: 1 }) + '">Keep going: ' + plural(p.more.length, "more weekly or monthly card", "more weekly or monthly cards") + "</a>";
        if (tally.missedIds.length) html += '<button type="button" class="fc-btn" data-again>Practice my ' + plural(tally.missedIds.length, "miss", "misses") + "</button>";
        if (o.cram && o.all) html += '<button type="button" class="fc-btn" data-more>Practice another round</button>';
        html += '<a class="fc-btn" href="' + BASE + 'flashcards/">Back to flashcards</a></p>';
        if (tally.missedIds.length && !o.cram) html += '<p class="muted fc-small">Practicing misses again today doesn’t move them; they come back tomorrow.</p>';
        d.innerHTML = html; d.hidden = false;
        var ag = $(d, "[data-again]");
        if (ag) ag.addEventListener("click", function () { session(tally.missedIds.slice(), { label: "Practice my misses", cram: true, sm: o.sm, into: host }); });
        var mo = $(d, "[data-more]");
        if (mo) mo.addEventListener("click", function () {
          session(o.all.slice().sort(function () { return Math.random() - 0.5; }).slice(0, 50), o);
        });
        d.focus && d.setAttribute("tabindex", "-1"); d.focus && d.focus({ preventScroll: true });
      }

      function onKey(ev) {
        if (!host.isConnected) { document.removeEventListener("keydown", onKey); return; }
        if (R("stage").hidden || !cur || ev.metaKey || ev.ctrlKey || ev.altKey) return;
        var tag = (ev.target && ev.target.tagName) || "";
        if (/^(INPUT|SELECT|TEXTAREA)$/.test(tag)) return;
        if (!shown && (ev.key === " " || ev.key === "Enter")) { ev.preventDefault(); reveal(); return; }
        if (shown && (ev.key === "1" || ev.key === "2")) { ev.preventDefault(); answer(ev.key === "2"); }
      }
      document.addEventListener("keydown", onKey);
      card.addEventListener("click", function (ev) { if (!shown && !(ev.target.closest && ev.target.closest("a"))) reveal(); });
      advance();
    }
  }

  // ---------------------------------------------------------------- settings panel
  function settings(onClose) {
    var m = S.meta(), c = S.cards(), wait = countBox(c, 0);
    var ov = document.createElement("div");
    ov.className = "fc-overlay";
    ov.innerHTML = '<aside class="fc-panel" role="dialog" aria-modal="true" aria-labelledby="fc-set-h">' +
      '<div class="fc-panel-head"><h2 id="fc-set-h">Flashcard settings</h2><button type="button" class="fc-x" data-close aria-label="Close settings">×</button></div>' +
      '<section><h3>New cards</h3><p><b>' + plural(wait, "card") + " waiting</b> to join Study daily.</p>" +
      (wait ? '<form class="fc-row" data-addnow><label for="fc-addn">Add</label><input id="fc-addn" class="fc-num" type="number" min="1" max="' + wait + '" value="' + Math.min(10, wait) + '"><span>now</span><button type="submit" class="btn btn-study btn-sm">Add to Study daily</button></form>' : "") +
      '<p class="fc-ok" data-addmsg aria-live="polite"></p>' +
      '<label class="fc-row" for="fc-perday">Add <input id="fc-perday" class="fc-num" type="number" min="0" max="100" value="' + m.perDay + '"> new cards each day automatically</label>' +
      '<label class="fc-row"><input type="checkbox" data-capon' + (m.capOn ? " checked" : "") + '> Pause new cards while Study daily has more than <input class="fc-num" type="number" min="1" max="999" value="' + m.cap + '" aria-label="Daily card limit" data-cap> cards</label>' +
      '<p><a href="' + BASE + 'flashcards/waiting/">View and edit the waiting cards →</a></p></section>' +
      '<section><h3>Studying</h3><label class="fc-row"><input type="checkbox" data-df' + (m.defFirst ? " checked" : "") + "> Show the definition first on term cards</label></section>" +
      '<section><h3>Streak</h3><p><b>' + plural(curStreak(m), "day") + "</b> now" + (m.streak.best ? " · best " + plural(m.streak.best, "day") : "") + "</p>" +
      '<p class="muted">A day counts when you finish your daily cards. Weekends are optional: studying adds a day, skipping doesn’t break your streak. Days with no cards in Study daily don’t count either way.</p></section>' +
      '<section data-season><h3>Off-season</h3>' + (m.paused != null
        ? '<p>Paused since ' + dateLabel(m.paused) + '.</p><p><button type="button" class="btn btn-study btn-sm" data-resume>Resume studying</button></p>'
        : '<p class="muted">Done for the year? Pausing freezes your streak and all your boxes so nothing piles up while you’re away.</p><p><button type="button" class="fc-btn" data-pauseask>Pause until next season</button></p>') +
      "</section></aside>";
    document.body.appendChild(ov);
    document.body.classList.add("fc-noscroll");
    var prev = document.activeElement;
    function close() {
      ov.remove(); document.body.classList.remove("fc-noscroll");
      document.removeEventListener("keydown", esc_);
      if (prev && prev.focus) prev.focus();
      onClose && onClose();
    }
    function esc_(ev) { if (ev.key === "Escape") close(); }
    document.addEventListener("keydown", esc_);
    ov.addEventListener("click", function (ev) { if (ev.target === ov || ev.target.closest("[data-close]")) close(); });
    function save(fn) { var mm = S.meta(); fn(mm); S.saveMeta(mm); }
    $(ov, "#fc-perday").addEventListener("change", function () { var v = clampInt(this.value, 0, 100, 10); this.value = v; save(function (mm) { mm.perDay = v; }); intro(); });
    $(ov, "[data-cap]").addEventListener("change", function () { var v = clampInt(this.value, 1, 999, 40); this.value = v; save(function (mm) { mm.cap = v; }); intro(); });
    $(ov, "[data-capon]").addEventListener("change", function () { var on = this.checked; save(function (mm) { mm.capOn = on; }); intro(); });
    $(ov, "[data-df]").addEventListener("change", function () { var on = this.checked; save(function (mm) { mm.defFirst = on; }); });
    var an = $(ov, "[data-addnow]");
    if (an) an.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var w = waitingIds(S.cards()), n = clampInt($(an, "input").value, 1, w.length, 10);
      var k = moveToDaily(w.slice(0, n));
      $(ov, "[data-addmsg]").textContent = "Added " + plural(k, "card") + " to Study daily.";
    });
    var sea = $(ov, "[data-season]");
    var seaHtml = sea.innerHTML;
    sea.addEventListener("click", function (ev) {
      if (ev.target.closest("[data-pausecancel]")) { sea.innerHTML = seaHtml; return; }
      if (ev.target.closest("[data-pauseask]")) {
        sea.innerHTML = '<h3>Pause until next season?</h3><p>Everything stays exactly where it is while you’re away:</p>' +
          "<ul><li>Your " + plural(curStreak(S.meta()), "day") + " streak is frozen, not lost.</li><li>No cards come due, so nothing piles up.</li>" +
          "<li>Your boxes, custom sets and weekly and monthly progress are kept.</li></ul><p class=\"muted\">Come back any time and press Resume.</p>" +
          '<p class="fc-row"><button type="button" class="btn btn-study btn-sm" data-pausego>Pause flashcards</button><button type="button" class="fc-btn" data-pausecancel>Cancel</button></p>';
        $(sea, "[data-pausego]").focus();
      } else if (ev.target.closest("[data-pausego]")) { pause(); close(); }
      else if (ev.target.closest("[data-resume]")) { resume(); close(); }
    });
    $(ov, "[data-close]").focus();
  }

  // ---------------------------------------------------------------- Flashcards home
  function home(root) {
    intro();
    siteMeta().then(function (sm) { draw(sm); });
    var sel = { c: [], s: [], all: false }, minApps = "", boxes = { 0: false, 1: true, 2: true, 3: true, 4: false, 5: false }, dueOnly = false, kinds = { t: true, a: true, w: true, p: true };
    var topKind = "t", topN = 20, matched = [];

    function draw(sm) {
      var c = S.cards(), m = S.meta(), t = today(), p = plan(c, m, t), bs = boxStats(c, t), wait = bs[0];
      var html = "";
      if (m.paused != null) {
        html += '<section class="fc-today paused"><div class="fc-paused-row"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>' +
          '<div><p class="fc-today-n">Paused for the off-season</p><p class="muted">Since ' + dateLabel(m.paused) + " · " + plural(curStreak(m), "day") + " streak and " + plural(Object.keys(c).length, "card") + " saved</p></div>" +
          '<button type="button" class="btn btn-study" data-resume>Resume studying</button></div>' +
          '<p class="muted fc-small">You can still add cards and make custom sets while paused.</p></section>';
      } else {
        var n = p.today.length;
        html += '<section class="fc-today"><button type="button" class="fc-gear" data-settings aria-label="Flashcard settings">' + GEAR + "</button>" +
          '<div class="fc-today-head"><p class="fc-today-n">' + (n ? plural(n, "card") + " today" : Object.keys(c).length ? "All done for today" : "Start your flashcards") + "</p>" + streakBadge(m) + "</div>";
        if (Object.keys(c).length) {
          html += '<div class="fc-boxes">' +
            boxLine("Daily", bs[1][0] ? (bs[1][1] ? bs[1][1] + " due" : "all done") : "empty", bs[1][0] ? 1 - bs[1][1] / bs[1][0] : 0) +
            boxLine("Weekly", bs[2][0] ? (bs[2][0] - bs[2][1]) + " of " + bs[2][0] + " this week" : "empty", bs[2][0] ? 1 - bs[2][1] / bs[2][0] : 0) +
            boxLine("Monthly", bs[3][0] ? (bs[3][0] - bs[3][1]) + " of " + bs[3][0] + " this month" : "empty", bs[3][0] ? 1 - bs[3][1] / bs[3][0] : 0) + "</div>";
        }
        if (!bs[1][0]) html += topOffer(sm, c, Object.keys(c).length > 0);
        var extras = [];
        if (wait) extras.push(plural(wait, "new card") + ' waiting · <button type="button" class="fc-link" data-settings>add some now</button>');
        if (bs[4]) extras.push(bs[4] + ' mastered · <a href="' + url("flashcards/study/", { b: 4 }) + '">review</a>');
        html += '<div class="fc-today-go">' +
          (n ? '<a class="btn btn-study" href="' + url("flashcards/review/") + '">Start studying</a>' :
            p.more.length ? '<a class="btn btn-study" href="' + url("flashcards/review/", { more: 1 }) + '">Get ahead: ' + plural(p.more.length, "more card") + "</a>" : "") +
          (extras.length ? '<span class="muted">' + extras.join(" &nbsp;·&nbsp; ") + "</span>" : "") + "</div></section>";
      }
      html += builder(sm, c);
      html += myCats(c);
      root.innerHTML = html;
      wire(sm);
    }
    function boxLine(name, stat, frac) {
      return '<div class="fc-boxline"><span><b>' + name + '</b> <span class="muted">· ' + stat + '</span></span><div class="fc-meter"><div style="width:' +
        Math.round(100 * Math.max(0, Math.min(1, frac))) + '%"></div></div></div>';
    }
    function topPick(sm, c) {
      return (sm.top[topKind] || []).filter(function (x) { return !c[x[0]]; }).slice(0, topN);
    }
    function topOffer(sm, c, any) {
      var pick = topPick(sm, c), noun = topKind === "t" ? "term" : "author";
      return '<div class="fc-offer">' +
        (any ? '<p class="fc-offer-sub">Your daily box is empty. Every card has moved up' + (plan(c, S.meta(), today()).today.length ? ", but you still have weekly or monthly cards for today." : ".") + "</p>" : "") +
        '<p class="fc-offer-h">Add the most-tested cards you don’t have yet</p>' +
        '<div class="fc-row"><label for="fc-topn">Add the</label><input id="fc-topn" class="fc-num" type="number" min="1" max="100" value="' + topN + '" data-topn>' +
        '<span>most-tested</span><select aria-label="Kind of card" data-topkind><option value="t"' + (topKind === "t" ? " selected" : "") + '>terms</option><option value="a"' + (topKind === "a" ? " selected" : "") + ">authors</option></select></div>" +
        '<p class="muted fc-small">Ranked by how often each ' + noun + " has appeared on UIL tests. Anything already in your flashcards is skipped.</p>" +
        (pick.length ? '<div class="fc-chips">' + pick.slice(0, 10).map(function (x) { return '<span class="fc-tag set">' + esc(x[1]) + "</span>"; }).join("") +
          (pick.length > 10 ? '<span class="fc-tag set fc-tag-more">+ ' + (pick.length - 10) + " more</span>" : "") + "</div>" +
          '<p class="fc-row"><button type="button" class="btn btn-study" data-topgo>Add ' + plural(pick.length, noun) + ' to Study daily</button><a href="' + BASE + 'flashcards/add/">Choose cards myself</a></p>' +
          '<p class="muted fc-small">They start today and go in a custom set called “Most-tested ' + noun + "s.”</p>"
          : '<p class="muted">You already have every tested ' + noun + ".</p>") + "</div>";
    }

    function scopeIds(sm) { return scopeOf(sel.c, sel.s, sel.all && sel.c.length + sel.s.length > 1, sm); }
    function builder(sm, c) {
      var cats = Cats.sorted();
      var chips = sel.c.map(function (k) { var g = S.cats()[k]; return g ? '<button type="button" class="fc-tag on" data-unsel="c:' + esc(k) + '" aria-label="Remove ' + esc(g.n) + '">' + esc(g.n) + ' <span aria-hidden="true">×</span></button>' : ""; }).join("") +
        sel.s.map(function (s) { return sm.sets[s] ? '<button type="button" class="fc-tag on" data-unsel="s:' + esc(s) + '" aria-label="Remove ' + esc(sm.sets[s][0]) + '">Set: ' + esc(sm.sets[s][0]) + ' <span aria-hidden="true">×</span></button>' : ""; }).join("");
      var quick = cats.filter(function (x) { return sel.c.indexOf(x.id) < 0; }).slice(0, 8)
        .map(function (x) { return '<button type="button" class="fc-tag add" data-sel="c:' + esc(x.id) + '">+ ' + esc(x.cat.n) + "</button>"; }).join("");
      var bc = function (b, name) { return '<label class="fc-check' + (boxes[b] ? " on" : "") + '"><input type="checkbox" data-box="' + b + '"' + (boxes[b] ? " checked" : "") + "> " + (name || SHORT[b]) + ' <span class="muted" data-bc="' + b + '"></span></label>'; };
      return '<section class="block fc-builder"><h2>Make a custom set</h2><div class="fc-builder-box">' +
        '<p class="fc-builder-lede">Choose cards, then save them as a set you can come back to, or just study them now.</p>' +
        '<div class="fc-step"><label class="fc-step-h" for="fc-scope">1. Start from</label>' +
        '<div class="fc-search"><input id="fc-scope" autocomplete="off" placeholder="Search your custom sets and the site’s sets…" data-scopeq><div class="fc-sugg" data-sugg hidden></div></div>' +
        (chips ? '<div class="fc-chips">' + chips + "</div>" : "") +
        (sel.c.length + sel.s.length > 1 ? '<div class="fc-combine" role="radiogroup" aria-label="Combine the sets"><span class="fc-combine-h">Combine them:</span>' +
          '<label class="fc-check' + (sel.all ? "" : " on") + '"><input type="radio" name="fc-mode" value="any" data-mode' + (sel.all ? "" : " checked") + '> <span>Cards in <b>any</b> of these <span class="muted">(union)</span></span></label>' +
          '<label class="fc-check' + (sel.all ? " on" : "") + '"><input type="radio" name="fc-mode" value="all" data-mode' + (sel.all ? " checked" : "") + '> <span>Only cards in <b>all</b> of these <span class="muted">(intersection)</span></span></label></div>' : "") +
        (quick ? '<div class="fc-chips quick"><span class="muted">Your custom sets:</span>' + quick + "</div>" : "") +
        '<span class="muted fc-small">Pick one or more of your custom sets or the site’s sets, or nothing to use all your flashcards.</span></div>' +
        '<div class="fc-step"><span class="fc-step-h">2. Which boxes?</span><div class="fc-checks">' + bc(1) + bc(2) + bc(3) + bc(4) + bc(0, "Waiting line") + bc(5, "Not in my boxes") + "</div>" +
        '<span class="muted fc-small">Waiting line and Not in my boxes are practice only: studying them doesn’t move them into a box. Not in my boxes needs a set from step 1.</span></div>' +
        '<div class="fc-step fc-step-inline"><span class="fc-step-h">3. Card types</span>' + "tawp".split("").map(function (l) {
          return '<label class="fc-row"><input type="checkbox" data-kind="' + l + '"' + (kinds[l] ? " checked" : "") + "> " + KINDS[l] + "</label>";
        }).join("") + "</div>" +
        '<div class="fc-step"><div class="fc-step-inline"><label class="fc-step-h" for="fc-apps">4. Test appearances</label>' +
        '<span class="fc-row">At least <input id="fc-apps" class="fc-num" type="number" min="0" max="999" step="1" inputmode="numeric" placeholder="any" value="' + esc(minApps) + '" data-apps aria-label="Minimum test appearances"> appearances</span></div>' +
        '<span class="muted fc-small">How often a term, author or work has come up on released UIL tests. Leave it blank for any. Prizes are left out when a number is set.</span></div>' +
        '<div class="fc-builder-go"><span data-summary></span><button type="button" class="fc-btn" data-savecat>Save as new set</button><a class="btn btn-study btn-sm" data-go href="#">Study without saving</a></div>' +
        '<p class="fc-ok fc-small" data-savemsg aria-live="polite"></p></div></section>';
    }
    function recount(sm) {
      var c = S.cards(), t = today(), scope = scopeIds(sm);
      var f = { b: [0, 1, 2, 3, 4, 5].filter(function (b) { return boxes[b]; }), k: "tawp".split("").filter(function (l) { return kinds[l]; }), d: dueOnly };
      var per = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 }, n = 0;
      var ids = Object.keys(c);
      if (scope) Object.keys(scope).forEach(function (id) { if (!c[id]) ids.push(id); });
      matched = [];
      ids.forEach(function (id) {
        var st = c[id], b = st ? st[0] : 5;
        if ((scope && !scope[id]) || f.k.indexOf(id[0]) < 0) return;
        if (!appsOK(id, +minApps, sm)) return;
        if (dueOnly && b >= 1 && b <= 4 && !isDue(st, t)) return;
        per[b]++;
        if (f.b.indexOf(b) >= 0) { n++; matched.push(id); }
      });
      [0, 1, 2, 3, 4, 5].forEach(function (b) { var s = $(root, '[data-bc="' + b + '"]'); if (s) s.textContent = per[b]; });
      var names = sel.c.map(function (k) { var g = S.cats()[k]; return g ? g.n : ""; }).filter(Boolean)
        .concat(sel.s.map(function (s) { return sm.sets[s] ? sm.sets[s][0] : ""; }).filter(Boolean));
      var both = sel.all && sel.c.length + sel.s.length > 1;
      var sum = $(root, "[data-summary]"), go = $(root, "[data-go]");
      if (!sum) return;
      sum.innerHTML = "<b>" + plural(n, "card") + "</b>" + (dueOnly && !boxes[0] && !boxes[5] ? " due now" : "") + (names.length ? (both ? " in all of " : " from ") + names.map(function (x) { return "<b>" + esc(x) + "</b>"; }).join(both ? " and " : ", ") : "");
      go.textContent = n ? "Study without saving" : "No cards to study";
      var sv = $(root, "[data-savecat]"); if (sv) sv.disabled = !n;
      go.classList.toggle("disabled", !n);
      go.setAttribute("aria-disabled", n ? "false" : "true");
      go.href = url("flashcards/study/", { c: sel.c.join(","), s: sel.s.join(","), m: both ? "all" : "", a: minApps, b: f.b.join(""), d: dueOnly ? 1 : 0, k: f.k.length === 4 ? "" : f.k.join("") });
    }
    function myCats(c) {
      var list = Cats.sorted();
      return '<section class="block fc-mycats"><div class="fc-h2row"><h2>My custom sets</h2><button type="button" class="fc-link" data-newcat>+ New set</button></div>' +
        (list.length ? '<ul class="fc-list-rows">' + list.map(function (x) {
          var n = x.cat.c.length;
          return '<li><a href="' + url("flashcards/study/", { c: x.id, b: ALLB }) + '">' + esc(x.cat.n) + '</a><span class="muted">' + plural(n, "card") +
            ' · <a href="' + url("flashcards/my/", { d: x.id }) + '" aria-label="Edit ' + esc(x.cat.n) + '">Edit</a></span></li>';
        }).join("") + '</ul><p class="muted fc-small">Click a name to study it.</p>'
          : '<p class="muted">Your own labels for cards: “Region week,” “Hard ones,” anything. Add cards to them from the <b>Add to flashcards</b> button on any term, author, work or prize page, while you study, or make one under <b>Make a custom set</b>. Cards in a custom set aren’t scheduled until you add them to your flashcards.</p>') +
        "</section>";
    }

    // Every control on the page is handled here once, by delegation, since draw() replaces the HTML.
    var smRef = null;
    siteMeta().then(function (sm) { smRef = sm; });
    root.addEventListener("click", function (ev) {
      var sm = smRef; if (!sm) return;
      var t = ev.target;
      if (t.closest("[data-settings]")) { openSettings(); return; }
      if (t.closest("[data-resume]")) { resume(); intro(); draw(sm); return; }
      if (t.closest("[data-topgo]")) {
        var ids = topPick(sm, S.cards()).map(function (x) { return x[0]; });
        addCards(ids, "top", "daily");
        Cats.addMany(Cats.byName(topKind === "t" ? "Most-tested terms" : "Most-tested authors"), ids);
        draw(sm); return;
      }
      if (t.closest("[data-savecat]")) {
        if (!matched.length) return;
        var def = sel.c.map(function (k) { var g = S.cats()[k]; return g ? g.n : ""; }).concat(sel.s.map(function (s) { return sm.sets[s] ? sm.sets[s][0] : ""; })).filter(Boolean).join(sel.all && sel.c.length + sel.s.length > 1 ? " ∩ " : " + ");
        var nm = askName(def); if (!nm) return;
        var cid = Cats.create(nm), saved = matched.slice();
        Cats.addMany(cid, saved);
        draw(sm);
        var msg = $(root, "[data-savemsg]");
        if (msg) msg.innerHTML = "Saved “" + esc(nm) + "” with " + plural(saved.length, "card") + ". It’s under My custom sets; its cards aren’t added to your boxes or waiting line. " +
          '<a href="' + url("flashcards/study/", { c: cid, b: ALLB }) + '">Study it now</a> · <a href="' + url("flashcards/my/", { d: cid }) + '">See the set</a>';
        return;
      }
      if (t.closest("[data-newcat]")) {
        var n = askName(""); if (!n) return;
        location.href = url("flashcards/my/", { d: Cats.create(n) }); return;
      }
      var s = t.closest("[data-sel]"), u = t.closest("[data-unsel]");
      if (s) { var v = s.getAttribute("data-sel"); (v[0] === "c" ? sel.c : sel.s).push(v.slice(2)); redrawKeep(sm, true); return; }
      if (u) { var w = u.getAttribute("data-unsel"), arr = w[0] === "c" ? sel.c : sel.s, i = arr.indexOf(w.slice(2)); if (i >= 0) arr.splice(i, 1); redrawKeep(sm, false); return; }
      var go = t.closest("[data-go]");
      if (go && go.classList.contains("disabled")) ev.preventDefault();
    });
    root.addEventListener("change", function (ev) {
      var sm = smRef, tg = ev.target; if (!sm) return;
      if (tg.hasAttribute("data-topn")) { topN = clampInt(tg.value, 1, 100, 20); draw(sm); return; }
      if (tg.hasAttribute("data-topkind")) { topKind = tg.value; draw(sm); return; }
      if (tg.hasAttribute("data-mode")) {
        sel.all = tg.value === "all";
        $$(root, "[data-mode]").forEach(function (r) { r.parentNode.classList.toggle("on", r.checked); });
      } else if (tg.hasAttribute("data-box")) { boxes[tg.getAttribute("data-box")] = tg.checked; tg.parentNode.classList.toggle("on", tg.checked); }
      else if (tg.hasAttribute("data-kind")) kinds[tg.getAttribute("data-kind")] = tg.checked;
      else if (tg.hasAttribute("data-apps")) { var v = parseInt(tg.value, 10); minApps = v > 0 ? String(Math.min(v, 999)) : ""; tg.value = minApps; }
      else return;
      recount(sm);
    });
    function options(sm, q) {
      var term = q.value.trim().toLowerCase();
      var o = Cats.sorted().filter(function (x) { return sel.c.indexOf(x.id) < 0; }).map(function (x) { return ["c:" + x.id, x.cat.n, "Your custom set"]; })
        .concat(sm.core.filter(function (s) { return sm.sets[s] && sel.s.indexOf(s) < 0; })
          .concat(Object.keys(sm.sets).filter(function (s) { return sel.s.indexOf(s) < 0 && sm.core.indexOf(s) < 0; })
            .sort(function (x, y) { return sm.sets[x][0].localeCompare(sm.sets[y][0]); }))
          .map(function (s) { var ids = sm.sets[s][1], L = ids.length && ids[0][0];
            return ["s:" + s, sm.sets[s][0], "Set · " + plural(ids.length, L ? KIND[L].toLowerCase() : "card")]; }));
      if (term) o = o.filter(function (x) { return x[1].toLowerCase().indexOf(term) >= 0; });
      return o;
    }
    function showSugg() {
      var q = $(root, "[data-scopeq]"), sugg = $(root, "[data-sugg]"); if (!q || !sugg || !smRef) return;
      var o = options(smRef, q);
      sugg.innerHTML = o.length ? o.map(function (x) { return '<button type="button" data-sel="' + esc(x[0]) + '"><span>' + esc(x[1]) + "</span><small>" + esc(x[2]) + "</small></button>"; }).join("")
        : '<p class="muted">No sets match.</p>';
      sugg.hidden = false;
    }
    root.addEventListener("input", function (ev) {
      if (ev.target.hasAttribute("data-scopeq")) showSugg();
      else if (ev.target.hasAttribute("data-apps") && smRef) { var v = parseInt(ev.target.value, 10); minApps = v > 0 ? String(Math.min(v, 999)) : ""; recount(smRef); }
    });
    root.addEventListener("focusin", function (ev) { if (ev.target.hasAttribute && ev.target.hasAttribute("data-scopeq")) showSugg(); });
    root.addEventListener("keydown", function (ev) {
      var opt = ev.target.closest && ev.target.closest("[data-sugg] [data-sel]");
      if (opt && (ev.key === "ArrowDown" || ev.key === "ArrowUp")) {
        ev.preventDefault();
        var all = [].slice.call(opt.parentNode.querySelectorAll("[data-sel]")), i = all.indexOf(opt) + (ev.key === "ArrowDown" ? 1 : -1);
        if (i < 0) $(root, "[data-scopeq]").focus(); else if (all[i]) all[i].focus();
        return;
      }
      if (opt && ev.key === "Escape") { opt.parentNode.hidden = true; $(root, "[data-scopeq]").focus(); return; }
      if (!ev.target.hasAttribute || !ev.target.hasAttribute("data-scopeq")) return;
      var sugg = $(root, "[data-sugg]");
      if (ev.key === "Enter") { ev.preventDefault(); var f = $(sugg, "[data-sel]"); if (f) f.click(); }
      if (ev.key === "ArrowDown") { ev.preventDefault(); var b = $(sugg, "[data-sel]"); if (b) b.focus(); }
      if (ev.key === "Escape") sugg.hidden = true;
    });
    document.addEventListener("click", function (ev) {
      var sugg = $(root, "[data-sugg]");
      if (sugg && !(ev.target.closest && ev.target.closest(".fc-search"))) sugg.hidden = true;
    });
    function wire(sm) { if ($(root, "[data-go]")) recount(sm); }
    function redrawKeep(sm, focus) {
      var y = window.scrollY;
      draw(sm);
      window.scrollTo(0, y);
      if (focus) { var q = $(root, "[data-scopeq]"); if (q) q.focus({ preventScroll: true }); }
    }
    function openSettings() { settings(function () { intro(); if (smRef) draw(smRef); }); }
    return { settings: openSettings };
  }

  // ---------------------------------------------------------------- category page (/flashcards/my/?d=)
  function catPage(root) {
    var id = new URLSearchParams(location.search).get("d"), g = S.cats()[id];
    var h1 = document.querySelector("main h1"), lede = document.querySelector("main .lede");
    if (!g) {
      h1.textContent = "Set not found";
      lede.textContent = "";
      root.innerHTML = '<p>This set isn’t in this browser or your account. <a href="' + BASE + 'flashcards/">See your flashcards</a></p>';
      return;
    }
    document.title = g.n + " · " + document.title.split(" · ").slice(1).join(" · ");
    h1.textContent = g.n;
    root.innerHTML = '<p class="muted">Loading cards…</p>';
    cardsFor(lettersOf(g.c)).then(function (data) {
      function draw() {
        var gg = S.cats()[id], c = S.cards(), t = today();
        if (!gg) { location.href = BASE + "flashcards/"; return; }
        var ids = gg.c.filter(function (x) { return data[x]; }).sort(function (x, y) { return data[x][0].localeCompare(data[y][0], undefined, { sensitivity: "base" }); });
        var due = ids.filter(function (x) { return c[x] && isDue(c[x], t); }).length;
        var out = ids.filter(function (x) { return !c[x]; });
        lede.innerHTML = plural(ids.length, "card") + (due ? " · " + due + " due now" : "") +
          ' · <button type="button" class="fc-link" data-ren>Rename</button> · <button type="button" class="fc-link warn" data-del>Delete set</button>';
        root.innerHTML = '<p class="fc-row"><a class="btn btn-study" href="' + url("flashcards/study/", { c: id, b: ALLB }) + '">Study this set</a>' +
          (due ? '<a class="fc-btn" href="' + url("flashcards/study/", { c: id, d: 1 }) + '">Only the ' + due + " due now</a>" : "") + "</p>" +
          (out.length ? '<div class="fc-addall"><button type="button" class="btn btn-study btn-sm" data-catadd="end">+ Add ' + (out.length === ids.length ? (out.length === 1 ? "it" : "all " + out.length) : "the other " + out.length) +
            " to my flashcards</button>" + '<button type="button" class="fc-btn" data-catadd="daily">Start ' + (out.length === 1 ? "it" : "them") + " today</button>" +
            '<span class="fc-addall-note">' + plural(out.length, "card isn’t", "cards aren’t") + " in your flashcards, so " + (out.length === 1 ? "it’s" : "they’re") +
            " practice only. Adding puts them in the waiting line; “Start today” puts them in Study daily.</span></div>" : "") +
          (ids.length ? '<ul class="fc-list-rows">' + ids.map(function (x) {
            return '<li><span><a href="' + BASE + data[x][2] + '">' + esc(data[x][0]) + '</a> <span class="muted">· ' + KIND[x[0]] + "</span></span>" +
              '<span class="muted">' + (c[x] ? (c[x][0] === 0 ? "Waiting" : BOX[c[x][0]]) : "Not in your flashcards") +
              ' <button type="button" class="fc-link" data-rm="' + esc(x) + '">Remove</button></span></li>';
          }).join("") + "</ul>"
            : '<p class="muted">This set is empty. Use <b>Add to flashcards</b> on any term, author, work or prize page, or “+ Custom set” while you study.</p>');
        $$(root, "[data-catadd]").forEach(function (b) { b.addEventListener("click", function () { addCards(out, "cat:" + id, b.getAttribute("data-catadd")); draw(); }); });
        $$(root, "[data-rm]").forEach(function (b) { b.addEventListener("click", function () { Cats.set(id, b.getAttribute("data-rm"), false); draw(); }); });
        $(lede, "[data-ren]").addEventListener("click", function () { var n = askName(gg.n); if (n) { Cats.rename(id, n); h1.textContent = n; draw(); } });
        $(lede, "[data-del]").addEventListener("click", function () {
          if (window.confirm("Delete “" + gg.n + "”? Only the set goes; cards in your flashcards stay there.")) { Cats.remove(id); location.href = BASE + "flashcards/"; }
        });
      }
      draw();
    });
  }

  // ---------------------------------------------------------------- waiting line (/flashcards/waiting/)
  function waitingPage(root) {
    root.innerHTML = '<p class="muted">Loading your waiting cards…</p>';
    var shown = 50, picked = {}, f = { q: "", k: "", src: "", app: "" }, dragId = null, data = {}, sm = null;
    Promise.all([siteMeta(), cardsFor(lettersOf(waitingIds(S.cards())))]).then(function (r) { sm = r[0]; data = r[1]; frame(); });

    function frame() {
      var m = S.meta();
      root.innerHTML =
        '<p class="lede" data-wlede></p>' +
        '<form class="fc-addline" data-addform><label for="fc-addq">Add to the line</label><div class="fc-search"><input id="fc-addq" autocomplete="off" placeholder="A term, author, work, prize, or a whole set…" data-addq><div class="fc-sugg" data-addsugg hidden></div></div>' +
        '<select aria-label="Where to add" data-where><option value="end">at the end</option><option value="front">at the front</option></select></form>' +
        '<p class="fc-ok" data-addmsg aria-live="polite"></p>' +
        '<div class="fc-filters"><input type="search" placeholder="Search…" aria-label="Search waiting cards" data-fq>' +
        '<select aria-label="Kind" data-fk><option value="">All kinds</option><option value="t">Terms</option><option value="a">Authors</option><option value="w">Works</option><option value="p">Prizes</option></select>' +
        '<select aria-label="Where they came from" data-fs></select>' +
        '<select aria-label="Test appearances" data-fa><option value="">Any test appearances</option><option value="50">50 or more</option><option value="20">20 or more</option><option value="1">At least once</option><option value="0">Never on a test</option></select></div>' +
        '<div class="fc-row fc-reorder"><span class="muted">Reorder the whole line:</span><select aria-label="Reorder by" data-ro><option value="apps">Most tested first</option><option value="az">A–Z</option><option value="t">Terms first</option><option value="a">Authors first</option><option value="old">Oldest added first</option><option value="new">Newest added first</option><option value="mix">Shuffle</option></select><button type="button" class="fc-btn" data-rogo>Reorder</button></div>' +
        '<div class="fc-wl"><div class="fc-bulk" data-bulk hidden><span data-bulkn></span>' +
        '<button type="button" class="fc-btn small" data-b="front">Move to front</button><button type="button" class="fc-btn small" data-b="end">Move to end</button>' +
        '<button type="button" class="fc-btn small" data-b="daily">Add to Study daily now</button><span class="fc-add-box"><button type="button" class="fc-btn small" data-b="cat">Add to a custom set…</button><span class="fc-pop" data-catpop></span></span>' +
        '<button type="button" class="fc-btn small warn" data-b="remove">Remove</button></div>' +
        '<div class="fc-wl-head"><input type="checkbox" aria-label="Select all shown" data-all><span></span><span class="pos">#</span><span>Card</span><span>Kind</span><span>From</span><span class="ap">On tests</span><span></span></div>' +
        '<ol class="fc-wl-list" data-list></ol><p class="fc-wl-more" data-more></p></div>' +
        '<p class="muted fc-small">Removing a card only takes it out of the line. You can add it again any time. New cards join Study daily ' + m.perDay + ' a day; change that in <a href="' + BASE + 'flashcards/#settings">settings</a>.</p>';
      wire();
      list();
    }
    function apps(id) { return sm.apps[id] || 0; }
    function name(id) { return data[id] ? data[id][0] : id; }
    function visible() {
      var c = S.cards(), ids = waitingIds(c), q = f.q.toLowerCase();
      return ids.filter(function (id) {
        if (f.k && id[0] !== f.k) return false;
        if (f.src && (c[id][4] || "") !== f.src) return false;
        if (f.app !== "") { var a = apps(id), n = +f.app; if (n === 0 ? a > 0 : a < n) return false; }
        if (q && name(id).toLowerCase().indexOf(q) < 0) return false;
        return true;
      });
    }
    function list() {
      var c = S.cards(), all = waitingIds(c), vis = visible(), pos = {};
      all.forEach(function (id, i) { pos[id] = i + 1; });
      var srcs = {}; all.forEach(function (id) { srcs[c[id][4] || ""] = 1; });
      var fs = $(root, "[data-fs]");
      fs.innerHTML = '<option value="">From anywhere</option>' + Object.keys(srcs).map(function (s) {
        return '<option value="' + esc(s) + '"' + (f.src === s ? " selected" : "") + ">" + esc(srcLabel(s, sm)) + "</option>";
      }).join("");
      var m = S.meta();
      $(root, "[data-wlede]").textContent = all.length
        ? "These " + plural(all.length, "card") + " join Study daily in this order, " + m.perDay + " a day" + (m.perDay ? " (about " + plural(Math.ceil(all.length / m.perDay), "day") + ")" : "") + ". Drag a card or use the arrows to move it."
        : "No cards are waiting. Add some below, or from any set or ready-made deck.";
      Object.keys(picked).forEach(function (id) { if (!c[id] || c[id][0] !== 0) delete picked[id]; });
      var rows = vis.slice(0, shown).map(function (id) {
        var d = data[id], a = apps(id);
        return '<li class="fc-wl-row' + (picked[id] ? " on" : "") + '" draggable="true" data-id="' + esc(id) + '">' +
          '<input type="checkbox" aria-label="Select ' + esc(name(id)) + '"' + (picked[id] ? " checked" : "") + ' data-pick>' +
          '<span class="grip" aria-hidden="true">⋮⋮</span><span class="pos">' + pos[id] + "</span>" +
          '<span class="nm">' + (d ? '<a href="' + BASE + d[2] + '">' + esc(d[0]) + "</a>" : esc(id)) + "</span>" +
          '<span class="kd">' + KIND[id[0]] + '</span><span class="fr">' + esc(srcLabel(c[id][4], sm)) + '</span><span class="ap">' + (a || "—") + "</span>" +
          '<span class="mv"><button type="button" data-mv="up" aria-label="Move ' + esc(name(id)) + ' up">↑</button><button type="button" data-mv="down" aria-label="Move ' + esc(name(id)) + ' down">↓</button>' +
          '<button type="button" data-mv="x" aria-label="Remove ' + esc(name(id)) + '">×</button></span></li>';
      }).join("");
      $(root, "[data-list]").innerHTML = rows || '<li class="fc-wl-empty muted">' + (all.length ? "No waiting cards match these filters." : "Nothing waiting.") + "</li>";
      $(root, "[data-more]").innerHTML = vis.length > shown ? '<button type="button" class="fc-link" data-showmore>Show the next ' + Math.min(50, vis.length - shown) + " (" + (vis.length - shown) + " more)</button>" : "";
      var n = Object.keys(picked).length;
      $(root, "[data-bulk]").hidden = !n;
      $(root, "[data-bulkn]").textContent = n + " selected";
      var al = $(root, "[data-all]");
      al.checked = vis.length > 0 && vis.every(function (id) { return picked[id]; });
      al.setAttribute("aria-label", "Select all " + vis.length + " shown");
    }
    function setOrder(ids) {
      var c = S.cards();
      ids.forEach(function (id, i) { if (c[id]) c[id][3] = i + 1; });
      S.saveCards(c);
    }
    function move(id, delta) {
      var ids = waitingIds(S.cards()), i = ids.indexOf(id), j = i + delta;
      if (i < 0 || j < 0 || j >= ids.length) return;
      ids.splice(i, 1); ids.splice(j, 0, id);
      setOrder(ids);
    }
    function moveMany(sel, toFront) {
      var ids = waitingIds(S.cards()), rest = ids.filter(function (x) { return !sel[x]; }), mine = ids.filter(function (x) { return sel[x]; });
      setOrder(toFront ? mine.concat(rest) : rest.concat(mine));
    }
    function wire() {
      var refilter = function () { shown = 50; list(); };
      $(root, "[data-fq]").addEventListener("input", function () { f.q = this.value.trim(); refilter(); });
      $(root, "[data-fk]").addEventListener("change", function () { f.k = this.value; refilter(); });
      $(root, "[data-fs]").addEventListener("change", function () { f.src = this.value; refilter(); });
      $(root, "[data-fa]").addEventListener("change", function () { f.app = this.value; refilter(); });
      $(root, "[data-rogo]").addEventListener("click", function () {
        var how = $(root, "[data-ro]").value, c = S.cards(), ids = waitingIds(c);
        var key = {
          apps: function (x, y) { return apps(y) - apps(x); },
          az: function (x, y) { return name(x).localeCompare(name(y), undefined, { sensitivity: "base" }); },
          t: function (x, y) { return (x[0] !== "t") - (y[0] !== "t"); },
          a: function (x, y) { return (x[0] !== "a") - (y[0] !== "a"); },
          old: function (x, y) { return (c[x][5] || 0) - (c[y][5] || 0); },
          "new": function (x, y) { return (c[y][5] || 0) - (c[x][5] || 0); }
        }[how];
        if (how === "mix") { var r = {}; ids.forEach(function (x) { r[x] = Math.random(); }); ids.sort(function (x, y) { return r[x] - r[y]; }); }
        else ids = ids.map(function (x, i) { return [x, i]; }).sort(function (p, q) { return key(p[0], q[0]) || p[1] - q[1]; }).map(function (p) { return p[0]; });
        setOrder(ids); list();
      });
      var listEl = $(root, "[data-list]");
      listEl.addEventListener("change", function (ev) {
        var cb = ev.target.closest("[data-pick]"); if (!cb) return;
        var id = cb.closest("[data-id]").getAttribute("data-id");
        if (cb.checked) picked[id] = 1; else delete picked[id];
        list();
      });
      listEl.addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-mv]"); if (!b) return;
        var id = b.closest("[data-id]").getAttribute("data-id"), how = b.getAttribute("data-mv");
        if (how === "x") removeCards([id]); else move(id, how === "up" ? -1 : 1);
        list();
        var again = $(listEl, '[data-id="' + id.replace(/"/g, '\\"') + '"] [data-mv="' + how + '"]'); if (again) again.focus();
      });
      listEl.addEventListener("dragstart", function (ev) {
        var li = ev.target.closest && ev.target.closest("[data-id]"); if (!li) return;
        dragId = li.getAttribute("data-id"); li.classList.add("dragging");
        try { ev.dataTransfer.setData("text/plain", dragId); ev.dataTransfer.effectAllowed = "move"; } catch (e) {}
      });
      listEl.addEventListener("dragover", function (ev) {
        if (!dragId) return; ev.preventDefault();
        $$(listEl, ".drop").forEach(function (x) { x.classList.remove("drop"); });
        var li = ev.target.closest && ev.target.closest("[data-id]"); if (li) li.classList.add("drop");
      });
      listEl.addEventListener("drop", function (ev) {
        ev.preventDefault();
        var li = ev.target.closest && ev.target.closest("[data-id]");
        if (dragId && li) {
          var target = li.getAttribute("data-id"), ids = waitingIds(S.cards());
          if (target !== dragId) { ids.splice(ids.indexOf(dragId), 1); ids.splice(ids.indexOf(target), 0, dragId); setOrder(ids); }
        }
        dragId = null; list();
      });
      listEl.addEventListener("dragend", function () { dragId = null; list(); });
      $(root, "[data-all]").addEventListener("change", function () {
        var on = this.checked; visible().forEach(function (id) { if (on) picked[id] = 1; else delete picked[id]; }); list();
      });
      $(root, "[data-more]").addEventListener("click", function (ev) { if (ev.target.closest("[data-showmore]")) { shown += 50; list(); } });
      var catBtn = $(root, '[data-b="cat"]'), catPop = $(root, "[data-catpop]");
      popover(catBtn, catPop);
      catPop.onopen = function () {
        var lst = Cats.sorted();
        catPop.innerHTML = '<p class="fc-pop-h">Add ' + plural(Object.keys(picked).length, "card") + " to:</p>" +
          lst.map(function (x) { return '<button type="button" class="fc-pop-row btnrow" data-tocat="' + esc(x.id) + '">' + esc(x.cat.n) + "</button>"; }).join("") +
          '<form class="fc-pop-new"><input maxlength="80" placeholder="New set" aria-label="New set name"><button class="fc-btn small" type="submit">Add</button></form>';
      };
      catPop.addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-tocat]"); if (!b) return;
        Cats.addMany(b.getAttribute("data-tocat"), Object.keys(picked));
        catPop.hidden = true; msg("Added to " + b.textContent + ".");
      });
      catPop.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var n = $(catPop, "input").value.replace(/\s+/g, " ").trim().slice(0, 80); if (!n) return;
        Cats.addMany(Cats.create(n), Object.keys(picked));
        catPop.hidden = true; msg("Added to " + n + ".");
      });
      $(root, "[data-bulk]").addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-b]"); if (!b) return;
        var how = b.getAttribute("data-b"), ids = Object.keys(picked);
        if (how === "cat") return;
        if (how === "front" || how === "end") moveMany(picked, how === "front");
        else if (how === "daily") { msg("Added " + plural(moveToDaily(ids), "card") + " to Study daily."); picked = {}; }
        else if (how === "remove") {
          if (!window.confirm("Remove " + plural(ids.length, "card") + " from the waiting line?")) return;
          removeCards(ids); picked = {};
        }
        list();
      });
      // adding cards and sets
      var aq = $(root, "[data-addq]"), as = $(root, "[data-addsugg]"), allData = null;
      function ensureAll() {
        if (!allData) allData = cardsFor(["t", "a", "w", "p"]).then(function (d) { Object.assign(data, d); return d; });
        return allData;
      }
      function sugg() {
        var term = aq.value.trim().toLowerCase();
        if (term.length < 2) { as.hidden = true; return; }
        ensureAll().then(function (d) {
          if (aq.value.trim().toLowerCase() !== term) return;
          var c = S.cards(), out = [];
          Object.keys(sm.sets).forEach(function (s) {
            if (sm.sets[s][0].toLowerCase().indexOf(term) >= 0) out.push(["set:" + s, "Set: " + sm.sets[s][0], sm.sets[s][1].length + " terms", 0]);
          });
          Object.keys(d).forEach(function (id) {
            var n = d[id][0].toLowerCase(), i = n.indexOf(term);
            if (i >= 0) out.push([id, d[id][0], KIND[id[0]] + (c[id] ? " · already in your flashcards" : ""), (i === 0 ? 0 : 1) * 1e6 - apps(id)]);
          });
          out.sort(function (x, y) { return x[3] - y[3]; });
          as.innerHTML = out.slice(0, 10).map(function (x) {
            return '<button type="button" data-addid="' + esc(x[0]) + '"><span>' + esc(x[1]) + "</span><small>" + esc(x[2]) + "</small></button>";
          }).join("") || '<p class="muted">Nothing matches.</p>';
          as.hidden = false;
        });
      }
      aq.addEventListener("input", sugg);
      aq.addEventListener("focus", function () { ensureAll(); });
      aq.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") { ev.preventDefault(); var b = $(as, "[data-addid]"); if (b) b.click(); }
        if (ev.key === "ArrowDown") { ev.preventDefault(); var b2 = $(as, "[data-addid]"); if (b2) b2.focus(); }
        if (ev.key === "Escape") as.hidden = true;
      });
      $(root, "[data-addform]").addEventListener("submit", function (ev) { ev.preventDefault(); });
      as.addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-addid]"); if (!b) return;
        var v = b.getAttribute("data-addid"), where = $(root, "[data-where]").value, n;
        if (v.indexOf("set:") === 0) { var s = v.slice(4); n = addCards(sm.sets[s][1], "set:" + s, where); msg("Added " + plural(n, "card") + " from " + sm.sets[s][0] + "."); }
        else { n = addCards([v], "add", where); msg(n ? "Added " + name(v) + "." : name(v) + " is already in your flashcards."); }
        aq.value = ""; as.hidden = true; aq.focus(); list();
      });
      document.addEventListener("click", function (ev) { if (!ev.target.closest || !ev.target.closest(".fc-addline")) as.hidden = true; });
    }
    function msg(t) { var p = $(root, "[data-addmsg]"); if (p) p.textContent = t; }
  }

  // ---------------------------------------------------------------- Study page tile (/study/)
  function studyTile() {
    var big = document.querySelector("[data-fc-big]"); if (!big) return;
    var c = S.cards(), m = S.meta(), p = plan(c, m, today()), n = p.today.length, sub = document.querySelector("[data-fc-sub]"), go = document.querySelector("[data-fc-go]");
    if (!Object.keys(c).length) return;
    if (m.paused != null) { big.textContent = "Paused"; sub.textContent = "Your flashcards are paused for the off-season."; go.textContent = "Open flashcards"; return; }
    big.textContent = plural(n, "card");
    var s = curStreak(m);
    sub.textContent = (n ? "Your daily cards plus today’s share of weekly and monthly." : "All done for today.") + (s ? " " + s + "-day streak." : "");
    go.textContent = n ? "Start studying" : "Open flashcards";
    go.href = n ? url("flashcards/review/") : BASE + "flashcards/";
  }

  // ---------------------------------------------------------------- start
  window.litcritFlash = { plan: function () { return plan(S.cards(), S.meta(), today()); } };
  onDom(function () {
    (window.litcritReady || Promise.resolve()).then(function () {
      migrate();
      document.querySelectorAll("[data-add-card]").forEach(function (slot) {
        slot.appendChild(addWidget(slot.getAttribute("data-add-card"), slot.getAttribute("data-title")));
        slot.hidden = false;
      });
      document.querySelectorAll("[data-fc-addall]").forEach(addAll);
      document.querySelectorAll(".fc[data-deck]").forEach(player);
      var h = document.querySelector("[data-fc-home]");
      if (h) {
        var hm = home(h);
        if (location.hash === "#settings") hm.settings();
      }
      var cp = document.querySelector("[data-fc-cat]"); if (cp) catPage(cp);
      var wp = document.querySelector("[data-fc-waiting]"); if (wp) waitingPage(wp);
      studyTile();
      var sync = document.querySelector("[data-fc-sync]");
      if (sync) {
        if (signedIn()) sync.textContent = "Your boxes, custom sets and streak are saved to your account.";
        else if (window.litcritAuth && window.litcritAuth.enabled) {
          sync.innerHTML = 'Your boxes, custom sets and streak are saved in this browser. <a href="' + BASE + "account/?next=" + encodeURIComponent(location.pathname) + '">Sign in</a> to keep them on every device.';
        }
      }
    });
  });
})();
