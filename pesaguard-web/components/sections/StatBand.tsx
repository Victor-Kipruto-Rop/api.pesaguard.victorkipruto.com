import { Metric } from "@/components/ui/Card";
import { cn } from "@/lib/utils/cn";
import type { MetricBlock } from "@/types/content";

/**
 * Band of figures.
 *
 * Only pass numbers that come from a measured source, in the repository or from
 * a customer's own environment. Placeholder statistics are worse than no
 * statistics on a page about financial controls.
 */
export function StatBand({ metrics, className }: { metrics: MetricBlock[]; className?: string }) {
  if (metrics.length === 0) {
    return null;
  }

  return (
    <div className={cn("stat-band", className)}>
      {metrics.map((metric) => (
        <Metric key={metric.label} label={metric.label} value={metric.value} />
      ))}
    </div>
  );
}