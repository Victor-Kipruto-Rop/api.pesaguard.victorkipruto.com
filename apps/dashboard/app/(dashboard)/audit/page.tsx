import { ContractError } from "@/components/domain/ContractError";
import { DataTable } from "@/components/ui/DataTable";
import { getAudit } from "@/lib/api/contracts";
import { requireSession } from "@/lib/auth/server-session";
import { formatDate } from "@/lib/utils/format";

export default async function AuditPage() {
  const session = await requireSession();
  try {
    const response = await getAudit(session.tenantId);
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Audit</p><h1>Audit trail</h1><p className="muted">Historical action records scoped to the authenticated organization.</p></div></header><section className="panel"><DataTable rows={response.items.map((item) => ({ ...item, id: item.id }))} columns={[{ key: "time", label: "Timestamp", render: (row) => formatDate(row.created_at ?? "") }, { key: "actor", label: "Actor", render: (row) => row.actor ?? "System" }, { key: "action", label: "Action", render: (row) => row.action ?? "Unknown" }, { key: "details", label: "Details", render: (row) => typeof row.details === "string" ? row.details : "Recorded" }]} emptyMessage="No audit events were returned for this organization." /></section></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Audit data is unavailable."} /></div>;
  }
}
