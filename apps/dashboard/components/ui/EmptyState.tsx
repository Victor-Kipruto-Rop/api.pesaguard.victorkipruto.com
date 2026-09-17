export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state" role="status"><p>{title}</p><span>{detail}</span></div>;
}
