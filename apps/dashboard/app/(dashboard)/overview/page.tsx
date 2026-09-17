import { Activity, ArrowUpRight, CircleAlert, Gauge, RefreshCw, ShieldCheck, WalletCards } from "lucide-react";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { Card } from "@/components/ui/Card";
import { requireSession } from "@/lib/auth/server-session";
import { getDiscrepancies, getReconciliationReport, getTransactions } from "@/lib/api/contracts";
import { formatPercentage } from "@/lib/utils/format";

function valueOrUnavailable<T>(result: PromiseSettledResult<T>, value: (data: T) => string, detail: string) {
  return result.status === "fulfilled" ? { value: value(result.value), detail } : { value: "Not available", detail: "Backend data unavailable" };
}

export default async function OverviewPage() {
  const session = await requireSession();
  const [transactions, discrepancies, criticalDiscrepancies, reconciliation] = await Promise.allSettled([getTransactions(session.tenantId), getDiscrepancies({ resolved: "open", perPage: 1 }), getDiscrepancies({ resolved: "open", severity: "critical", perPage: 1 }), getReconciliationReport()]);
  const transactionMetric = valueOrUnavailable(transactions, (data) => data.items.length.toLocaleString(), "Records returned by backend");
  const exceptionMetric = valueOrUnavailable(discrepancies, (data) => data.total.toLocaleString(), "Open discrepancy records");
  const criticalCount = criticalDiscrepancies.status === "fulfilled" ? criticalDiscrepancies.value.total : null;
  const reconciliationMetric = valueOrUnavailable(reconciliation, (data) => formatPercentage(data.summary.resolution_rate * 100), "Resolution rate for latest report period");
  const latencyMetric = { value: "Not available", detail: "No latency contract published" };

  return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">Workspace / Overview</p><h1>Operational overview</h1><p className="muted">Live financial controls for the selected organization.</p></div><div className="header-actions"><button className="button secondary" type="button"><RefreshCw size={15} />Refresh</button><button className="button primary" type="button"><ArrowUpRight size={15} />Customize</button></div></header><section className="metric-grid" aria-label="Operational metrics"><StatusPanel icon={<WalletCards />} label="Transactions" value={transactionMetric.value} detail={transactionMetric.detail} /><StatusPanel icon={<ShieldCheck />} label="Resolution rate" value={reconciliationMetric.value} detail={reconciliationMetric.detail} /><StatusPanel icon={<CircleAlert />} label="Open exceptions" value={exceptionMetric.value} detail={exceptionMetric.detail} /><StatusPanel icon={<Gauge />} label="Processing latency" value={latencyMetric.value} detail={latencyMetric.detail} /></section><section className="overview-grid"><Card eyebrow="Anomaly signal" title="Open critical anomalies"><div className="metric-value">{criticalCount === null ? "Not available" : criticalCount.toLocaleString()}</div><p className="muted">This count reflects the returned open anomaly page and is not inferred from transaction data.</p></Card><Card eyebrow="Operational boundary" title="Backend-backed overview"><div className="empty-state"><Activity size={20} aria-hidden="true" /><p>Metrics above are sourced from authenticated tenant-scoped endpoints.</p><span>Unavailable datasets remain explicitly labelled.</span></div></Card></section></div>;
}
