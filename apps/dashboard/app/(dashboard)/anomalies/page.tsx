import { ContractError } from "@/components/domain/ContractError";
import { DataTable } from "@/components/ui/DataTable";
import { getDiscrepancies } from "@/lib/api/contracts";
import { Badge } from "@/components/ui/Badge";
import { AnomalyActions } from "@/components/anomalies/AnomalyActions";

export default async function AnomaliesPage() {
  try {
    const response = await getDiscrepancies({ resolved: "open", perPage: 100 });
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Anomalies</p><h1>Anomaly command center</h1><p className="muted">Open discrepancy records and their backend-assigned severity.</p></div></header><section className="panel"><DataTable rows={response.items.map((item) => ({ ...item, id: item.id }))} columns={[{ key: "id", label: "Alert", render: (row) => row.id }, { key: "transaction", label: "Transaction", render: (row) => row.trans_id ?? "Not linked" }, { key: "rule", label: "Rule", render: (row) => row.anomaly_type ?? "Not specified" }, { key: "severity", label: "Risk", render: (row) => <Badge tone={row.severity === "critical" ? "danger" : row.severity === "warning" ? "warning" : "neutral"}>{row.severity ?? "unknown"}</Badge> }, { key: "status", label: "Status", render: (row) => row.status ?? "unknown" }, { key: "assignee", label: "Assignee", render: (row) => row.assignee ?? "Unassigned" }, { key: "actions", label: "Actions", render: (row) => <AnomalyActions id={row.id} /> }]} emptyMessage="No open anomalies were returned for this organization." /></section></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Anomaly data is unavailable."} /></div>;
  }
}
