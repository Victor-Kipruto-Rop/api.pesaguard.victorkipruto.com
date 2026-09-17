"use client";

export default function DashboardError({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <div className="error-screen"><p className="eyebrow">Workspace error</p><h1>Unable to load workspace data</h1><button className="button primary" onClick={reset}>Retry</button></div>; }
