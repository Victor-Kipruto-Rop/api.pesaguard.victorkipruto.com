import Link from "next/link";

export function BackendPendingPage({ title, eyebrow, detail }: { title: string; eyebrow: string; detail: string }) {
  return <div className="page-shell"><header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{detail}</p></div></header><section className="panel empty-state" aria-live="polite"><p>This operational surface is ready for its tenant-scoped API contract.</p><span>No production fixtures or simulated events are rendered.</span><Link className="button secondary" href="/overview">Return to overview</Link></section></div>;
}
