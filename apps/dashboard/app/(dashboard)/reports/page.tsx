import { ContractError } from "@/components/domain/ContractError";
import { DataTable } from "@/components/ui/DataTable";
import { getReports } from "@/lib/api/contracts";
import { requireSession } from "@/lib/auth/server-session";
import { formatDate } from "@/lib/utils/format";

export default async function ReportsPage() {
  const session = await requireSession();
  try {
    const response = await getReports(session.tenantId);
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Reports</p><h1>Report center</h1><p className="muted">Generated reconciliation reports for the authenticated organization.</p></div></header><section className="panel"><DataTable rows={response.items.map((item) => ({ ...item, id: item.id }))} columns={[{ key: "id", label: "Report", render: (row) => row.id }, { key: "type", label: "Type", render: (row) => row.report_type ?? "Unknown" }, { key: "period", label: "Period", render: (row) => `${formatDate(row.period_start ?? "")} - ${formatDate(row.period_end ?? "")}` }, { key: "status", label: "Status", render: (row) => row.status ?? "Unknown" }]} emptyMessage="No generated reports were returned for this organization." /></section></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Report data is unavailable."} /></div>;
  }
}
