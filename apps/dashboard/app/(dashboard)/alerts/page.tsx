import { ContractError } from "@/components/domain/ContractError";
import { DataTable } from "@/components/ui/DataTable";
import { getWebhooks } from "@/lib/api/contracts";
import { requireSession } from "@/lib/auth/server-session";
import { Badge } from "@/components/ui/Badge";

export default async function AlertsPage() {
  const session = await requireSession();
  try {
    const response = await getWebhooks(session.tenantId);
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Alerts</p><h1>Alert delivery</h1><p className="muted">Webhook notification channels configured for this organization.</p></div></header><section className="panel"><DataTable rows={response.webhooks} columns={[{ key: "id", label: "Endpoint", render: (row) => row.url }, { key: "events", label: "Events", render: (row) => row.event_types?.join(", ") ?? "Not specified" }, { key: "status", label: "Status", render: (row) => <Badge tone={row.active ? "success" : "warning"}>{row.active ? "Active" : "Disabled"}</Badge> }, { key: "created", label: "Created", render: (row) => row.created_at ?? "Not available" }]} emptyMessage="No webhook alert channels were returned for this organization." /></section></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Alert data is unavailable."} /></div>;
  }
}
