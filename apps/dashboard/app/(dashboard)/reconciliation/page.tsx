import { ContractError } from "@/components/domain/ContractError";
import { Card } from "@/components/ui/Card";
import { getReconciliationReport } from "@/lib/api/contracts";
import { formatPercentage } from "@/lib/utils/format";
import { DistributionList } from "@/components/reconciliation/DistributionList";

export default async function ReconciliationPage() {
  try {
    const report = await getReconciliationReport();
    const metrics = [{ label: "Incidents", value: report.summary.total_incidents }, { label: "Resolved", value: report.summary.resolved }, { label: "Open", value: report.summary.open }, { label: "Resolution rate", value: formatPercentage(report.summary.resolution_rate * 100) }];
    return (
      <div className="page-shell">
        <header className="page-header"><div><p className="eyebrow">Workspace / Reconciliation</p><h1>Reconciliation control</h1><p className="muted">Backend reconciliation incident report for the last {report.report_period_days} days.</p></div></header>
        <section className="metric-grid">{metrics.map((metric) => <article className="metric-card" key={metric.label}><div className="metric-top"><span>{metric.label}</span></div><div className="metric-value">{metric.value}</div></article>)}</section>
        <div className="overview-grid">
          <Card eyebrow="Severity distribution" title="Observed discrepancies"><div className="table-empty"><DistributionList values={report.by_severity} /></div></Card>
          <Card eyebrow="Status distribution" title="Current state"><div className="table-empty"><DistributionList values={report.by_status} /></div></Card>
        </div>
      </div>
    );
  } catch (error) {
    return <div className="page-shell"><ContractError message={error instanceof Error ? error.message : "Reconciliation data is unavailable."} /></div>;
  }
}
