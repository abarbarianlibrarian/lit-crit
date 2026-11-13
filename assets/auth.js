/*
 * Accounts (Supabase): optional sign-in that saves practice answers, scored pages, test scores,
 * the flashcard schedule, custom flashcard decks and essays
 * to the visitor's account, so they follow them between browsers and devices.
 *
 * Guests: nothing changes; progress stays in this browser (localStorage), and the Supabase library
 * is never loaded.
 * Signed in: on each page load, before the quiz scripts start (window.litcritReady), the saved
 * progress is pulled from the account; every change the quiz scripts make to localStorage is pushed
 * back a moment later. Signing in keeps whatever was answered as a guest in this browser.
 * Signing out clears this browser's copy.
 *
 * Settings come from the page: window.LITCRIT_AUTH = {url, key, lib}.
 */
(function () {
  var cfg = window.LITCRIT_AUTH || {};
  var KEYS = { answers: "litcrit-answers-v1", scored: "litcrit-scored-v1", scores: "litcrit-test-scores-v1",
               cards: "litcrit-cards-v1", decks: "litcrit-decks-v1", quiz: "litcrit-quiz-v1", last: "litcrit-last-v1",
               fcCards: "litcrit-fc-cards-v2", fcCats: "litcrit-fc-cats-v2", fcMeta: "litcrit-fc-meta-v2",
               essays: "litcrit-essays-v1", mock: "litcrit-mock-v1", mockAttempts: "litcrit-mock-attempts-v1" };
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
    var re = (remote && remote.essays) || {};
    Object.keys(re).forEach(function (id) {
      var l = (local.essays || {})[id];
      if (l && (re[id].updated || 0) > (l.updated || 0)) out.essays[id] = re[id];
    });
    return out;
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
  function pull(uid) {
    return client().then(function (sb) {
      return sb.from("progress").select("data").eq("user_id", uid).maybeSingle();
    }).then(function (res) {
      if (res.error) throw res.error;
      var remote = res.data ? res.data.data : null, local = localData(), m = meta();
      var result, needPush = false;
      if (m.uid === uid && !m.dirty) {
        result = remote || local;                     // the account is the latest copy
      } else if (m.uid === uid) {
        result = local; needPush = true;              // changes made here weren't saved yet
      } else {
        result = merge(remote, m.uid ? {} : local); // guest progress joins the account
        needPush = !remote || !isEmpty(local);
      }
      writeLocal(result);
      setMeta({ uid: uid, dirty: needPush });
      if (needPush) return push();
    });
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
      return pull(s.user.id);
    }).catch(function () { setStatus("offline"); });
    // Never hold the page up for long.
    ready = Promise.race([ready, new Promise(function (r) { setTimeout(r, 4000); })]);
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
