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
    root.querySelectorAll("[data-view-also]").forEach(function (v) { v.hidden = v.getAttribute("data-view-also") !== view; });
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
  // ---- profile (public.profiles: role, graduation_year, school)
  function syncGrad(form) {
    var role = (form.querySelector('[name="role"]:checked') || {}).value;
    var grad = form.querySelector("[data-grad]"), other = form.querySelector("[data-grad-other]");
    grad.hidden = role !== "student";
    other.hidden = role !== "student" || form.graduation_year.value !== "other";
  }
  root.querySelectorAll("#acct-signup, #acct-profile").forEach(function (form) {
    form.addEventListener("change", function () { syncGrad(form); });
  });
  // UIL school list (from the Schools Master table), shown as type-ahead suggestions.
  var schools = null, schoolByLabel = {}, schoolById = {};
  function schoolLabel(x) { return x[1] + (x[2] ? " (" + x[2] + ")" : ""); }
  var schoolsReady = fetch(window.LITCRIT_SCHOOLS || "").then(function (r) { return r.ok ? r.json() : null; })
    .catch(function () { return null; }).then(function (list) {
      schools = list && list.length ? list : null;
      if (!schools) return;
      var html = schools.map(function (x) {
        var l = schoolLabel(x);
        schoolByLabel[l.toLowerCase()] = x; schoolById[x[0]] = x;
        return '<option value="' + l.replace(/&/g, "&amp;").replace(/"/g, "&quot;") + '">' + (x[3] || "") + "</option>";
      }).join("");
      root.querySelectorAll("[data-school-list]").forEach(function (d) { d.innerHTML = html; });
      root.querySelectorAll("[data-school-other]").forEach(function (c) { c.hidden = false; });
    });
  function matchSchool(text) {
    var t = text.trim().toLowerCase();
    if (!schools || !t) return null;
    if (schoolByLabel[t]) return schoolByLabel[t];
    var byName = schools.filter(function (x) { return x[1].toLowerCase() === t; });
    return byName.length === 1 ? byName[0] : null;
  }
  function checkSchool(form) {     // returns an error message, or "" when the school is fine
    var text = form.school.value.trim();
    if (!text || !schools || form.school_other.checked || matchSchool(text)) return "";
    return "Pick your school from the suggestions, or tick \u201cMy school isn\u2019t on the list.\u201d";
  }

  function readProfile(form) {
    var role = (form.querySelector('[name="role"]:checked') || {}).value || null;
    var year = null;
    if (role === "student") {
      var v = form.graduation_year.value === "other" ? form.graduation_year_other.value : form.graduation_year.value;
      year = /^\d{4}$/.test(String(v).trim()) ? parseInt(v, 10) : null;
    }
    var hit = form.school_other.checked ? null : matchSchool(form.school.value);
    return { role: role, graduation_year: year, school_id: hit ? hit[0] : null,
             school: (hit ? schoolLabel(hit) : form.school.value.trim()).slice(0, 120) || null };
  }
  function fillProfile(form, p) {
    p = p || {};
    form.querySelectorAll('[name="role"]').forEach(function (r) { r.checked = r.value === p.role; });
    var known = [].some.call(form.graduation_year.options, function (o) { return o.value === String(p.graduation_year); });
    form.graduation_year.value = p.graduation_year ? (known ? String(p.graduation_year) : "other") : "";
    form.graduation_year_other.value = p.graduation_year && !known ? p.graduation_year : "";
    form.school.value = p.school || "";
    schoolsReady.then(function () {
      if (p.school_id && schoolById[p.school_id]) form.school.value = schoolLabel(schoolById[p.school_id]);
      form.school_other.checked = !!(p.school && !p.school_id && schools);
    });
    syncGrad(form);
  }
  function emptyProfile(p) { return !p.role && !p.graduation_year && !p.school; }
  function saveProfile(user, p) {
    return auth.client().then(function (sb) {
      return sb.from("profiles").upsert({ user_id: user.id, role: p.role, graduation_year: p.graduation_year,
        school: p.school, school_id: p.school_id, updated_at: new Date().toISOString() });
    }).then(function (r) { if (r.error) throw r.error; });
  }
  function loadProfile(user) {
    return auth.client().then(function (sb) {
      return sb.from("profiles").select("role, graduation_year, school, school_id").eq("user_id", user.id).maybeSingle();
    }).then(function (r) { return r.error ? null : r.data; }).catch(function () { return null; });
  }

  function afterSignIn(user) {
    return auth.signedIn(user).then(function () {
      if (next) { location.href = next; return; }
      drawAccount(user);
    });
  }
  var me = null;
  function drawAccount(user) {
    me = user;
    $("[data-acct-email]").textContent = user.email;
    $("[data-acct-count]").textContent = counts();
    show("account");
    loadProfile(user).then(function (p) { fillProfile($("#acct-profile"), p); });
  }

  $("#acct-profile").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var form = ev.target;
    if (!me) return;
    var bad = checkSchool(form);
    if (bad) return message(form, bad);
    var p = readProfile(form);
    message(form, ""); busy(form, true);
    saveProfile(me, p).then(function () { message(form, "Profile saved.", true); })
      .catch(function (e) { message(form, friendly(e)); })
      .then(function () { busy(form, false); syncGrad(form); });
  });

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
    var badSchool = checkSchool(form);
    if (badSchool) return message(form, badSchool);
    busy(form, true);
    auth.client().then(function (sb) {
      return sb.auth.signUp({
        email: form.email.value.trim(), password: form.password.value,
        options: { emailRedirectTo: location.origin + BASE + "account/" }
      });
    }).then(function (r) {
      if (r.error) throw r.error;
      var p = readProfile(form);
      if (r.data.session) {
        var saved = emptyProfile(p) ? Promise.resolve() : saveProfile(r.data.user, p).catch(function () {});
        return saved.then(function () { return afterSignIn(r.data.user); });
      }
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
