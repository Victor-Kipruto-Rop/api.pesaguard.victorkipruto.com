import { BackendPendingPage } from "@/components/domain/BackendPendingPage";
import { ContractError } from "@/components/domain/ContractError";
import { DataTable } from "@/components/ui/DataTable";
import { getTransactions } from "@/lib/api/contracts";
import { requireSession } from "@/lib/auth/server-session";
import { formatCurrency, formatDate } from "@/lib/utils/format";

export default async function TransactionsPage() {
  const session = await requireSession();
  try {
    const response = await getTransactions(session.tenantId);
    const rows = response.items.map((item) => ({ ...item, id: item.trans_id }));
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Transactions</p><h1>Transaction explorer</h1><p className="muted">Tenant-scoped transaction records from the reconciliation API.</p></div></header><section className="panel"><DataTable rows={rows} columns={[{ key: "id", label: "Transaction", render: (row) => row.trans_id }, { key: "time", label: "Timestamp", render: (row) => formatDate(row.created_at ?? row.trans_time ?? "") }, { key: "amount", label: "Amount", render: (row) => formatCurrency(row.trans_amount) }, { key: "channel", label: "Channel", render: (row) => row.business_short_code ?? "Not specified" }, { key: "customer", label: "Customer", render: (row) => row.msisdn ? `••••${row.msisdn.slice(-4)}` : "Masked" }]} emptyMessage="No transactions were returned for this organization." /></section></div>;
  } catch (error) {
    return <div className="page-shell"><BackendPendingPage eyebrow="Workspace / Transactions" title="Transaction explorer" detail="The backend returned no usable transaction dataset." /><ContractError message={error instanceof Error ? error.message : "Transaction data is unavailable."} /></div>;
  }
}
