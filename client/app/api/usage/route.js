import { auth } from "@/auth";

// Same isolation story as /api/keys: the API's /account/usage takes an
// `email` parameter, so it is master-key-only and the ONLY caller is this
// server-side handler, which reads the email from the signed session. The
// browser never states which account's usage it wants.

const API = (process.env.NEXT_PUBLIC_LATTICE_API || "https://lattice-api-fs5f.onrender.com").replace(/\/$/, "");
const MASTER = process.env.LATTICE_MASTER_KEY || "";

const fail = (msg, status = 500) => Response.json({ error: msg }, { status });

export async function GET(req) {
  const session = await auth();
  const email = session?.user?.email?.trim().toLowerCase();
  if (!email) return fail("not signed in", 401);
  if (!MASTER) return fail("LATTICE_MASTER_KEY is not set on this deployment", 503);

  const days = Math.min(90, Math.max(1, Number(new URL(req.url).searchParams.get("days")) || 30));
  const r = await fetch(
    `${API}/account/usage?email=${encodeURIComponent(email)}&days=${days}`,
    { headers: { "X-API-Key": MASTER }, cache: "no-store" });
  const text = await r.text();
  let body;
  try { body = text ? JSON.parse(text) : {}; } catch { body = { detail: text }; }
  if (!r.ok) return fail(body.detail || `upstream ${r.status}`, r.status);
  return Response.json(body);
}
