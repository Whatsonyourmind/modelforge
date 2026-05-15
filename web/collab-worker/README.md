# ModelForge Collab Worker

Yjs realtime collaboration server on **Cloudflare Workers + Durable Objects**.

The free tier covers tens of concurrent design-partner users (100K req/day,
1M DO requests/month, ~100 concurrent WebSocket connections per Worker).

## Architecture

```
   Python CommentStore  ─POST── /docs/<id>/comments ─┐
   (modelforge.collab)  ─GET ── /docs/<id>/comments ─┤
                                                     │
   Browser UI (Yjs client) ─WS── /docs/<id>/ws  ─────┼──► CollabDoc DO (1 per workbook)
                                                     │       ├─ Y.Doc in-memory
                                                     │       │   ├─ ymap "comments"
                                                     │       │   ├─ ymap "review"
                                                     │       │   └─ ymap "presence"
                                                     │       └─ DO storage (persisted Y state)
   Auth: Supabase JWT (HS256)  ─Authorization── ─────┘
```

## Tenant isolation

Every Durable Object id is `${tenantId}:${docId}`. Cross-tenant access is
impossible because the Worker derives the DO id from the *authenticated*
tenant_id claim, not from the URL path. JWT verification is HS256 against
`SUPABASE_JWT_SECRET` — same code path as `modelforge/saas/auth.py`.

## Local dev

```bash
cd web/collab-worker
npm install
npx wrangler dev   # binds http://localhost:8787
```

Without `SUPABASE_JWT_SECRET` set, the Worker runs in dev-mode (decodes JWT
without signature check). Never deploy without the secret.

## Deploy (free tier)

```bash
npx wrangler login           # one-time
npx wrangler deploy          # ships to <subdomain>.workers.dev
npx wrangler secret put SUPABASE_JWT_SECRET   # prod secret
```

The default `wrangler.toml` provisions one Durable Object class (`CollabDoc`).
Deploy is idempotent.

## Capacity envelope (free tier)

| Resource | Free limit | At scale of |
|---|---|---|
| Worker requests | 100K / day | ~30 daily-active design partners w/ 5 docs each |
| DO requests | 1M / month | ~100 daily-active users |
| DO storage | 5 GB | ~10K Y.Docs of typical size |
| WebSocket concurrency | ~100 per Worker | early multi-tenant SaaS |
| CPU time | 30s / request | All sync ops are <100ms |

When you hit any of these: upgrade to Workers Paid ($5/mo) which raises all
limits 10-50x.

## Python client

See `modelforge/collab/realtime.py` for the Python WebSocket client that
mirrors `CommentStore` events into the Y.Doc via the REST `/comments`
endpoint (no Y CRDT logic in Python — the Worker handles merge).

## Architecture notes

- **No third-party host required**: Cloudflare deploys + DO storage.
- **Eviction**: DO instances evict from edge memory when no active WS.
  State persists to DO storage; reconnects warm-load.
- **Bursty updates debounced**: persistence trails by 1s to coalesce.
- **CRDT** (Yjs) means concurrent edits never lose data; conflict resolution
  is automatic.
