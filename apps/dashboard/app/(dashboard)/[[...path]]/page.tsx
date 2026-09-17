import { BackendPendingPage } from "@/components/domain/BackendPendingPage";

type CatchAllProps = { params: Promise<{ path?: string[] }> };

const labels: Record<string, string> = {
  transactions: "Transactions", pending: "Pending transactions", failed: "Failed transactions", flagged: "Flagged transactions", duplicates: "Duplicate transactions", search: "Transaction search",
  reconciliation: "Reconciliation", runs: "Reconciliation runs", matched: "Matched records", unmatched: "Unmatched records", mismatches: "Mismatches", manual: "Manual matching", rules: "Reconciliation rules", exceptions: "Exceptions",
  anomalies: "Anomalies", alerts: "Anomaly alerts", investigations: "Investigations", "high-risk": "High-risk anomalies",
  integrations: "Integrations", mpesa: "M-Pesa", "airtel-money": "Airtel Money", banks: "Banks", pos: "POS", webhooks: "Webhooks", health: "Integration health",
  customers: "Customers", segments: "Customer segments", audit: "Audit", events: "Audit events", "user-activity": "User activity", "security-events": "Security events",
  developer: "Developer", "api-keys": "API keys", usage: "API usage", logs: "API logs", documentation: "Developer documentation",
  operations: "Operations", services: "Services", workers: "Workers", queues: "Queues", dlq: "Dead-letter queue", infrastructure: "Infrastructure", incidents: "Incidents",
  settings: "Settings", profile: "Profile", organization: "Organization", team: "Team", roles: "Roles", permissions: "Permissions", security: "Security", notifications: "Notifications", data: "Data",
};

export default async function DashboardCatchAll({ params }: CatchAllProps) {
  const segments = (await params).path ?? [];
  const title = labels[segments.at(-1) ?? ""] ?? labels[segments[0] ?? ""] ?? "Workspace view";
  return <BackendPendingPage eyebrow={`Workspace / ${segments.join(" / ") || "Overview"}`} title={title} detail="This route is registered and ready for its tenant-scoped backend adapter." />;
}
