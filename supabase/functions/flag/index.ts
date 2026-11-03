// "Flag an error" reports from the website.
//
// The site POSTs {category, message, item, item_id, url, email?, name?, website?} here.
// This function checks the report, limits how often one visitor can send them, saves it to
// public.flags, and passes it to the Airtable automation "Website flags → Requests"
// (its webhook URL is kept in the private public.app_config table, not in this code).
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const ALLOWED_ORIGINS = [
  "https://abarbarianlibrarian.github.io",
  "http://localhost:8765",
];
const CATEGORIES = [
  "Wrong answer key",
  "Typo or scanning error",
  "Incorrect information",
  "Broken link or missing content",
  "Other",
];
const PER_HOUR = 6, PER_DAY = 25;

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
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors(origin), "Content-Type": "application/json" },
  });
}
function text(v: unknown, max: number) {
  return typeof v === "string" ? v.replace(/\u0000/g, "").trim().slice(0, max) : "";
}
async function sha256(s: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors(origin) });
  if (req.method !== "POST") return reply(origin, 405, { error: "Use POST." });

  let body: Record<string, unknown>;
  try { body = await req.json(); } catch { return reply(origin, 400, { error: "Invalid request." }); }

  // Bots fill in the hidden "website" field; pretend success and drop it.
  if (text(body.website, 200)) return reply(origin, 200, { ok: true });

  const category = text(body.category, 60);
  const message = text(body.message, 2000);
  const item = text(body.item, 300);
  const itemId = text(body.item_id, 40);
  let url = text(body.url, 500);
  let email = text(body.email, 200);
  let name = text(body.name, 100);
  if (!CATEGORIES.includes(category)) return reply(origin, 400, { error: "Please choose what kind of problem it is." });
  if (message.length < 5) return reply(origin, 400, { error: "Please describe the problem in a few words." });
  if (url && !url.startsWith("https://abarbarianlibrarian.github.io/")) url = "";
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) email = "";

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
    auth: { persistSession: false },
  });

  // Signed-in visitor? Use their account email.
  let userId: string | null = null;
  const token = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (token.split(".").length === 3) {
    const { data } = await db.auth.getUser(token);
    if (data?.user) { userId = data.user.id; email = email || data.user.email || ""; }
  }

  const { data: cfg } = await db.from("app_config").select("key, value");
  const conf = Object.fromEntries((cfg || []).map((r) => [r.key, r.value]));
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "unknown";
  const ipHash = await sha256((conf.ip_salt || "") + ip);

  // Rate limit by visitor.
  const hourAgo = new Date(Date.now() - 3600e3).toISOString();
  const dayAgo = new Date(Date.now() - 86400e3).toISOString();
  const { count: lastHour } = await db.from("flags").select("id", { count: "exact", head: true })
    .eq("ip_hash", ipHash).gte("created_at", hourAgo);
  const { count: lastDay } = await db.from("flags").select("id", { count: "exact", head: true })
    .eq("ip_hash", ipHash).gte("created_at", dayAgo);
  if ((lastHour || 0) >= PER_HOUR || (lastDay || 0) >= PER_DAY)
    return reply(origin, 429, { error: "Thanks! You've sent a lot of reports today. Please try again later." });

  const { data: row, error } = await db.from("flags").insert({
    category, message, item, item_id: itemId, page_url: url, email, name, user_id: userId, ip_hash: ipHash,
  }).select("id").single();
  if (error) return reply(origin, 500, { error: "Couldn't save the report. Please try again." });

  // Pass it on to Airtable (Requests table). If this fails the report is still saved here.
  if (conf.airtable_flag_webhook) {
    try {
      const r = await fetch(conf.airtable_flag_webhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category, message, item: itemId ? `${item} (${itemId})` : item, url,
          email, name: name || (email ? email.split("@")[0] : "Website visitor"),
          flag_id: row.id,
        }),
      });
      if (r.ok) await db.from("flags").update({ forwarded: true }).eq("id", row.id);
    } catch { /* kept in public.flags */ }
  }
  return reply(origin, 200, { ok: true });
});
