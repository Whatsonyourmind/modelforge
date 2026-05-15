/**
 * ModelForge Collab Worker — Yjs realtime sync entrypoint.
 *
 * Routes:
 *   GET  /healthz                       — liveness (returns "ok")
 *   GET  /docs/<id>/ws                  — WebSocket upgrade → joins Y.Doc room
 *   GET  /docs/<id>/snapshot            — returns latest persisted Y.Doc state (binary)
 *   POST /docs/<id>/comments            — REST mirror for CommentStore sync
 *   GET  /docs/<id>/comments            — REST list of comments (auth-scoped)
 *
 * Auth: every request must carry an `Authorization: Bearer <jwt>` header
 * verified against SUPABASE_JWT_SECRET (mirrors Python saas/auth.py logic).
 * Tenant isolation is enforced at the DO level — DO ID = `${tenantId}:${docId}`.
 */

export interface Env {
  COLLAB_DOC: DurableObjectNamespace;
  ENV: string;
  ALLOWED_ORIGINS: string;
  SUPABASE_JWT_SECRET?: string;
}

const corsHeaders = (origin: string | null) => ({
  "Access-Control-Allow-Origin": origin ?? "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
  "Access-Control-Max-Age": "86400",
});

interface AuthClaims {
  sub: string;        // user_id
  tenant_id: string;  // from user_metadata.tenant_id
  email?: string;
  role?: string;
}

/** Decode JWT without verifying signature (dev mode only). */
function decodeJwtUnverified(token: string): Record<string, unknown> {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("malformed jwt");
  const padded = parts[1] + "=".repeat((4 - (parts[1].length % 4)) % 4);
  const json = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(json);
}

/** Verify JWT signature with HS256 + the Supabase secret. */
async function verifyJwt(token: string, secret: string): Promise<AuthClaims> {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("malformed jwt");
  const [headerB64, payloadB64, sigB64] = parts;
  const data = `${headerB64}.${payloadB64}`;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const sigBytes = Uint8Array.from(
    atob(sigB64.replace(/-/g, "+").replace(/_/g, "/").padEnd(sigB64.length + ((4 - (sigB64.length % 4)) % 4), "=")),
    (c) => c.charCodeAt(0),
  );
  const verified = await crypto.subtle.verify(
    "HMAC",
    key,
    sigBytes,
    new TextEncoder().encode(data),
  );
  if (!verified) throw new Error("jwt signature mismatch");
  const payload = decodeJwtUnverified(token);
  const sub = payload["sub"] as string;
  const meta = (payload["user_metadata"] ?? {}) as Record<string, unknown>;
  const tenantId = (meta["tenant_id"] ?? payload["tenant_id"] ?? sub) as string;
  return {
    sub,
    tenant_id: tenantId,
    email: payload["email"] as string | undefined,
    role: (meta["role"] as string | undefined) ?? "member",
  };
}

async function authenticate(req: Request, env: Env): Promise<AuthClaims> {
  const auth = req.headers.get("Authorization") ?? "";
  if (!auth.toLowerCase().startsWith("bearer ")) {
    throw new Response("missing or malformed Authorization header", { status: 401 });
  }
  const token = auth.slice(7).trim();
  if (!env.SUPABASE_JWT_SECRET) {
    // Dev mode — decode without verifying. NEVER ship to prod without secret.
    const payload = decodeJwtUnverified(token) as Record<string, unknown>;
    const sub = (payload["sub"] ?? "dev-user") as string;
    const meta = (payload["user_metadata"] ?? {}) as Record<string, unknown>;
    return {
      sub,
      tenant_id: (meta["tenant_id"] ?? sub) as string,
      email: payload["email"] as string | undefined,
      role: "member",
    };
  }
  return verifyJwt(token, env.SUPABASE_JWT_SECRET);
}

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    const origin = req.headers.get("Origin");

    if (req.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(origin) });
    }

    if (url.pathname === "/healthz") {
      return new Response("ok", { headers: { "Content-Type": "text/plain", ...corsHeaders(origin) } });
    }

    // Path: /docs/<id>/{ws|snapshot|comments}
    const docMatch = url.pathname.match(/^\/docs\/([^/]+)\/(ws|snapshot|comments)$/);
    if (!docMatch) {
      return new Response("not found", { status: 404, headers: corsHeaders(origin) });
    }

    let claims: AuthClaims;
    try {
      claims = await authenticate(req, env);
    } catch (e) {
      if (e instanceof Response) return e;
      return new Response(`auth error: ${(e as Error).message}`, {
        status: 401,
        headers: corsHeaders(origin),
      });
    }

    const docId = docMatch[1];
    const action = docMatch[2];
    // Tenant-scoped DO id ensures cross-tenant isolation
    const doIdHash = `${claims.tenant_id}:${docId}`;
    const doId = env.COLLAB_DOC.idFromName(doIdHash);
    const stub = env.COLLAB_DOC.get(doId);

    // Forward request to the DO with auth claims propagated as headers
    const forwardReq = new Request(req.url, {
      method: req.method,
      headers: {
        ...Object.fromEntries(req.headers),
        "X-MF-User-Id": claims.sub,
        "X-MF-Tenant-Id": claims.tenant_id,
        "X-MF-Action": action,
      },
      body: req.method === "POST" ? await req.arrayBuffer() : undefined,
    });
    return stub.fetch(forwardReq);
  },
};

export { CollabDoc } from "./durable_object";
