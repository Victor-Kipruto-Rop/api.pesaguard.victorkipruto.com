import { ContractError } from "@/components/domain/ContractError";
import { DataTable } from "@/components/ui/DataTable";
import { getProviders } from "@/lib/api/contracts";
import { Badge } from "@/components/ui/Badge";

export default async function IntegrationsPage() {
  try {
    const response = await getProviders();
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Integrations</p><h1>Integration center</h1><p className="muted">Provider configuration and health state returned by the backend.</p></div></header><section className="panel"><DataTable rows={response.providers} columns={[{ key: "id", label: "Provider", render: (row) => row.name }, { key: "type", label: "Type", render: (row) => row.provider_type ?? "Unknown" }, { key: "connection", label: "Connection", render: (row) => <Badge tone={row.connection_status === "connected" ? "success" : "warning"}>{row.connection_status ?? "unknown"}</Badge> }, { key: "health", label: "Health", render: (row) => row.health_status ?? "Unknown" }, { key: "status", label: "Status", render: (row) => row.status ?? "Unknown" }]} emptyMessage="No providers are configured for this organization." /></section></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Provider data is unavailable."} /></div>;
  }
}
