# Deploy ModelForge SaaS Shell — 30-min Playbook

This is the user-side checklist to flip the SaaS shell from "scaffolded
locally" to "live on the public internet at a URL anyone can hit."

**Total time: ~30 minutes. Total spend: $0.**

Everything in this playbook uses free tiers. The first paying customer
will incur Stripe transaction fees (~3% + €0.30) and nothing else.

---

## What you get when you finish

| URL | Service | Free-tier limit |
|---|---|---|
| `https://<your-name>-modelforge.onrender.com` | FastAPI app (auth + tenants + billing webhook) | 750 hr/mo, 512 MB RAM |
| `https://modelforge-collab.<you>.workers.dev` | Yjs realtime collab (WebSocket) | 100K req/day, 1M DO req/mo |
| Supabase Postgres + Auth | Tenant DB + JWT issuer | 500 MB DB, 50K MAU |
| Stripe test mode | Billing webhook ingress | unlimited (no fixed cost; only fees on real transactions) |

GitHub Actions auto-deploys both services on every push to `master` once
you've added 4 secrets.

---

## Pre-flight (1 min)

```bash
cd "C:/Users/lukep/Desktop/Projects AI/ModelForge"
git status              # confirm clean tree
gh repo view            # confirm GitHub remote authenticated
```

---

## Step 1 — Supabase project (~5 min)

1. Open <https://supabase.com/dashboard/sign-in> → sign in (free, no credit card).
2. **New project**:
   - Name: `modelforge-prod`
   - Database password: generate a strong one, save to `~/.claude/secrets/supabase.env`
   - Region: `Frankfurt` (eu-central-1) for Italian users
   - Pricing plan: **Free**
3. Wait ~2 min for provisioning. When ready:
   - **Settings → API**: copy the `Project URL` and `anon` and `service_role` keys
   - **Settings → API → JWT Secret**: copy the JWT secret
4. **SQL Editor → New query**: paste the entire content of `migrations/001_supabase_init.sql` and Run. Should return "Success. No rows returned." Verify with:
   ```sql
   SELECT tablename FROM pg_tables WHERE schemaname='public'
     AND tablename IN ('tenants','tenant_members','workbooks','audit_events_saas','billing_events');
   ```
   → expect 5 rows.
5. Save the 4 values to `~/.claude/secrets/supabase.env`:
   ```bash
   SUPABASE_URL=https://<project-ref>.supabase.co
   SUPABASE_ANON_KEY=eyJ...
   SUPABASE_SERVICE_ROLE_KEY=eyJ...
   SUPABASE_JWT_SECRET=<long-random-string>
   ```

---

## Step 2 — Render web service (~5 min)

1. Open <https://dashboard.render.com/sign-in> → sign in via GitHub.
2. **New → Blueprint** → connect this repo (`Whatsonyourmind/modelforge`) → select branch `master`.
3. Render reads `deploy/render.yaml` and proposes 2 services (`modelforge-saas` web + `modelforge-audit-listed-cron` cron). Click **Apply**.
4. After provision, on the `modelforge-saas` service:
   - **Environment** tab → add the 4 Supabase env vars from Step 1
   - Add `MODELFORGE_DISABLE_DEMO=1` (turns off the unauthenticated demo UI)
   - **Settings → Deploy Hook** → copy the URL → save as GitHub secret `RENDER_DEPLOY_HOOK_URL` (Step 5 below)
5. First deploy runs automatically (~3-5 min). When green:
   ```bash
   curl https://<your-name>-modelforge.onrender.com/healthz
   # → {"status":"ok","service":"modelforge-web"}
   ```

---

## Step 3 — Cloudflare Workers (Yjs collab) (~5 min)

1. Open <https://dash.cloudflare.com/sign-up> → sign in (free, no credit card).
2. **My Profile → API Tokens → Create Token**:
   - Template: **Edit Cloudflare Workers**
   - Account Resources: All accounts
   - Zone Resources: All zones
   - **Continue → Create Token** → copy the token
3. **Workers & Pages → Overview**: copy the `Account ID` shown on the right sidebar.
4. Save both as GitHub secrets (Step 5 below):
   - `CLOUDFLARE_API_TOKEN` = token from step 2
   - `CLOUDFLARE_ACCOUNT_ID` = account id from step 3

The `web/collab-worker/wrangler.toml` is already config'd. The GitHub Actions workflow will run `wrangler deploy` on next push.

---

## Step 4 — Stripe (test mode, 5 min)

1. Open <https://dashboard.stripe.com/register> → sign in (free).
2. **Developers → API keys → Test mode** → copy `Secret key` (`sk_test_...`).
3. **Developers → Webhooks → Add endpoint**:
   - Endpoint URL: `https://<your-name>-modelforge.onrender.com/api/v1/billing/webhook`
   - Events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
   - **Add endpoint → Reveal signing secret** → copy `whsec_...`
4. Add to Render service env vars (Step 2 above):
   - `STRIPE_SECRET_KEY=sk_test_...`
   - `STRIPE_WEBHOOK_SECRET=whsec_...`

---

## Step 5 — Add 4 GitHub secrets (~2 min)

```bash
gh secret set RENDER_DEPLOY_HOOK_URL  # paste from Step 2.4
gh secret set CLOUDFLARE_API_TOKEN    # paste from Step 3.2
gh secret set CLOUDFLARE_ACCOUNT_ID   # paste from Step 3.3
gh secret set SUPABASE_JWT_SECRET     # paste from Step 1.3
```

Verify:
```bash
gh secret list
```

---

## Step 6 — Trigger deploy (1 min)

```bash
git commit --allow-empty -m "deploy: kick off first SaaS deploy"
git push origin master
```

Open the Actions tab — `Deploy` workflow should be running. Both jobs
(`deploy-render` + `deploy-cf-worker`) should turn green in ~3-5 min.

---

## Step 7 — Smoke test (~3 min)

```bash
APP=https://<your-name>-modelforge.onrender.com
WORKER=https://modelforge-collab.<you>.workers.dev

# 1. Healthchecks
curl $APP/healthz
curl $WORKER/healthz

# 2. SaaS healthz reports prod env vars wired
curl $APP/api/v1/healthz
# → expect: "supabase_jwt_configured":true, "stripe_webhook_configured":true,
#   "auth_dev_bypass":false

# 3. Sign up a test user via Supabase Auth (use the dashboard or gotrue API).
#    The auto-provision-personal-tenant trigger creates a tenant for the user.

# 4. Get a JWT for the test user (Supabase dashboard → Auth → user → "Get JWT")
#    or sign in via your frontend.

JWT=eyJ...    # paste user JWT

# 5. Whoami end-to-end (production auth path)
curl -H "Authorization: Bearer $JWT" $APP/api/v1/auth/whoami
# → expect: {"user_id":"<uuid>","tenant_id":"tenant_<...>","email":"...",
#            "role":"member","is_dev_bypass":false}

# 6. List my tenants
curl -H "Authorization: Bearer $JWT" $APP/api/v1/tenants
```

If all 6 calls succeed → **the SaaS shell is live on the public internet
behind real auth**.

---

## Step 8 — First Stripe transaction test

In Stripe Dashboard (test mode):

1. **Products → Add product**: "Per-seat monthly" / $99/mo recurring.
2. **Payment links → Create**: select the product, add metadata `tenant_id=<your-tenant-id>` + `user_id=<your-user-id>`.
3. Open the payment link in a browser, pay with `4242 4242 4242 4242` (Stripe test card).
4. Webhook should fire → check Render logs:
   ```
   [billing.webhook] ok event_type=checkout.session.completed amount=9900
   ```
5. Verify the audit row was written:
   ```bash
   curl -H "Authorization: Bearer $JWT" \
        $APP/api/v1/tenants/<your-tenant-id>/workbooks
   # (audit slices live under storage/<tenant_id>/audit/ on the Render disk)
   ```

---

## Step 9 — Wire your domain (optional, ~5 min)

1. Render → service → **Settings → Custom Domain** → add `app.modelforge.dev` (or your domain).
2. CNAME `app.modelforge.dev → <your-name>-modelforge.onrender.com` in your DNS.
3. Wait for SSL provision (~2 min).
4. Update Stripe webhook endpoint to the custom domain.

---

## Operating notes

- **Render free tier sleeps after 15 min idle.** First request after idle takes ~30s. Acceptable for early design partners; upgrade to Starter ($7/mo) when you have ≥3 active users.
- **Supabase free DB pauses after 7 days inactivity.** Pings on real traffic prevent pause. Upgrade to Pro ($25/mo) when paying customers exist.
- **Cloudflare Workers free tier is generous** — won't hit limits at design-partner scale.
- **Stripe is pure transactional.** No fixed cost; charged 2.9% + €0.30 per US payment, 1.5% + €0.25 per EU.

**Total monthly cost at first 10 paying customers**: $0-7 (only Render Starter if you upgrade off free).

---

## Rollback

```bash
git push -f origin <prior-good-commit>:master
```

Render auto-redeploys the prior commit. Worker re-deploys via the same flow.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/api/v1/healthz` shows `supabase_jwt_configured: false` in prod | Render env var not set | Add `SUPABASE_JWT_SECRET` in Render dashboard, restart service |
| 401 on `/api/v1/auth/whoami` with valid JWT | JWT signed by different secret | Regenerate JWT secret in Supabase, update Render env var |
| Stripe webhook returns 400 "verification" | `STRIPE_WEBHOOK_SECRET` mismatch | Re-copy from Stripe dashboard → re-add to Render |
| Worker route returns 404 | Route path mismatch | Check `web/collab-worker/src/index.ts` `docMatch` regex |
| Render deploy times out at "Installing dependencies" | Free tier RAM limit | Switch buildCommand to `pip install --no-cache-dir` |
| GitHub Actions deploy job skipped | Secret not set | Run `gh secret list` — add missing |

---

## Post-deploy: open the door for a design partner

Once live, the call-to-action for outreach changes from:
> "We're building a tool, want to take a look?"

to:
> "Here's a live URL. Sign up at `app.modelforge.dev`, get a personal tenant
> in 5 seconds, ingest one of your real deal teasers and tell me where the
> output is wrong."

That's the customer-pull move all three IC reviewers (round-3 + round-4)
are waiting for. Without it, the next dollar of dev work doesn't move
investability.

---

## What's intentionally NOT in this playbook

- **Frontend (Next.js / React / Tailwind)** — the API is live; the UI layer
  is week-2 work, not week-1. For now, demo via curl + Postman.
- **Custom OAuth providers** — Supabase email-link auth is sufficient for
  10 design partners. Google / Microsoft SSO is Phase B.
- **SOC 2 audit kickoff** — €15-30K spend; not in this no-spend deploy.
- **Bloomberg / Refinitiv data** — €25-300K/yr; the free Yahoo + FRED
  stack covers screening + plausibility-check use cases.

---

## Appendix — files referenced

- `deploy/render.yaml` — Render blueprint
- `web/collab-worker/wrangler.toml` — CF Worker config
- `migrations/001_supabase_init.sql` — Supabase schema
- `modelforge/web/saas_routes.py` — SaaS API surface
- `modelforge/saas/auth.py` — JWT verification
- `modelforge/saas/tenant.py` — tenant store + RLS-friendly schema
- `modelforge/saas/billing.py` — Stripe webhook handler
- `.github/workflows/deploy.yml` — auto-deploy on push
