import { auth } from "@/auth";

// Every console call to the Lattice API goes through here.
//
// The console used to authenticate from the browser, which meant an API key
// had to be embedded in the JavaScript bundle -- and anything in the bundle is
// public, no matter which key it is. So the browser now holds no key at all:
// it calls same-origin /api/lattice/*, this handler checks the session, and
// only then attaches the key server-side.
//
// The key is spent on behalf of a signed-in user, so an anonymous visitor
// cannot use this as a free relay to the paid API.

const API = (process.env.NEXT_PUBLIC_LATTICE_API || "https://lattice-api-fs5f.onrender.com").replace(/\/$/, "");
const KEY = process.env.LATTICE_MASTER_KEY || "";

// Endpoints that are public on the API itself and are needed before sign-in.
// Everything else requires a session.
const OPEN = new Set(["health", "stats", "signup", "examples"]);

async function proxy(req, ctx) {
  const path = "/" + ((await ctx.params).path || []).join("/");
  const first = path.split("/")[1] || "";

  if (!OPEN.has(first)) {
    const session = await auth();
    if (!session?.user) {
      return Response.json({ error: "sign in to use the console" }, { status: 401 });
    }
  }
  if (!KEY) {
    return Response.json({ error: "LATTICE_MASTER_KEY is not set on this deployment" }, { status: 503 });
  }

  const qs = new URL(req.url).search;
  const ct = req.headers.get("content-type") || "";
  const method = req.method;

  // Audio and CSV arrive as raw bodies; JSON as text. Streaming the raw bytes
  // through keeps /stt/parse working without multipart on either hop.
  let body;
  if (method !== "GET" && method !== "HEAD") {
    body = Buffer.from(await req.arrayBuffer());
  }

  const upstream = await fetch(API + path + qs, {
    method,
    headers: {
      "X-API-Key": KEY,
      ...(ct ? { "Content-Type": ct } : {}),
    },
    body,
    cache: "no-store",
  });

  // Pass the response through untouched -- callers parse JSON or download CSV.
  const headers = new Headers();
  for (const h of ["content-type", "content-disposition"]) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
export const PATCH = proxy;
