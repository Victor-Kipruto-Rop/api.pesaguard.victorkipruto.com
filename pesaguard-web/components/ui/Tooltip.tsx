export function Tooltip({ label, children }: { label: string; children: React.ReactNode }) { return <span title={label}>{children}</span>; }
