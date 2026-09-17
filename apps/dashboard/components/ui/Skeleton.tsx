export function Skeleton({ width = "100%", height = "14px" }: { width?: string; height?: string }) {
  return <span className="skeleton" aria-hidden="true" style={{ width, height }} />;
}
