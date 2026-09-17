import type { PageData } from "@/types/content";

export const pages: Record<string, PageData> = {
  product: {
    title: "One control plane for payment trust.",
    description: "Bring transactions, reconciliation, risk, and evidence into one operational view.",
    label: "PesaGuard product",
    lede: "PesaGuard watches M-Pesa (Safaricom Daraja) transaction flow as it happens, matches callbacks against internal records, and flags mismatches and suspicious patterns before they become disputes or losses.",
    status: {
      availability: "pilot",
      label: "MVP live with a pilot customer.",
      note: "Active payment scope: M-Pesa (Safaricom Daraja).",
    },
    steps: [
      { step: "01", title: "Connect", body: "Daraja callbacks land as normalized payment events.", detail: "Validated, de-duplicated and tied to a tenant from the first write." },
      { step: "02", title: "Match", body: "Callbacks are matched against internal records as they arrive.", detail: "Mismatches become exceptions with the evidence your team needs." },
      { step: "03", title: "Act", body: "Review risk signals, send alerts and keep an audit trail.", detail: "SMS, email and Slack notifications route the right alert to the right owner." },
    ],
    comparison: [
      { label: "Payment rail scope", ours: "M-Pesa (Safaricom Daraja) today", others: "Every rail at once, thinly", oursNegative: true },
      { label: "Reconciliation", ours: "Real-time matching with exceptions", others: "End-of-day spreadsheets" },
      { label: "Evidence", ours: "Append-only audit trail", others: "Chat threads and memory" },
    ],
    sections: [
      {
        title: "See the whole payment lifecycle",
        body: "PesaGuard connects payment rails to the controls your team depends on, so every exception has context and every decision leaves evidence.",
        items: [
          "Normalize Daraja callback events into canonical payment records",
          "Match callbacks against internal records in real time",
          "Route risk signals and exceptions to the right team",
        ],
      },
      {
        title: "Built for the work between systems",
        body: "Give finance, operations, and engineering a shared view of what happened, what needs attention, and what can be trusted.",
      },
    ],
    related: [
      { label: "How it works", href: "/how-it-works", description: "From Daraja callback to reconciled record." },
      { label: "Security model", href: "/security", description: "Tenant isolation, access control and audit trail." },
      { label: "System status", href: "/status", description: "Live health of the services we run." },
    ],
    cta: {
      eyebrow: "Talk to the pilot team",
      title: "Bring your M-Pesa flow and current reconciliation process.",
      body: "We will show what real-time matching and evidence-backed exceptions look like on your volume.",
      primary: { label: "Talk to our team", href: "/contact/sales", description: "Start a pilot conversation." },
      secondary: { label: "Read the docs", href: "/documentation", description: "Guides for building against PesaGuard." },
    },
  },
  solutions: {
    title: "Payment operations that fit your world.",
    description: "Purpose-built workflows for teams moving money across East Africa.",
    sections: [
      {
        title: "A clearer operating rhythm",
        body: "Whether you run a SACCO, merchant network, institution, or fintech, PesaGuard turns fragmented payment data into accountable action.",
        items: [
          "SACCOs: reconcile member collections with confidence",
          "Merchants: protect revenue across every channel",
          "Financial institutions: strengthen controls without slowing teams",
          "Fintechs: scale payment operations with durable foundations",
        ],
      },
    ],
    related: [
      { label: "SACCOs", href: "/solutions/saccos", description: "Member contributions and loan repayments." },
      { label: "Merchants", href: "/solutions/merchants", description: "STK Push volume and reversal checks." },
      { label: "Fintechs", href: "/solutions/fintechs", description: "Fraud visibility without a data team." },
    ],
    cta: {
      eyebrow: "Find your fit",
      title: "Tell us how money moves through your organisation.",
      body: "We will map your flow to the reconciliation, monitoring and alerting controls that matter first.",
      primary: { label: "Talk to our team", href: "/contact/sales", description: "Start a solutions conversation." },
    },
  },
  "how-it-works": {
    title: "From payment event to trusted record.",
    description: "A practical data path for payment teams.",
    lede: "Daraja callbacks become normalized records, matched outcomes and an audit trail your team can investigate.",
    steps: [
      { step: "01", title: "Connect", body: "Bring in Daraja callbacks and internal records.", detail: "Signature-checked, idempotent and de-duplicated on write." },
      { step: "02", title: "Understand", body: "Normalize, validate and match each record.", detail: "Missing, duplicated or contradictory data becomes an exception." },
      { step: "03", title: "Act", body: "Reconcile, investigate and preserve evidence.", detail: "Alerts, review workflows and an append-only trail." },
    ],
    sections: [
      { title: "Connect", body: "Bring in transaction, settlement, and operational signals through connectors or webhooks." },
      { title: "Understand", body: "Normalize and validate records, then identify missing, duplicated, or contradictory data." },
      { title: "Act", body: "Reconcile, investigate risk, notify owners, and preserve the evidence behind each outcome." },
    ],
    related: [
      { label: "Reconciliation", href: "/features/reconciliation", description: "Match callbacks to internal records as they land." },
      { label: "Transaction monitoring", href: "/features/transaction-monitoring", description: "Watch the M-Pesa flow in real time." },
      { label: "Documentation", href: "/documentation", description: "Guides for building against PesaGuard." },
    ],
    cta: {
      eyebrow: "See it on your flow",
      title: "Walk us through a recent mismatch or dispute.",
      body: "We will show how the callback-to-evidence path would have caught it earlier.",
      primary: { label: "Talk to our team", href: "/contact/sales", description: "Book a walkthrough." },
    },
  },
  features: {
    title: "Controls for every critical moment.",
    description: "The operational building blocks behind reliable payment systems.",
    features: [
      { iconKey: "reconcile", title: "Reconciliation", body: "Match callbacks to internal records as they land.", href: "/features/reconciliation", linkLabel: "Explore reconciliation" },
      { iconKey: "monitor", title: "Transaction monitoring", body: "Watch the M-Pesa flow in real time.", href: "/features/transaction-monitoring", linkLabel: "Explore monitoring" },
      { iconKey: "shield", title: "Fraud detection", body: "Rule-based and statistical anomaly checks.", href: "/features/fraud-detection", linkLabel: "Explore fraud signals" },
      { iconKey: "alert", title: "Real-time alerts", body: "SMS, email and Slack notifications.", href: "/features/real-time-alerts", linkLabel: "Explore alerts" },
      { iconKey: "report", title: "Reporting", body: "Operational and reconciliation summaries.", href: "/features/reporting", linkLabel: "Explore reporting" },
      { iconKey: "audit", title: "Audit trail", body: "Append-only record of decisions and actions.", href: "/features/audit-trail", linkLabel: "Explore audit trail" },
    ],
    sections: [
      {
        title: "A focused toolkit",
        body: "Move from raw events to clear decisions with reconciliation, monitoring, fraud detection, alerting, reporting, audit trails, and data quality controls.",
        items: ["Reconciliation", "Transaction monitoring", "Fraud detection", "Real-time alerts", "Reporting and audit trail", "Data quality"],
      },
    ],
    related: [
      { label: "Product overview", href: "/product", description: "What PesaGuard does and where it stands today." },
      { label: "Pricing", href: "/pricing", description: "How pilot and growth plans are scoped." },
    ],
    cta: {
      eyebrow: "Start with one control",
      title: "Pick the exception that costs you the most time.",
      body: "We will scope reconciliation, monitoring or alerting around it first.",
      primary: { label: "Talk to our team", href: "/contact/sales", description: "Scope the first control." },
    },
  },
  security: {
    title: "Security is part of the product.",
    description: "Layered controls for sensitive financial data and the teams that operate it.",
    pillars: [
      { index: "01", title: "Encrypt in transit and at rest", body: "Protect sensitive payment and operational data across every hop." },
      { index: "02", title: "Authenticate explicitly", body: "Bearer tokens, scopes and rotation for server-to-server access." },
      { index: "03", title: "Isolate tenants", body: "Every tenant-owned resource is evaluated against the authenticated tenant context." },
      { index: "04", title: "Keep evidence", body: "Append-only audit records make review and compliance practical." },
    ],
    sections: [
      {
        title: "Designed for accountable access",
        body: "PesaGuard keeps security practical: protect data in transit and at rest, make access explicit, isolate tenants, and retain useful evidence.",
        items: ["Encryption-aware architecture", "Authentication and role-based access", "Tenant isolation", "Operational compliance controls"],
      },
    ],
    related: [
      { label: "Tenant isolation", href: "/security/tenant-isolation", description: "Strong boundaries between tenants." },
      { label: "Authentication", href: "/security/authentication", description: "Identity teams can reason about." },
      { label: "Compliance", href: "/security/compliance", description: "Policies as visible controls." },
    ],
    cta: {
      eyebrow: "Review the controls",
      title: "Bring your security questionnaire to the first call.",
      body: "We will walk through encryption, isolation, access and audit evidence line by line.",
      primary: { label: "Talk to our team", href: "/contact/sales", description: "Start a security review." },
    },
  },
  integrations: {
    title: "Meet your payment stack where it is.",
    description: "Connect the rails, channels, and systems that matter to your operation.",
    lede: "M-Pesa (Safaricom Daraja) and outbound webhooks are live. Everything else on this page is named so the scope is unambiguous.",
    sections: [
      {
        title: "Start with the signals you already have",
        body: "Use adapters and webhooks to bring mobile money, banks, point of sale, and internal events into a consistent operational model.",
        items: ["M-Pesa", "Airtel Money", "Banks", "Point of sale", "Webhooks"],
      },
    ],
    related: [
      { label: "M-Pesa", href: "/integrations/mpesa", description: "Daraja callbacks, validated and matched." },
      { label: "Webhooks", href: "/integrations/webhooks", description: "Signed delivery with retries and dead letters." },
      { label: "Webhook docs", href: "/documentation/webhooks", description: "Signature checks, retries and replay." },
    ],
    cta: {
      eyebrow: "Check your rail",
      title: "Tell us which rails and channels you depend on.",
      body: "We will confirm what is live today and what the path looks like for the rest.",
      primary: { label: "Talk to our team", href: "/contact/sales", description: "Confirm integration scope." },
    },
  },
  pricing: {
    title: "Pricing that follows your operation.",
    description: "Start with the controls you need, then grow into deeper visibility as payment volume and complexity increase.",
    plans: [
      {
        name: "Pilot",
        price: "Scoped per pilot",
        summary: "For one M-Pesa flow and the team that owns it.",
        features: ["Real-time Daraja reconciliation", "Exception queue with evidence", "SMS, email and Slack alerts", "Append-only audit trail"],
        note: "MVP live with a pilot customer. Production hardening in progress.",
        cta: { label: "Talk to our team", href: "/contact/sales", description: "Scope a pilot." },
      },
      {
        name: "Growth",
        price: "Talk to us",
        summary: "For growing volume, more owners and deeper history.",
        features: ["Everything in Pilot", "Additional flows and environments", "Longer retention and reporting", "Review workflows and roles"],
        note: "Scoped around payment volume, data sources and retention.",
        featured: true,
        cta: { label: "Talk to our team", href: "/contact/sales", description: "Scope growth pricing." },
      },
      {
        name: "Institution",
        price: "Talk to us",
        summary: "For audits, controls and multi-team accountability.",
        features: ["Everything in Growth", "Tenant isolation review", "Compliance evidence pack", "Dedicated support path"],
        cta: { label: "Contact sales", href: "/contact/sales", description: "Scope institutional pricing." },
      },
    ],
    faq: [
      { question: "Is there a self-serve plan?", answer: "No. PesaGuard is deployed and scoped with the pilot team so reconciliation matches your flow from day one." },
      { question: "What drives the price?", answer: "Payment volume, data sources, retention and the workflows your team needs. We scope it in a focused conversation." },
      { question: "Can we start with one flow?", answer: "Yes. Most pilots start with a single M-Pesa flow, then expand to more owners and history." },
    ],
    sections: [
      {
        title: "A conversation, not a hidden meter",
        body: "We scope pricing around payment volume, data sources, retention, and the workflows your team needs. Talk to us for a considered proposal.",
      },
    ],
    related: [
      { label: "Product overview", href: "/product", description: "What is included in the platform today." },
      { label: "Contact sales", href: "/contact/sales", description: "Scope pricing around your operation." },
    ],
    cta: {
      eyebrow: "Get a considered proposal",
      title: "Bring your volume and current reconciliation process.",
      body: "We will scope a pilot or growth plan around what your team needs first.",
      primary: { label: "Talk to our team", href: "/contact/sales", description: "Request pricing." },
    },
  },
  about: {
    title: "Building trust into African payments.",
    description: "PesaGuard is focused on the operational layer that makes digital payments dependable.",
    lede: "MVP live with a pilot customer. Active payment scope: M-Pesa (Safaricom Daraja).",
    timeline: [
      { when: "Now", title: "Pilot live", body: "Real-time M-Pesa reconciliation and anomaly detection with a pilot customer.", state: "active" },
      { when: "Next", title: "Production hardening", body: "Reliability, evidence and review workflows for wider rollout.", state: "todo" },
      { when: "Later", title: "More rails", body: "Additional payment rails only when adapters, tests and docs exist.", state: "todo" },
    ],
    sections: [
      { title: "Our mission", body: "Make it easier for payment teams to know what happened, why it happened, and what to do next." },
      { title: "Our approach", body: "We favor durable controls, clear evidence, and systems that respect the realities of high-volume payment operations." },
    ],
    related: [
      { label: "Product overview", href: "/product", description: "What PesaGuard does today." },
      { label: "Contact", href: "/contact", description: "Start a conversation with the team." },
    ],
    cta: {
      eyebrow: "Meet the team",
      title: "Tell us what dependable payments would unlock.",
      body: "We build around real operator workflows, not slideware.",
      primary: { label: "Contact us", href: "/contact", description: "Start a conversation." },
    },
  },
};
