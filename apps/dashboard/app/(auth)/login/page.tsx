import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return <main className="auth-page"><section className="auth-panel" aria-labelledby="login-title"><div className="brand-lockup"><span className="brand-mark">P</span><span>PesaGuard</span></div><p className="eyebrow">Financial infrastructure control center</p><h1 id="login-title">Sign in to your workspace</h1><p className="muted">Use your organization credentials to access operational data.</p><LoginForm /></section><aside className="auth-aside"><p className="eyebrow">Traceable by design</p><h2>Control every critical payment moment.</h2><p>Reconciliation, risk, and evidence in one secured operational view.</p></aside></main>;
}
