// Opens or downloads a Reading Resources file (PDF etc.) for signed-in visitors only.
//
// Step 1 (POST, from the Resources page): {id: "rec…", att?: "att…", download?: bool} with the visitor's
// Supabase access token in the Authorization header. The function checks the account, applies per-user
// limits, checks the record's "Share File" box in Airtable, logs the request in public.file_downloads and
// answers {url, filename}: a link back to this function that works for 5 minutes.
// Step 2 (GET ?t=…, the link from step 1): checks the link, looks the record up in Airtable again (so
// unticking "Share File" takes effect at once) and streams the file. Airtable's own file address is
// never sent to the browser.
//
// Needs the Edge Function secret AIRTABLE_TOKEN: an Airtable token with data.records:read on the
// Literary Criticism base. SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are provided by Supabase.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const BASE_ID = "appIwriYb9qeDgwst";
const TABLE_ID = "tblfrvM5B3HwYgqh3"; // Reading Resources
const F_NAME = "fldL0NeGFsHTtCuTY";
const F_FILE = "fldBxMbT6tJ7TlwFk";
const F_SHARE = "fld72zxz5ayHFJ63h"; // "Share File" checkbox
const LINK_MINUTES = 5;
const PER_HOUR = 30, PER_DAY = 100;
const ALLOWED_ORIGINS = ["https://abarbarianlibrarian.github.io", "http://localhost:8765"];

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const SELF = `${SUPABASE_URL}/functions/v1/resource-file`;

function cors(origin: string | null) {
  const allow = origin && ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Vary": "Origin",
  };
}
function reply(origin: string | null, status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { ...cors(origin), "Content-Type": "application/json" } });
}
function page(status: number, message: string) {
  // Shown in the tab when a link is opened late or the file was withdrawn.
  return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
}

// ---- signed links (HMAC with a key derived from the service role key; nothing extra to configure)
const enc = new TextEncoder();
let keyPromise: Promise<CryptoKey> | null = null;
function hmacKey() {
  keyPromise ??= crypto.subtle.digest("SHA-256", enc.encode("resource-file:" + SERVICE_KEY))
    .then((raw) => crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]));
  return keyPromise;
}
function b64url(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function unb64url(s: string) {
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}
type Ticket = { r: string; a: string; d: boolean; x: number };
async function sign(t: Ticket) {
  const body = b64url(enc.encode(JSON.stringify(t)));
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", await hmacKey(), enc.encode(body)));
  return `${body}.${b64url(sig)}`;
}
async function verify(token: string): Promise<Ticket | null> {
  const [body, sig] = token.split(".");
  if (!body || !sig) return null;
  try {
    const ok = await crypto.subtle.verify("HMAC", await hmacKey(), unb64url(sig), enc.encode(body));
    if (!ok) return null;
    const t = JSON.parse(new TextDecoder().decode(unb64url(body))) as Ticket;
    return t.x > Date.now() ? t : null;
  } catch { return null; }
}

// ---- Airtable
type Att = { id: string; url: string; filename: string; type?: string; size?: number };
async function sharedFiles(recordId: string): Promise<{ name: string; files: Att[] } | null | "no-token"> {
  const token = Deno.env.get("AIRTABLE_TOKEN");
  if (!token) return "no-token";
  const params = new URLSearchParams({ returnFieldsByFieldId: "true", filterByFormula: `RECORD_ID()='${recordId}'` });
  for (const f of [F_NAME, F_FILE, F_SHARE]) params.append("fields[]", f);
  const res = await fetch(`https://api.airtable.com/v0/${BASE_ID}/${TABLE_ID}?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Airtable ${res.status}`);
  const rec = (await res.json()).records?.[0];
  if (!rec || rec.fields?.[F_SHARE] !== true) return null;
  const files = (rec.fields?.[F_FILE] || []) as Att[];
  return files.length ? { name: rec.fields?.[F_NAME] || "", files } : null;
}

function disposition(download: boolean, filename: string) {
  const ascii = filename.replace(/[^\x20-\x7e]/g, "_").replace(/["\\]/g, "_");
  return `${download ? "attachment" : "inline"}; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`;
}

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors(origin) });

  // ---- step 2: serve the file
  if (req.method === "GET") {
    const t = await verify(new URL(req.url).searchParams.get("t") || "");
    if (!t) return page(403, "This link has expired. Go back to the Resources page and click the file again.");
    let found;
    try { found = await sharedFiles(t.r); } catch { return page(502, "The file couldn't be fetched just now. Please try again."); }
    if (found === "no-token") return page(503, "File sharing isn't set up yet.");
    const att = found?.files.find((f) => f.id === t.a);
    if (!att) return page(404, "This file is no longer available.");
    const upstream = await fetch(att.url);
    if (!upstream.ok || !upstream.body) return page(502, "The file couldn't be fetched just now. Please try again.");
    const headers: Record<string, string> = {
      "Content-Type": att.type || upstream.headers.get("content-type") || "application/octet-stream",
      "Content-Disposition": disposition(t.d, att.filename || "file"),
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": "noindex",
    };
    const len = upstream.headers.get("content-length");
    if (len) headers["Content-Length"] = len;
    return new Response(upstream.body, { status: 200, headers });
  }

  if (req.method !== "POST") return reply(origin, 405, { error: "Use POST." });

  // ---- step 1: check the visitor and hand out a short-lived link
  const jwt = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });
  const { data: who } = jwt.split(".").length === 3 ? await db.auth.getUser(jwt) : { data: null };
  const user = who?.user;
  if (!user) return reply(origin, 401, { error: "Please sign in to open this file." });

  let body: Record<string, unknown>;
  try { body = await req.json(); } catch { return reply(origin, 400, { error: "Invalid request." }); }
  const recordId = typeof body.id === "string" ? body.id : "";
  const attId = typeof body.att === "string" ? body.att : "";
  if (!/^rec[A-Za-z0-9]{14}$/.test(recordId) || (attId && !/^att[A-Za-z0-9]{14}$/.test(attId))) {
    return reply(origin, 400, { error: "Invalid request." });
  }

  const now = Date.now();
  const since = (ms: number) => new Date(now - ms).toISOString();
  const [hour, day] = await Promise.all([
    db.from("file_downloads").select("id", { count: "exact", head: true }).eq("user_id", user.id).gte("created_at", since(3600e3)),
    db.from("file_downloads").select("id", { count: "exact", head: true }).eq("user_id", user.id).gte("created_at", since(86400e3)),
  ]);
  if ((hour.count ?? 0) >= PER_HOUR || (day.count ?? 0) >= PER_DAY) {
    return reply(origin, 429, { error: "You've opened a lot of files in a short time. Please try again later." });
  }

  let found;
  try { found = await sharedFiles(recordId); } catch { return reply(origin, 502, { error: "The file couldn't be fetched just now. Please try again." }); }
  if (found === "no-token") return reply(origin, 503, { error: "File sharing isn't set up yet." });
  const att = found && (attId ? found.files.find((f) => f.id === attId) : found.files[0]);
  if (!att) return reply(origin, 404, { error: "This file isn't available." });

  await db.from("file_downloads").insert({ user_id: user.id, record_id: recordId, attachment_id: att.id, filename: att.filename });
  const ticket = await sign({ r: recordId, a: att.id, d: body.download === true, x: now + LINK_MINUTES * 60e3 });
  return reply(origin, 200, { url: `${SELF}?t=${encodeURIComponent(ticket)}`, filename: att.filename });
});
