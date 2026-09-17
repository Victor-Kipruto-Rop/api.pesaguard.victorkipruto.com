export type TableColumn<T> = { key: string; label: string; render: (row: T) => React.ReactNode };

export function DataTable<T extends { id: string }>({ columns, rows, emptyMessage = "No records are available." }: { columns: TableColumn<T>[]; rows: T[]; emptyMessage?: string }) {
  if (!rows.length) return <div className="table-empty">{emptyMessage}</div>;
  return <div className="table-scroll"><table><thead><tr>{columns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.id}>{columns.map((column) => <td key={column.key}>{column.render(row)}</td>)}</tr>)}</tbody></table></div>;
}
