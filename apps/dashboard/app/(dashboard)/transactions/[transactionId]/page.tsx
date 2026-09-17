import Link from "next/link";
import { ContractError } from "@/components/domain/ContractError";
import { Card } from "@/components/ui/Card";
import { getTransaction } from "@/lib/api/contracts";
import { requireSession } from "@/lib/auth/server-session";
import { formatCurrency, formatDate } from "@/lib/utils/format";

type TransactionDetailProps = { params: Promise<{ transactionId: string }> };

export default async function TransactionDetailPage({ params }: TransactionDetailProps) {
  const session = await requireSession();
  const { transactionId } = await params;
  try {
    const transaction = await getTransaction(session.tenantId, transactionId);
    return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Transactions / {transaction.trans_id}</p><h1>Transaction detail</h1><p className="muted">Tenant-scoped financial record and matched ledger context.</p></div><Link className="button secondary" href="/transactions">Back to transactions</Link></header><div className="overview-grid"><Card eyebrow="Financial record" title={transaction.trans_id}><dl className="settings-list"><div><dt>Amount</dt><dd>{formatCurrency(transaction.trans_amount)}</dd></div><div><dt>Timestamp</dt><dd>{formatDate(transaction.created_at ?? transaction.trans_time ?? "")}</dd></div><div><dt>Customer</dt><dd>{transaction.msisdn ? `••••${transaction.msisdn.slice(-4)}` : "Masked"}</dd></div><div><dt>Business short code</dt><dd>{transaction.business_short_code ?? "Not available"}</dd></div></dl></Card><Card eyebrow="Reconciliation" title="Matched context"><dl className="settings-list"><div><dt>Ledger reference</dt><dd>{transaction.matched_record?.internal_ref ?? "No match returned"}</dd></div><div><dt>Ledger status</dt><dd>{transaction.matched_record?.status ?? "Not available"}</dd></div><div><dt>Synced</dt><dd>{formatDate(transaction.matched_record?.synced_at ?? "")}</dd></div></dl></Card></div></div>;
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Transaction detail is unavailable."} /></div>;
  }
}
