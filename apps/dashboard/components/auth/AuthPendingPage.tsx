import Link from "next/link";

export function AuthPendingPage({ title, detail }: { title: string; detail: string }) {
  return <main className="auth-page"><section className="auth-panel"><div className="brand-lockup"><span className="brand-mark">P</span><span>PesaGuard</span></div><p className="eyebrow">Identity and access</p><h1>{title}</h1><p className="muted">{detail}</p><div className="panel auth-notice"><p>This workflow is reserved for the backend identity contract.</p><span>Nothing is submitted until the server-side flow is available.</span></div><Link className="button secondary" href="/login">Back to sign in</Link></section></main>;
}
