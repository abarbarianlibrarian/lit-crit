/* Members-only files on the Resources page.
 *
 * Each shared file has Open and Download buttons ([data-file-rec][data-file-att]). Guests see
 * "Sign in to open", which leads to the Account page and back. Signed-in visitors' clicks go to the
 * Supabase Edge Function resource-file (window.LITCRIT_FILES) with their access token; it checks the
 * account and the record's "Share File" box and answers with a link that works for 5 minutes, which
 * this script opens in a new tab (Open) or downloads (Download). The file's real address is never
 * in the page.
 */
(function () {
  var FN = window.LITCRIT_FILES;
  var BASE = window.SITE_BASE || "/";
  var boxes = document.querySelectorAll("[data-file-rec]");
  if (!boxes.length) return;

  function signInUrl() {
    return BASE + "account/?next=" + encodeURIComponent(location.pathname + location.search);
  }
  function setGuest(guest) {
    boxes.forEach(function (box) {
      box.querySelectorAll(".res-file-btn").forEach(function (b) { b.hidden = guest; });
      var lock = box.querySelector(".res-file-lock");
      if (!lock) return;
      if (guest && lock.tagName !== "A") {
        var a = document.createElement("a");
        a.className = lock.className; a.href = signInUrl(); a.textContent = "🔒 Sign in to open";
        lock.replaceWith(a); lock = a;
      }
      lock.hidden = !guest;
    });
    var note = document.querySelector("[data-files-note]");
    if (note) note.hidden = !guest;
    var link = document.querySelector("[data-files-signin]");
    if (link) link.href = signInUrl();
  }

  function token() {
    var auth = window.litcritAuth;
    if (!auth || !auth.enabled) return Promise.resolve(null);
    return auth.client().then(function (sb) { return sb.auth.getSession(); })
      .then(function (r) { var s = r && r.data && r.data.session; return s ? s.access_token : null; })
      .catch(function () { return null; });
  }

  function say(box, text, bad) {
    var m = box.querySelector(".res-file-msg");
    if (!m) return;
    m.textContent = text || "";
    m.classList.toggle("bad", !!bad);
  }

  function request(box, download) {
    return token().then(function (t) {
      if (!t) { location.href = signInUrl(); return null; }
      return fetch(FN, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + t },
        body: JSON.stringify({ id: box.getAttribute("data-file-rec"), att: box.getAttribute("data-file-att"), download: download })
      }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (j) {
          if (res.status === 401) { location.href = signInUrl(); return null; }
          if (!res.ok || !j.url) throw new Error(j.error || "Couldn't open the file. Please try again.");
          return j.url;
        });
      });
    });
  }

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest && ev.target.closest(".res-file-btn");
    if (!btn) return;
    var box = btn.closest("[data-file-rec]");
    if (!FN) { say(box, "Files aren't available right now.", true); return; }
    var download = btn.getAttribute("data-file-mode") === "download";
    // Open the tab now, while the click still counts, so pop-up blockers allow it.
    var win = download ? null : window.open("", "_blank");
    if (win) { try { win.document.title = "Opening…"; win.document.body.textContent = "Opening the file…"; } catch (e) {} }
    btn.disabled = true;
    say(box, download ? "Preparing download…" : "Opening…");
    request(box, download).then(function (url) {
      if (!url) { if (win) win.close(); return; }
      if (download) {
        var a = document.createElement("a");
        a.href = url; a.rel = "noopener"; a.style.display = "none";
        document.body.appendChild(a); a.click(); a.remove();
      } else if (win) {
        try { win.opener = null; } catch (e) {}
        win.location.href = url;
      } else {
        location.href = url;   // pop-ups blocked: open it here
      }
      say(box, "");
      if (window.gtag) gtag("event", download ? "file_download" : "file_open", { record_id: box.getAttribute("data-file-rec") });
    }).catch(function (err) {
      if (win) win.close();
      say(box, err.message, true);
    }).then(function () { btn.disabled = false; });
  });

  setGuest(!window.litcritUser);
  (window.litcritReady || Promise.resolve()).then(function () { setGuest(!window.litcritUser); });
})();
