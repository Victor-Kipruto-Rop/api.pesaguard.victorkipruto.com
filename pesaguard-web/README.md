# PesaGuard web

The public PesaGuard website lives in this folder as an isolated Next.js App Router project. The backend remains in the parent repository.

## Run locally

Install Node.js 20+ and npm, then run:

```bash
npm install
npm run dev
```

Set `PESAGUARD_API_URL` to enable the server-side status health check. No backend secret is exposed to the browser.

## Checks

```bash
npm run lint
npm run typecheck
npm test
npm run test:e2e
npm run build
```
