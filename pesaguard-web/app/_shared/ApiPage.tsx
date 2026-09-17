import Link from "next/link";
import { ArrowRight, ArrowUpRight, Check, LockKeyhole, Terminal, Webhook } from "lucide-react";

const endpoints = [
	{ method: "POST", path: "/v1/transactions", label: "Transactions", href: "/api/transactions", detail: "Create and normalize payment events" },
	{ method: "GET", path: "/v1/reconciliation/runs", label: "Reconciliation", href: "/api/reconciliation", detail: "Inspect matching runs and exceptions" },
	{ method: "POST", path: "/v1/fraud/signals", label: "Fraud signals", href: "/api/fraud", detail: "Send context into risk workflows" },
	{ method: "POST", path: "/v1/webhooks", label: "Webhooks", href: "/api/webhooks", detail: "Configure durable event delivery" },
];

export function ApiPage({ title, intro }: { title: string; intro: string }) {
	return <main className="api-page">
		<section className="api-hero"><div className="container api-hero-grid"><div>
			<div className="api-kicker"><span className="api-kicker-mark"><Terminal size={14} /></span><span>Developer platform / v1</span></div>
			<h1>{title}</h1><p className="api-intro">{intro}</p>
			<div className="actions"><Link className="button button-primary" href="/documentation/getting-started">Read the docs <ArrowRight size={17} /></Link><Link className="button button-api-quiet" href="/contact/sales">Talk to engineering <ArrowUpRight size={16} /></Link></div>
			<div className="api-proof"><span><Check size={14} /> JSON-first</span><span><Check size={14} /> Replay-safe</span><span><Check size={14} /> Observable</span></div>
		</div><div className="api-code-card"><div className="api-code-top"><span><i /> <i /> <i /></span><small>request.sh</small><span className="api-code-secure"><LockKeyhole size={12} /> secure</span></div><pre><code><span className="code-muted">curl</span> https://api.pesaguard.com/v1/transactions {"\\"}{"\n"}  -X POST {"\\"}{"\n"}  -H <span className="code-lime">&quot;Authorization: Bearer $KEY&quot;</span> {"\\"}{"\n"}  -H <span className="code-lime">&quot;Content-Type: application/json&quot;</span> {"\\"}{"\n"}  -d <span className="code-amber">&apos;{"{"}&quot;amount&quot;: 284500, &quot;currency&quot;: &quot;KES&quot;{"}"}&apos;</span></code></pre><div className="api-code-response"><span className="response-status"><Check size={13} /> 201 Created</span><span>request_id: pg_01HT...</span></div></div></div></section>
		<section className="api-strip"><div className="container api-strip-inner"><span>One API for the moments that matter</span><span>transactions</span><span>reconciliation</span><span>risk signals</span><span>event delivery</span></div></section>
		<section className="section api-section"><div className="container"><div className="api-section-heading"><div><p className="eyebrow">Explore the surface</p><h2>Small primitives. Serious operations.</h2></div><p>Connect the workflows your teams already run, then keep the operational evidence close to the data.</p></div><div className="endpoint-grid">{endpoints.map((endpoint) => <Link className="endpoint-card" href={endpoint.href} key={endpoint.path}><div className="endpoint-top"><span className={`method method-${endpoint.method.toLowerCase()}`}>{endpoint.method}</span><ArrowUpRight size={17} /></div><code>{endpoint.path}</code><strong>{endpoint.label}</strong><p>{endpoint.detail}</p></Link>)}</div></div></section>
		<section className="section api-dark-section"><div className="container api-dark-grid"><div><p className="eyebrow">Built for production reality</p><h2>Good APIs explain what happened.</h2><p>Idempotency, durable webhooks, explicit errors, and audit-friendly request IDs give your team a useful trail from event to outcome.</p><Link className="text-link api-text-link" href="/documentation">Browse documentation <ArrowRight size={16} /></Link></div><div className="api-control-list"><div><span><LockKeyhole size={17} /></span><div><strong>Scoped access</strong><p>Keep credentials aligned with environment and responsibility.</p></div></div><div><span><Webhook size={17} /></span><div><strong>Durable delivery</strong><p>Design consumers around retries, replay, and clear outcomes.</p></div></div><div><span><Terminal size={17} /></span><div><strong>Useful observability</strong><p>Carry request context into every investigation.</p></div></div></div></div></section>
	</main>;
}
