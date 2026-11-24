/*
 * Accounts (Supabase): optional sign-in that saves practice answers, scored pages, test scores,
 * the flashcard schedule, custom flashcard decks and essays
 * to the visitor's account, so they follow them between browsers and devices.
 *
 * Guests: nothing changes; progress stays in this browser (localStorage), and the Supabase library
 * is never loaded.
 * Signed in: on each page load, before the quiz scripts start (window.litcritReady), the saved
 * progress is pulled from the account; every change the quiz scripts make to localStorage is pushed
 * back a moment later. Signing in when both this browser (as a guest) and the account hold progress
 * asks which copy to keep, with a side-by-side comparison (choose); if only one has progress, it is used.
 * Signing out clears this browser's copy.
 *
 * Settings come from the page: window.LITCRIT_AUTH = {url, key, lib}.
 */
(function () {
  var cfg = window.LITCRIT_AUTH || {};
  var KEYS = { answers: "litcrit-answers-v1", scored: "litcrit-scored-v1", scores: "litcrit-test-scores-v1",
               cards: "litcrit-cards-v1", decks: "litcrit-decks-v1", quiz: "litcrit-quiz-v1", last: "litcrit-last-v1",
               fcCards: "litcrit-fc-cards-v2", fcCats: "litcrit-fc-cats-v2", fcMeta: "litcrit-fc-meta-v2",
               essays: "litcrit-essays-v1", mock: "litcrit-mock-v1", mockAttempts: "litcrit-mock-attempts-v1",
               mockEssays: "litcrit-mock-essays-v1" };
  var META = "litcrit-sync-v1";          // {uid, dirty}: whose progress this browser holds, and unsaved changes
  var SESSION = "litcrit-auth";          // where the Supabase library keeps the session
  var BASE = window.SITE_BASE || "/";
  var enabled = !!(cfg.url && cfg.key);

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  var rawSet = Storage.prototype.setItem, rawRemove = Storage.prototype.removeItem;
  function put(k, v) { try { rawSet.call(localStorage, k, v); } catch (e) {} }
  function drop(k) { try { rawRemove.call(localStorage, k); } catch (e) {} }
  function json(k) { try { return JSON.parse(get(k)) || {}; } catch (e) { return {}; } }
  function meta() { return json(META); }
  function setMeta(m) { put(META, JSON.stringify(m)); }

  function storedUser() {
    try { var s = JSON.parse(get(SESSION)); return s && s.user ? s.user : null; } catch (e) { return null; }
  }
  function localData() { var d = {}; Object.keys(KEYS).forEach(function (k) { d[k] = json(KEYS[k]); }); return d; }
  function writeLocal(d) {
    Object.keys(KEYS).forEach(function (k) { put(KEYS[k], JSON.stringify((d && d[k]) || {})); });
  }
  function isEmpty(d) { return Object.keys(KEYS).every(function (k) { return !Object.keys(d[k] || {}).length; }); }
  function merge(remote, local) {     // local wins where both have an entry (essays: the newer draft wins)
    var out = {};
    Object.keys(KEYS).forEach(function (k) { out[k] = Object.assign({}, (remote && remote[k]) || {}, local[k] || {}); });
    // Flashcard settings and streak: the account's copy wins. Signing out leaves this browser as a guest,
    // and any flashcard page then saves default settings and an empty streak; letting those win wiped the
    // account's streak on the next sign-in (Nov 23, 2026). A guest streak is kept only if it's longer.
    var rm = (remote && remote.fcMeta) || {}, lm = local.fcMeta || {};
    out.fcMeta = Object.assign({}, Object.keys(rm).length ? rm : lm);
    var rs = rm.streak, ls = lm.streak;
    if (rs || ls) {
      var s = Object.assign({}, rs && (!ls || (rs.n || 0) >= (ls.n || 0)) ? rs : ls);
      s.best = Math.max((rs && rs.best) || 0, (ls && ls.best) || 0, s.n || 0);
      var days = {};
      [rs, ls].forEach(function (x) { ((x && x.days) || []).forEach(function (d) { days[d] = 1; }); });
      s.days = Object.keys(days).map(Number).sort(function (a, b) { return a - b; }).slice(-30);
      out.fcMeta.streak = s;
    }
    var re = (remote && remote.essays) || {};
    Object.keys(re).forEach(function (id) {
      var l = (local.essays || {})[id];
      if (l && (re[id].updated || 0) > (l.updated || 0)) out.essays[id] = re[id];
    });
    return out;
  }

  // ---- comparing the browser's copy with the account's (the sign-in chooser)
  function n(o) { return Object.keys(o || {}).length; }
  function pl(x, w, ws) { return x.toLocaleString() + " " + (x === 1 ? w : (ws || w + "s")); }
  function fcCardsOf(d) { return n(d.fcCards) ? d.fcCards : {}; }
  // Is there anything here worth keeping? Default settings and the last-test pointer don't count.
  function hasProgress(d) {
    if (!d) return false;
    var streak = d.fcMeta && d.fcMeta.streak;
    return ["answers", "scored", "scores", "quiz", "essays", "mockAttempts", "fcCards", "fcCats", "cards", "decks"]
      .some(function (k) { return n(d[k]) > 0; }) || !!(streak && (streak.n || streak.best));
  }
  function dayLabel(day) {
    var dt = new Date(day * 864e5);
    return new Date(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate()).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  // One row per kind of progress: [label, text]. Used for both copies so they line up.
  function summary(d) {
    d = d || {};
    var rows = [];
    var scores = d.scores || {}, tests = Object.keys(scores);
    var avg = tests.length ? Math.round(tests.reduce(function (s, k) {
      var t = scores[k] || {}; return s + (t.total ? 100 * (t.score || 0) / t.total : 0);
    }, 0) / tests.length) : null;
    rows.push(["Practice questions", n(d.answers) ? pl(n(d.answers), "answer") : "none"]);
    rows.push(["Practice tests scored", tests.length ? tests.length + " (average " + avg + "%)" : "none"]);
    rows.push(["Quick-quiz questions", n(d.quiz) ? pl(n(d.quiz), "question") : "none"]);
    var att = d.mockAttempts || {};
    rows.push(["Timed mock tests", n(att) ? pl(n(att), "attempt") : "none"]);
    var c = fcCardsOf(d), box = [0, 0, 0, 0, 0];
    Object.keys(c).forEach(function (id) { var b = (c[id] || [])[0]; if (b >= 0 && b <= 4) box[b]++; });
    var total = n(c) || n(d.cards);
    rows.push(["Flashcards", !total ? "none" : n(c)
      ? pl(total, "card") + " (" + [[1, "daily"], [2, "weekly"], [3, "monthly"], [4, "mastered"], [0, "waiting"]]
          .filter(function (x) { return box[x[0]]; }).map(function (x) { return box[x[0]] + " " + x[1]; }).join(", ") + ")"
      : pl(total, "card")]);
    var s = (d.fcMeta && d.fcMeta.streak) || {};
    rows.push(["Flashcard streak", s.n || s.best
      ? pl(s.n || 0, "day") + (s.best ? ", best " + s.best : "") + (s.last != null ? " (last " + dayLabel(s.last) + ")" : "")
      : "none"]);
    var cats = n(d.fcCats) || n(d.decks);
    rows.push(["Custom flashcard sets", cats ? String(cats) : "none"]);
    var es = d.essays || {}, words = Object.keys(es).reduce(function (w, k) { return w + ((es[k] || {}).words || 0); }, 0);
    rows.push(["Essays", n(es) ? pl(n(es), "essay") + ", " + pl(words, "word") : "none"]);
    return rows;
  }
  // Ask which copy to keep. Resolves "account" or "browser". The dialog can't be dismissed without a choice.
  function choose(remote, local, updated) {
    return new Promise(function (resolve) {
      function go() {
        var a = summary(remote), b = summary(local);
        var when = updated ? new Date(updated).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";
        var dlg = document.createElement("dialog");
        dlg.className = "flag-dialog sync-choice";
        dlg.setAttribute("aria-labelledby", "sync-choice-h");
        dlg.innerHTML =
          '<h2 id="sync-choice-h">Which progress do you want to keep?</h2>' +
          '<p class="flag-about">This browser has progress saved while you were signed out, and your account has its own. ' +
          'Choose one to keep. The other is replaced and can’t be brought back.</p>' +
          '<table class="sync-table"><thead><tr><th></th><th scope="col">Your account' + (when ? '<small>last saved ' + esc(when) + '</small>' : '') +
          '</th><th scope="col">This browser<small>while signed out</small></th></tr></thead><tbody>' +
          a.map(function (r, i) {
            var diff = r[1] !== b[i][1] ? ' class="differs"' : "";
            return '<tr' + diff + '><th scope="row">' + esc(r[0]) + '</th><td>' + esc(r[1]) + '</td><td>' + esc(b[i][1]) + '</td></tr>';
          }).join("") +
          '</tbody></table>' +
          '<div class="flag-actions sync-actions">' +
          '<button type="button" class="acct-btn" data-keep="account">Keep my account’s progress</button>' +
          '<button type="button" class="acct-btn sync-alt" data-keep="browser">Keep this browser’s progress</button></div>';
        document.body.appendChild(dlg);
        dlg.addEventListener("cancel", function (ev) { ev.preventDefault(); });   // Escape doesn't skip the choice
        dlg.addEventListener("click", function (ev) {
          var btn = ev.target.closest && ev.target.closest("[data-keep]");
          if (!btn) return;
          var pick = btn.getAttribute("data-keep");
          if (pick === "browser" && !window.confirm("Replace your account’s progress with this browser’s? Your account’s current progress will be gone.")) return;
          if (dlg.close) dlg.close(); dlg.remove();
          resolve(pick);
        });
        if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
        dlg.querySelector('[data-keep="account"]').focus();
      }
      onDom(go);
    });
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ---- the Supabase library, loaded only when needed
  var clientPromise = null;
  function client() {
    if (clientPromise) return clientPromise;
    clientPromise = new Promise(function (resolve, reject) {
      function make() {
        resolve(window.supabase.createClient(cfg.url, cfg.key, {
          auth: { storageKey: SESSION, persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
        }));
      }
      if (window.supabase && window.supabase.createClient) return make();
      var s = document.createElement("script");
      s.src = cfg.lib; s.async = true;
      s.onload = make;
      s.onerror = function () { reject(new Error("Could not load the sign-in library.")); };
      document.head.appendChild(s);
    });
    return clientPromise;
  }

  // ---- syncing
  var pushTimer = null, pushing = null;
  function push() {
    clearTimeout(pushTimer); pushTimer = null;
    var m = meta();
    if (!m.uid) return Promise.resolve();
    var data = localData();
    pushing = client().then(function (sb) {
      return sb.from("progress").upsert({ user_id: m.uid, data: data, updated_at: new Date().toISOString() });
    }).then(function (res) {
      if (res && res.error) throw res.error;
      var now = meta();
      if (now.uid === m.uid) { now.dirty = false; setMeta(now); }
      setStatus("saved");
    }).catch(function () { setStatus("offline"); });
    return pushing;
  }
  function schedulePush() {
    var m = meta();
    if (!m.uid) return;
    m.dirty = true; setMeta(m);
    setStatus("saving");
    clearTimeout(pushTimer);
    pushTimer = setTimeout(push, 700);
  }
  // Watch the quiz and flashcard scripts' writes to the progress keys.
  var watched = {}; Object.keys(KEYS).forEach(function (k) { watched[KEYS[k]] = 1; });
  Storage.prototype.setItem = function (k, v) {
    rawSet.call(this, k, v);
    if (this === window.localStorage && watched[k]) schedulePush();
  };
  Storage.prototype.removeItem = function (k) {
    rawRemove.call(this, k);
    if (this === window.localStorage && watched[k]) schedulePush();
  };
  window.addEventListener("pagehide", function () { if (pushTimer) push(); });

  // Bring this browser's copy in line with the account. Returns a promise.
  // When both this browser (as a guest) and the account hold progress, the student chooses which to keep
  // (choose); otherwise whichever copy has progress is used, as before.
  // onChoice runs after a choice was made (the page-load path reloads the page, since its scripts may have started).
  function pull(uid, onChoice) {
    return client().then(function (sb) {
      return sb.from("progress").select("data, updated_at").eq("user_id", uid).maybeSingle();
    }).then(function (res) {
      if (res.error) throw res.error;
      var remote = res.data ? res.data.data : null, local = localData(), m = meta();
      var updated = res.data ? res.data.updated_at : null;
      if (m.uid === uid && !m.dirty) return apply(remote || local, false);      // the account is the latest copy
      if (m.uid === uid) return apply(local, true);                             // changes made here weren't saved yet
      if (m.uid) return apply(merge(remote, {}), !remote);                      // another account's copy: ignore it
      if (hasProgress(remote) && hasProgress(local)) {
        return choose(remote, local, updated).then(function (pick) {
          return apply(pick === "browser" ? local : remote, pick === "browser");
        }).then(function () { if (onChoice) onChoice(); });
      }
      return apply(hasProgress(local) ? merge(remote, local) : (remote || local), !remote || hasProgress(local));
    });
    function apply(result, needPush) {
      writeLocal(result);
      setMeta({ uid: uid, dirty: needPush });
      if (needPush) return push();
    }
  }

  // ---- header link and status
  var statusText = { saving: "Saving…", saved: "Saved to your account", offline: "Not saved yet: offline" };
  function setStatus(s) {
    var el = document.querySelector("[data-acct-status]");
    if (el) { el.textContent = statusText[s] || ""; el.setAttribute("data-state", s); }
    try { window.dispatchEvent(new CustomEvent("litcrit-sync", { detail: s })); } catch (e) {}
  }
  function drawHeader(user) {
    var a = document.querySelector("[data-acct]");
    if (!a) return;
    if (!enabled) { a.hidden = true; return; }
    a.hidden = false;
    a.textContent = user ? (user.email || "My account") : "Sign in";
    a.title = user ? "Your account" : "Sign in to save your progress";
    a.classList.toggle("signed-in", !!user);
    if (!user) {
      var here = location.pathname + location.search;
      if (here.indexOf(BASE + "account/") !== 0) a.href = BASE + "account/?next=" + encodeURIComponent(here);
    } else a.href = BASE + "account/";
  }

  // ---- start
  var user = enabled ? storedUser() : null;
  window.litcritUser = user;
  var ready = Promise.resolve();
  if (user) {
    ready = client().then(function (sb) { return sb.auth.getSession(); }).then(function (r) {
      var s = r && r.data && r.data.session;
      if (!s) { window.litcritUser = null; return; }
      window.litcritUser = s.user;
      // If the student had to choose after the page's scripts started, reload so they show the kept copy.
      return pull(s.user.id, function () { if (timedOut) location.reload(); });
    }).catch(function () { setStatus("offline"); });
    // Never hold the page up for long.
    var timedOut = false;
    ready = Promise.race([ready, new Promise(function (r) { setTimeout(function () { timedOut = true; r(); }, 4000); })]);
  }
  window.litcritReady = ready;
  function onDom(fn) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); }
  onDom(function () { drawHeader(user); ready.then(function () { drawHeader(window.litcritUser); }); });

  // ---- used by the Account page (account.js)
  window.litcritAuth = {
    enabled: enabled,
    client: client,
    signedIn: function (u) { window.litcritUser = u; return pull(u.id).then(function () { drawHeader(u); }); },
    signOut: function () {
      var done = pushTimer ? push() : (pushing || Promise.resolve());
      return done.then(client).then(function (sb) { return sb.auth.signOut(); }).catch(function () {}).then(function () {
        Object.keys(KEYS).forEach(function (k) { drop(KEYS[k]); });
        drop(META); drop(SESSION);
        window.litcritUser = null;
        drawHeader(null);
      });
    },
    progress: localData
  };
})();
