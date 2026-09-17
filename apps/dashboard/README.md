# PesaGuard Dashboard

The authenticated application lives in `apps/dashboard` and is intentionally isolated from the public `pesaguard-web` site.

## Current contract boundary

The existing backend exposes token login at `/auth/login`, token verification at `/auth/verify`, token revocation at `/auth/revoke`, and service health at `/health`. Browser authentication is proxied through same-origin Next route handlers so the backend bearer token is kept in an `HttpOnly` cookie rather than browser JavaScript.

The dashboard now consumes the backend's existing tenant-scoped contracts for transactions, discrepancy/anomaly records, reconciliation analytics, reports, providers, webhook alerts, audit history, dead letters, settings, and health. Customer directory, API-key management, MFA, and richer workflow mutations remain explicitly pending because no corresponding stable backend read/write contract was found. No production fixtures or simulated realtime status are used.

Browser requests to backend data go through the authenticated `/api/backend/*` proxy, which forwards the server-held session token and preserves backend authorization as the source of truth.

## Configuration

Copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL`. Never place credentials, signing secrets, or provider secrets in `NEXT_PUBLIC_*` variables.

## Checks

```bash
npm install
npm run typecheck
npm run lint
npm run build
```

Node/npm must be available on the PATH. Production deployment should set `PESAGUARD_API_URL` as a server-only variable and use HTTPS so the session cookie is secure.
