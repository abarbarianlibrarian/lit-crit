/*
 * The Account page: sign in, create an account, forgot password, set a new password,
 * and (signed in) the account summary with Change password and Sign out.
 * Uses window.litcritAuth from auth.js.
 */
(function () {
  var root = document.querySelector("[data-account]");
  if (!root) return;
  var auth = window.litcritAuth;
  var BASE = window.SITE_BASE || "/";
  var params = new URLSearchParams(location.search);
  var next = params.get("next");
  if (!next || next.charAt(0) !== "/" || next.indexOf("//") === 0) next = null;

  if (!auth || !auth.enabled) {
    show("off");
    return;
  }

  function $(sel) { return root.querySelector(sel); }
  function show(view) {
    root.querySelectorAll("[data-view]").forEach(function (v) { v.hidden = v.getAttribute("data-view") !== view; });
    var f = root.querySelector('[data-view="' + view + '"] input');
    if (f && view !== "account") f.focus();
  }
  function message(form, text, ok) {
    var m = form.querySelector(".acct-msg");
    m.textContent = text || "";
    m.className = "acct-msg" + (ok ? " ok" : text ? " err" : "");
  }
  function busy(form, on) {
    form.querySelectorAll("button, input").forEach(function (el) { el.disabled = on; });
  }
  function friendly(err) {
    var t = (err && (err.message || err.error_description)) || String(err || "");
    if (/invalid login credentials/i.test(t)) return "That email and password don't match an account.";
    if (/email not confirmed/i.test(t)) return "Please confirm your email address first, using the link we sent you.";
    if (/already registered|already exists/i.test(t)) return "There is already an account with that email. Try signing in.";
    if (/password should be at least/i.test(t)) return "Please choose a password of at least 8 characters.";
    if (/rate limit|too many/i.test(t)) return "Too many tries just now. Please wait a few minutes and try again.";
    if (/not authorized|error sending/i.test(t)) return "We couldn't send that email right now. Please try again later.";
    if (/failed to fetch|network|load the sign-in/i.test(t)) return "Couldn't reach the sign-in service. Check your connection and try again.";
    return t || "Something went wrong. Please try again.";
  }
  function counts() {
    var p = auth.progress();
    var tests = Object.keys(p.scores).length, answers = Object.keys(p.answers).length;
    return answers + (answers === 1 ? " answer" : " answers") + " and " + tests + (tests === 1 ? " scored test" : " scored tests");
  }
  function afterSignIn(user) {
    return auth.signedIn(user).then(function () {
      if (next) { location.href = next; return; }
      drawAccount(user);
    });
  }
  function drawAccount(user) {
    $("[data-acct-email]").textContent = user.email;
    $("[data-acct-count]").textContent = counts();
    show("account");
  }

  // view switching links
  root.addEventListener("click", function (ev) {
    var go = ev.target.closest("[data-go]");
    if (!go) return;
    ev.preventDefault();
    show(go.getAttribute("data-go"));
  });

  // Sign in
  $("#acct-signin").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var form = ev.target;
    message(form, ""); busy(form, true);
    auth.client().then(function (sb) {
      return sb.auth.signInWithPassword({ email: form.email.value.trim(), password: form.password.value });
    }).then(function (r) {
      if (r.error) throw r.error;
      return afterSignIn(r.data.user);
    }).catch(function (e) { message(form, friendly(e)); }).then(function () { busy(form, false); });
  });

  // Create account
  $("#acct-signup").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var form = ev.target;
    message(form, "");
    if (form.password.value.length < 8) return message(form, "Please choose a password of at least 8 characters.");
    if (form.password.value !== form.password2.value) return message(form, "The two passwords don't match.");
    busy(form, true);
    auth.client().then(function (sb) {
      return sb.auth.signUp({
        email: form.email.value.trim(), password: form.password.value,
        options: { emailRedirectTo: location.origin + BASE + "account/" }
      });
    }).then(function (r) {
      if (r.error) throw r.error;
      if (r.data.session) return afterSignIn(r.data.user);
      if (r.data.user && r.data.user.identities && !r.data.user.identities.length)
        throw new Error("already registered");
      message(form, "Almost done: check your email for a link to confirm your account, then sign in.", true);
    }).catch(function (e) { message(form, friendly(e)); }).then(function () { busy(form, false); });
  });

  // Forgot password
  $("#acct-forgot").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var form = ev.target;
    message(form, ""); busy(form, true);
    auth.client().then(function (sb) {
      return sb.auth.resetPasswordForEmail(form.email.value.trim(), { redirectTo: location.origin + BASE + "account/" });
    }).then(function (r) {
      if (r.error) throw r.error;
      message(form, "If there's an account for that email, a link to set a new password is on its way.", true);
    }).catch(function (e) { message(form, friendly(e)); }).then(function () { busy(form, false); });
  });

  // New password (after the email link, or Change password while signed in)
  $("#acct-reset").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var form = ev.target;
    message(form, "");
    if (form.password.value.length < 8) return message(form, "Please choose a password of at least 8 characters.");
    if (form.password.value !== form.password2.value) return message(form, "The two passwords don't match.");
    busy(form, true);
    auth.client().then(function (sb) {
      return sb.auth.updateUser({ password: form.password.value }).then(function (r) {
        if (r.error) throw r.error;
        return sb.auth.getUser();
      });
    }).then(function (r) {
      form.reset();
      return afterSignIn(r.data.user).then(function () { message($("#acct-reset"), ""); });
    }).catch(function (e) { message(form, friendly(e)); }).then(function () { busy(form, false); });
  });

  $("[data-signout]").addEventListener("click", function () {
    auth.signOut().then(function () { show("signin"); });
  });

  // Which view to start on. An email link (confirm or reset) lands here with a token in the address.
  var hash = location.hash || "";
  var recovering = /type=recovery/.test(hash);
  var errorInLink = /error_description=([^&]+)/.exec(hash);
  show("loading");
  auth.client().then(function (sb) {
    sb.auth.onAuthStateChange(function (event) {
      if (event === "PASSWORD_RECOVERY") { recovering = true; show("reset"); }
    });
    return sb.auth.getSession();
  }).then(function (r) {
    var s = r.data && r.data.session;
    if (hash && /access_token|error/.test(hash)) history.replaceState(null, "", location.pathname + location.search);
    if (errorInLink) {
      show("signin");
      message($("#acct-signin"), decodeURIComponent(errorInLink[1].replace(/\+/g, " ")) + " Please try again.");
      return;
    }
    if (s && recovering) return show("reset");
    if (s) return auth.signedIn(s.user).then(function () { drawAccount(s.user); });
    show(params.get("mode") === "signup" ? "signup" : "signin");
  }).catch(function (e) {
    show("signin");
    message($("#acct-signin"), friendly(e));
  });
})();
