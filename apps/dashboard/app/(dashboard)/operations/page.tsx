import { ContractError } from "@/components/domain/ContractError";
import { DataTable } from "@/components/ui/DataTable";
import { getDeadLetters } from "@/lib/api/contracts";
import { requireSession } from "@/lib/auth/server-session";
import { formatDate } from "@/lib/utils/format";
import { DlqActions } from "@/components/operations/DlqActions";

export default async function OperationsPage() {
  const session = await requireSession();
  try {
    const response = await getDeadLetters(session.tenantId);
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Operations</p><h1>Operations center</h1><p className="muted">Dead-letter events returned by the tenant-scoped operations API.</p></div></header><section className="panel"><DataTable rows={response.items.map((item) => ({ ...item, id: item.id }))} columns={[{ key: "id", label: "Event", render: (row) => row.id }, { key: "reason", label: "Failure reason", render: (row) => row.reason ?? "Not specified" }, { key: "created", label: "Created", render: (row) => formatDate(row.created_at ?? "") }, { key: "processed", label: "Status", render: (row) => row.processed ? "Processed" : "Pending review" }, { key: "actions", label: "Actions", render: (row) => <DlqActions id={row.id} /> }]} emptyMessage="No dead-letter events were returned for this organization." /></section></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Operations data is unavailable."} /></div>;
  }
}
