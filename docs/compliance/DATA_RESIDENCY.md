# PesaGuard Data Residency Decision

This document satisfies requirements **RES-1** through **RES-5** from Addendum III. It records where tenant data is stored, the hosting decision for pilot deployments, and the legal basis for any unavoidable cross-border transfer.

> **Validation status:** Hosting provider and region choices marked *pending real-world input* must be confirmed during Phase 0 pilot discovery and before production go-live.

---

## 1. Data categories and storage locations (RES-1)

| Data category | What it contains | Primary store | Pilot default region | Jurisdiction |
|---|---|---|---|---|
| **Application / reconciliation data** | Discrepancies, incidents, tenant config, audit trails | PostgreSQL (`postgres` service) | `ke-1` (Kenya / East Africa) | Kenya — *pending confirmation of exact provider region* |
| **Event stream** | M-Pesa webhook payloads, reconciliation events | Kafka (`kafka` service) | Same as primary (`ke-1`) | Same as primary |
| **Backups** | `pg_dump` snapshots, optional S3 copies | Local backup dir + optional object storage | Must match primary (`BACKUP_REGION=ke-1`) | Same as primary — **RES-4** |
| **Application logs** | Structured service logs, alert delivery logs | Container stdout / log aggregator | Same as primary (`LOG_REGION=ke-1`) | Same as primary |
| **Alert metadata** | SMS/Slack/email delivery records | PostgreSQL + external provider logs | Primary in `ke-1`; see cross-border table below | Mixed — see §3 |

Personal data in scope includes phone numbers, transaction references, and operator contact details used in reconciliation and alerting.

---

## 2. Hosting options and tradeoffs (RES-2)

### Option A — Kenya / East Africa region (recommended for pilot)

| Provider | Region / option | Notes |
|---|---|---|
| **AWS** | `af-south-1` (Cape Town) | Closest AWS region to Kenya; not in-country but within Africa. Latency to Nairobi typically acceptable for pilot workloads. |
| **GCP** | No Kenya region; nearest is `europe-west1` or multi-region | Higher latency; cross-border transfer documentation required. |
| **Azure** | `southafricanorth` (Johannesburg) | Similar tradeoff to AWS Cape Town. |
| **Local Kenyan hosting** | e.g. Safaricom Cloud, local VPS/datacenter | Strongest in-country residency story; ops maturity and managed Postgres/Kafka availability *pending real-world input*. |

**Pilot recommendation:** Prefer **Option A** with `DEPLOYMENT_REGION=ke-1` mapped to an East Africa–adjacent cloud region (e.g. AWS `af-south-1`) until a customer explicitly requires in-country hosting or a local provider is selected.

### Option B — Default US/EU region (not recommended without legal review)

Lower cost and broader managed-service availability, but triggers cross-border transfer obligations under Kenya's Data Protection Act (2019). Do not use for pilot without documented legal basis and customer consent.

---

## 3. Cross-border transfers (RES-3)

Some managed services cannot run inside the chosen primary region. When used, document the service, data involved, and legal basis:

| Service | Data transferred | Destination | Legal basis (Kenya DPA) | Mitigation |
|---|---|---|---|---|
| **Africa's Talking (SMS)** | Phone number, alert text snippet | Provider infrastructure (may route outside Kenya) | Legitimate interest / contract performance for critical alerts; *pending legal review* | Minimize PII in SMS body; tenant opt-in to SMS channel |
| **Slack webhooks** | Alert summary, transaction IDs | Slack (typically US) | Contract performance; *pending legal review* | Use Slack only when tenant accepts; redact where possible |
| **SMTP / email providers** | Recipient email, incident details | Provider-dependent | Contract performance | Tenant-configured recipients only |
| **Daraja (Safaricom)** | M-Pesa transaction data | Safaricom Kenya | Primary processing in Kenya | N/A — in-scope payment rail |

Set `cross_border_transfer_allowed: false` on a tenant unless legal review and customer agreement explicitly permit cross-border alert delivery.

---

## 4. Backup residency (RES-4)

Backups **must** stay in the same jurisdiction as primary data unless RES-3 is satisfied for that backup destination.

- `scripts/backup_postgres.sh` writes locally by default; optional `S3_BUCKET` upload must use a bucket in `BACKUP_REGION`.
- Tenant settings expose `backup_region` (defaults to `deployment_region`).
- Do not configure cross-region replication or off-shore backup storage without updating this document and tenant DPA.

---

## 5. Per-deployment configuration (RES-5)

Hosting region is **not hardcoded**. Configure per deployment via environment and tenant settings:

| Mechanism | Variable / field | Default |
|---|---|---|
| Docker Compose | `DEPLOYMENT_REGION`, `BACKUP_REGION`, `LOG_REGION` | `ke-1` |
| Tenant settings | `deployment_region`, `backup_region`, `log_region` | Inherit from `default` tenant |
| Admin API | `GET /admin/tenant/<id>/residency` | Returns merged residency context |

Different tenants could theoretically use different regions in a future multi-region deployment; the current pilot uses a single deployment region shared by all tenants.

---

## 6. Operational checklist before go-live

- [ ] Confirm cloud provider and exact region with pilot customer (*pending real-world input*)
- [ ] Verify Postgres, Kafka, and backup storage all reside in the chosen region
- [ ] Set `cross_border_transfer_allowed` per tenant after legal review
- [ ] Record signed-off version of this document in the pilot readiness pack
- [ ] Re-run checklist if any managed service region changes

---

## Related files

- `docker/docker-compose.yml` — deployment region env vars
- `infra/docker-compose.yml` — staging reference with residency note
- `tenant_settings.json` — per-tenant `deployment_region`, `backup_region`, `log_region`
- `docs/compliance/DATA_RESIDENCY.md` — canonical compliance reference
