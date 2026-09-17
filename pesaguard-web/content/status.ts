/**
 * Static service catalogue for the marketing status page.
 *
 * Kept as static content rather than runtime health data so the marketing site
 * reports exactly what it can observe and says plainly when it cannot.
 */

/** Names of services the status page tracks. */
export const serviceCatalogue = [
  { name: "Core API", detail: "Backend the dashboard and integrations query.", observedByProbe: true },
  {
    name: "M-Pesa reconciliation",
    detail: "Daraja-style reconciliation flows wrapped by PesaGuard.",
    observedByProbe: false,
    unobservedReason: "Reported as unknown unless a backend signal exists for it.",
  },
  {
    name: "Outbound webhooks",
    detail: "Provider-to-webhook notifications we send to integrators.",
    observedByProbe: false,
    unobservedReason: "Reported as unknown unless a backend signal exists for it.",
  },
  {
    name: "Airtel Money",
    detail: "Airtel Money rail support is not started yet.",
    observedByProbe: false,
    unobservedReason: "Not started — not monitored by any probe.",
  },
  {
    name: "Bank rails",
    detail: "Bank-based payout rails are not started yet.",
    observedByProbe: false,
    unobservedReason: "Not started — not monitored by any probe.",
  },
  {
    name: "POS integrations",
    detail: "Point-of-sale channels are not started yet.",
    observedByProbe: false,
    unobservedReason: "Not started — not monitored by any probe.",
  },
];

/** Incident list is always empty on the marketing site until a real incident is logged. */
export const unpublishedIncidentNote =
  "There are no recorded incidents right now. If something breaks, it will be listed here until it is resolved and a real timeline starts.";

/** Placeholder until the real content graph exists. */
export const recentIntegrations = ["M-Pesa (Daraja)", "Outbound webhooks"];

