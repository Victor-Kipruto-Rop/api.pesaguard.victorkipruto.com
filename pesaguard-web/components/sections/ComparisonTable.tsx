import { Check, Minus } from "lucide-react";
import type { ComparisonRow } from "@/types/content";

/**
 * Comparison table.
 *
 * Both columns describe behaviour, not marketing. `oursNegative` exists so the
 * PesaGuard column can honestly show a limitation (today, M-Pesa is the only
 * live rail) instead of implying parity with everything else.
 */
export function ComparisonTable({
  rows,
  oursHeading = "With PesaGuard",
  othersHeading = "Without it",
  caption,
}: {
  rows: ComparisonRow[];
  oursHeading?: string;
  othersHeading?: string;
  caption?: string;
}) {
  if (rows.length === 0) {
    return null;
  }

  return (
    <div className="comparison">
      <div className="comparison-row">
        <span>{caption ?? "Control"}</span>
        <span>{oursHeading}</span>
        <span>{othersHeading}</span>
      </div>
      {rows.map((row) => (
        <div className="comparison-row" key={row.label}>
          <strong>{row.label}</strong>
          <span className={row.oursNegative ? "negative" : undefined}>
            {row.oursNegative ? <Minus aria-hidden="true" size={15} /> : <Check aria-hidden="true" size={15} />}
            {row.ours}
          </span>
          <span className="negative">
            <Minus aria-hidden="true" size={15} />
            {row.others}
          </span>
        </div>
      ))}
    </div>
  );
}