import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";
import type { SpecRow } from "@/types/content";

export type Column = {
  /** Key used to read the cell value out of each row object. */
  key: string;
  label: string;
};

/**
 * Horizontally scrollable data table.
 *
 * Cells accept React nodes so a table can render availability badges, links or
 * code values without stringly-typed workarounds.
 */
export function DataTable({
  columns,
  rows,
  caption,
  className,
}: {
  columns: Column[];
  rows: Array<Record<string, ReactNode>>;
  caption?: string;
  className?: string;
}) {
  return (
    <div className={cn("table-wrap", className)}>
      <table className="data-table">
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={column.key}>{row[column.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Label/value fact list. Prefer this over a table for two-column facts. */
export function SpecList({ rows, className }: { rows: SpecRow[]; className?: string }) {
  return (
    <dl className={cn("spec-list", className)}>
      {rows.map((row) => (
        <div key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}
