export function Card({ title, eyebrow, action, children }: { title?: string; eyebrow?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return <section className="panel"><div className="panel-heading">{(eyebrow || title) && <div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}{title && <h2>{title}</h2>}</div>}{action}</div>{children}</section>;
}
