import type { IntegrationSummary } from "@/types/content";

/**
 * Payment rails and channels, with an explicit availability value.
 *
 * Keep this list honest: `evidence` points at the place in the repository or
 * documentation that supports the claim. Anything we have not built stays
 * `not-started` until an adapter, its tests and its docs exist.
 */
export const integrations: IntegrationSummary[] = [
  {
    name: "M-Pesa (Safaricom Daraja)",
    href: "/integrations/mpesa",
    availability: "available",
    summary:
      "Daraja callbacks are received, validated, de-duplicated and matched against internal records in real time.",
    evidence: "docs/product/PILOT_READINESS.md · docs/architecture/CURRENT_ARCHITECTURE.md",
  },
  {
    name: "Outbound webhooks",
    href: "/integrations/webhooks",
    availability: "available",
    summary:
      "PesaGuard delivers signed event notifications with delivery attempts, retries and a dead-letter path.",
    evidence: "webhook_manager.py · webhook delivery tables and migrations",
  },
  {
    name: "Airtel Money",
    href: "/integrations/airtel-money",
    availability: "not-started",
    summary:
      "Named on this site so the scope is clear to buyers. No adapter, tests or documentation exist yet.",
    evidence: "docs/architecture/CURRENT_ARCHITECTURE.md — Airtel Money is not implemented",
  },
  {
    name: "Bank rails",
    href: "/integrations/banks",
    availability: "not-started",
    summary:
      "Statement and settlement imports from banks are out of today's scope. The design keeps room for them.",
    evidence: "docs/architecture/CURRENT_ARCHITECTURE.md — bank adapters not implemented",
  },
  {
    name: "Point of sale",
    href: "/integrations/pos",
    availability: "not-started",
    summary:
      "In-store terminal feeds are not ingested today. We only claim what the M-Pesa pipeline does.",
    evidence: "docs/product/PRODUCT_SCOPE.md — M-Pesa is the active scope",
  },
];

export const availableIntegrations = integrations.filter(
  (integration) => integration.availability === "available",
);

export const pendingIntegrations = integrations.filter(
  (integration) => integration.availability !== "available",
);
