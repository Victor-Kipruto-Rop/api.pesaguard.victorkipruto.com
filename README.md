# PesaGuard

**Real-time M-Pesa reconciliation and anomaly detection for SACCOs, e-commerce operators, and small fintechs.**

PesaGuard watches your M-Pesa transaction flow as it happens, flags mismatches before they become disputes, and catches suspicious patterns before they become losses — so finance teams stop reconciling by hand and stop finding fraud after the money's gone.

---

## The Problem

Most SACCOs and small fintechs in East Africa reconcile M-Pesa transactions manually — cross-checking statements, spreadsheets, and internal records days after the fact. By the time a discrepancy is spotted, the transaction window for recovery has often closed, and fraud patterns (duplicate payments, phantom reversals, callback spoofing) go unnoticed until they've repeated dozens of times.

## What PesaGuard Does

- **Real-time reconciliation** — ingests M-Pesa (Daraja) callbacks and matches them against internal records as transactions happen, not at end-of-day.
- **Anomaly detection** — flags irregular patterns (duplicate transaction IDs, amount mismatches, timing anomalies, suspicious reversal sequences) using rule-based and statistical checks.
- **Webhook-first architecture** — built for idempotent, secure ingestion of Safaricom Daraja callbacks, so retried or duplicate webhooks never corrupt your ledger.
- **Alerting** — surfaces discrepancies to your team immediately, not at month-end audit.
- **Built for scale-down as much as scale-up** — designed to run affordably for a single SACCO branch or a growing fintech, not just enterprise volumes.

## Who It's For

- **SACCOs** reconciling member contributions and loan repayments via M-Pesa
- **E-commerce operators** processing high volumes of STK Push payments
- **Small fintechs** that need fraud visibility without building a data team

## Status

🚧 **MVP live with a pilot customer.** Currently in production hardening — focused on webhook idempotency, security, and reliability before wider rollout.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | *(fill in: e.g. Django / FastAPI / Node.js)* |
| Transaction ingestion | Safaricom Daraja API (M-Pesa) |
| Deployment | Render (free-tier infrastructure) |
| Database | *(fill in: e.g. PostgreSQL)* |

*(Update the stack table with your actual services — happy to fill this in if you tell me the current setup.)*

## Getting Started

```bash
# Clone the repo
git clone https://github.com/Victor-Kipruto-Rop/pesaguard.git
cd pesaguard

# Install dependencies
# (add your install command here)

# Configure environment variables
cp .env.example .env
# Add your Daraja API credentials, database URL, etc.

# Run locally
# (add your run command here)
```

## Roadmap

- [x] Core reconciliation engine
- [x] MVP deployed with first pilot customer
- [ ] Webhook idempotency hardening
- [ ] Security audit (auth, secrets management, rate limiting)
- [ ] Multi-tenant support for additional SACCOs/fintechs
- [ ] Public dashboard for real-time transaction health

## Branding

PesaGuard uses a shield-and-"PG" mark in forest green — reflecting trust, security, and financial stewardship.

## Observability & Code Quality

PesaGuard ships with an optional Sentry-backed observability bootstrap and a Sourcery-enabled developer workflow.

Sentry:
- Production error tracking and exception monitoring
- Performance sampling and release/environment tagging
- Safe context enrichment and structured service tags

Sourcery:
- AI-powered code review on pull requests
- Repository-level quality configuration in `.sourcery.yaml`
- GitHub Actions workflow under `.github/workflows/sourcery.yml`

These integrations operate around the existing Flask and worker architecture and do not replace the repository’s business logic.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Contact

Built by **Victor Kipruto Rop** ([DataForge](https://github.com/Victor-Kipruto-Rop)) — data engineer focused on East African fintech infrastructure.

For pilot inquiries or partnership questions, reach out via [GitHub](https://github.com/Victor-Kipruto-Rop).
