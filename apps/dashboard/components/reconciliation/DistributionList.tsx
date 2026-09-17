export function DistributionList({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values);
  if (!entries.length) return <p>None recorded</p>;
  return <>{entries.map(([label, count]) => <p key={label}>{label}: {count}</p>)}</>;
}
