import { auth } from "@/auth";

// Why this route exists at all, instead of the console calling the API directly:
// the API's /account/keys endpoints take an `email` parameter, so whoever
// calls them chooses whose keys they see. This handler runs on the server,
// reads the email from the signed session cookie, and forwards it with the
// master key. The browser never states which account it is — so signing in
// as someone else is the only way to see someone else's keys, which is the
// isolation we actually want.

const API = (process.env.NEXT_PUBLIC_LATTICE_API || "https://lattice-api-fs5f.onrender.com").replace(/\/$/, "");
const MASTER = process.env.LATTICE_MASTER_KEY || "";

const fail = (msg, status = 500) =>
  Response.json({ error: msg }, { status });

async function callApi(path, init = {}) {
  const r = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-API-Key": MASTER, ...(init.headers || {}) },
    cache: "no-store",
  });
  const text = await r.text();
  let body;
  try { body = text ? JSON.parse(text) : {}; } catch { body = { detail: text }; }
  return { ok: r.ok, status: r.status, body };
}

async function requireEmail() {
  const session = await auth();
  const email = session?.user?.email?.trim().toLowerCase();
  return email || null;
}

export async function GET() {
  const email = await requireEmail();
  if (!email) return fail("not signed in", 401);
  if (!MASTER) return fail("LATTICE_MASTER_KEY is not set on this deployment", 503);

  const { ok, status, body } = await callApi(`/account/keys?email=${encodeURIComponent(email)}`);
  if (!ok) return fail(body.detail || `upstream ${status}`, status);
  return Response.json({ email, keys: body.keys || [] });
}

export async function POST(req) {
  const email = await requireEmail();
  if (!email) return fail("not signed in", 401);
  if (!MASTER) return fail("LATTICE_MASTER_KEY is not set on this deployment", 503);

  let label = "";
  try { label = ((await req.json())?.label || "").toString().slice(0, 60); } catch {}

  const { ok, status, body } = await callApi("/account/keys", {
    method: "POST",
    body: JSON.stringify({ email, label }),
  });
  if (!ok) return fail(body.detail || `upstream ${status}`, status);
  return Response.json(body);
}

export async function DELETE(req) {
  const email = await requireEmail();
  if (!email) return fail("not signed in", 401);
  if (!MASTER) return fail("LATTICE_MASTER_KEY is not set on this deployment", 503);

  const id = new URL(req.url).searchParams.get("id");
  if (!id) return fail("id required", 400);

  const { ok, status, body } = await callApi(
    `/account/keys/${encodeURIComponent(id)}?email=${encodeURIComponent(email)}`,
    { method: "DELETE" });
  if (!ok) return fail(body.detail || `upstream ${status}`, status);
  return Response.json(body);
}
