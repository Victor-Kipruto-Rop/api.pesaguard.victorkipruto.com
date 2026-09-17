import type { FooterGroup, NavItem } from "@/types/navigation";

/**
 * Header navigation.
 *
 * Every top-level entry links to a real section index page. Entries with
 * `groups` also open a mega-menu panel, and the panels only list destinations
 * that exist as routes so the header cannot promise pages we do not ship.
 */
const primary: NavItem[] = [
  {
    label: "Product",
    href: "/product",
    groups: [
      {
        title: "Platform",
        links: [
          { label: "Product overview", href: "/product", description: "What PesaGuard does and where it stands today" },
          { label: "How it works", href: "/how-it-works", description: "From Daraja callback to reconciled record" },
          { label: "Security model", href: "/security", description: "Tenant isolation, access control, audit trail" },
          { label: "System status", href: "/status", description: "Live health of the services we run" },
        ],
      },
      {
        title: "Capabilities",
        links: [
          { label: "Reconciliation", href: "/features/reconciliation", description: "Match callbacks to internal records as they land" },
          { label: "Transaction monitoring", href: "/features/transaction-monitoring", description: "Watch the M-Pesa flow in real time" },
          { label: "Fraud detection", href: "/features/fraud-detection", description: "Rule-based and statistical anomaly checks" },
          { label: "Real-time alerts", href: "/features/real-time-alerts", description: "SMS, email and Slack notifications" },
          { label: "Reporting", href: "/features/reporting", description: "Operational and reconciliation summaries" },
          { label: "Audit trail", href: "/features/audit-trail", description: "Append-only record of decisions and actions" },
        ],
      },
      {
        title: "Developers",
        links: [
          { label: "API reference", href: "/api", description: "Endpoints, payloads and error shapes" },
          { label: "Documentation", href: "/documentation", description: "Guides for building against PesaGuard" },
          { label: "Webhook ingestion", href: "/integrations/webhooks", description: "Idempotent, signature-checked callbacks" },
          { label: "Changelog", href: "/documentation/changelog", description: "What changed and when" },
        ],
      },
    ],
    foot: {
      label: "Talk to the team about your M-Pesa flow",
      href: "/contact/sales",
      description: "Bring your transaction volume and current reconciliation process.",
    },
  },
  {
    label: "Solutions",
    href: "/solutions",
    groups: [
      {
        title: "By organisation",
        links: [
          { label: "SACCOs", href: "/solutions/saccos", description: "Member contributions and loan repayments" },
          { label: "E-commerce operators", href: "/solutions/merchants", description: "STK Push volume and reversal checks" },
          { label: "Fintechs", href: "/solutions/fintechs", description: "Fraud visibility without a data team" },
          { label: "Financial institutions", href: "/solutions/financial-institutions", description: "Controls and evidence for audits" },
        ],
      },
      {
        title: "By problem",
        links: [
          { label: "Duplicate payments", href: "/features/fraud-detection", description: "Catch the same Daraja transaction twice" },
          { label: "Phantom reversals", href: "/features/fraud-detection", description: "Reversal sequences that do not match settlement" },
          { label: "Callback spoofing", href: "/integrations/mpesa", description: "Signature and source checks on every callback" },
          { label: "Manual reconciliation", href: "/features/reconciliation", description: "Replace statement-by-statement cross-checking" },
        ],
      },
    ],
    foot: { label: "Read how it works end to end", href: "/how-it-works", description: "The full path from callback to reconciled record." },
  },
  {
    label: "Features",
    href: "/features",
    groups: [
      {
        title: "Reconcile",
        links: [
          { label: "Reconciliation", href: "/features/reconciliation", description: "Real-time matching against internal records" },
          { label: "Data quality", href: "/features/data-quality", description: "Completeness, duplicates and validity checks" },
        ],
      },
      {
        title: "Monitor",
        links: [
          { label: "Transaction monitoring", href: "/features/transaction-monitoring", description: "Live flow, timing and volume signals" },
          { label: "Real-time alerts", href: "/features/real-time-alerts", description: "Notify owners the moment something breaks" },
        ],
      },
      {
        title: "Protect",
        links: [
          { label: "Fraud detection", href: "/features/fraud-detection", description: "Duplicate, amount and timing anomalies" },
          { label: "Audit trail", href: "/features/audit-trail", description: "Append-only history with actor and reason" },
        ],
      },
      {
        title: "Report",
        links: [
          { label: "Reporting", href: "/features/reporting", description: "Summaries for finance and operations" },
        ],
      },
    ],
    foot: { label: "See the capability status list", href: "/features", description: "Each capability marked available, in progress, planned or not started." },
  },
  {
    label: "Integrations",
    href: "/integrations",
    groups: [
      {
        title: "Available now",
        links: [
          { label: "M-Pesa (Daraja)", href: "/integrations/mpesa", availability: "available", description: "Callbacks, OAuth, validation and matching" },
          { label: "Outbound webhooks", href: "/integrations/webhooks", availability: "available", description: "Delivery attempts, retries and dead letters" },
        ],
      },
      {
        title: "Not started",
        links: [
          { label: "Airtel Money", href: "/integrations/airtel-money", availability: "not-started", description: "No adapter exists today" },
          { label: "Bank rails", href: "/integrations/banks", availability: "not-started", description: "No adapter exists today" },
          { label: "Point of sale", href: "/integrations/pos", availability: "not-started", description: "No adapter exists today" },
        ],
      },
    ],
    foot: { label: "Read the integration status list", href: "/integrations", description: "What is live, what is planned, and what is out of scope." },
  },
  {
    label: "Docs",
    href: "/documentation",
    groups: [
      {
        title: "Start here",
        links: [
          { label: "Getting started", href: "/documentation/getting-started", description: "Credentials, environments, first request" },
          { label: "Authentication", href: "/documentation/authentication", description: "Bearer tokens, scopes and rotation" },
          { label: "Transactions", href: "/documentation/transactions", description: "Canonical transaction shape" },
          { label: "Reconciliation", href: "/documentation/reconciliation", description: "Matching rules and exceptions" },
        ],
      },
      {
        title: "Operating PesaGuard",
        links: [
          { label: "Webhooks", href: "/documentation/webhooks", description: "Signature checks, retries and replay" },
          { label: "Fraud", href: "/documentation/fraud", description: "Signals, scoring and review" },
          { label: "Errors", href: "/documentation/errors", description: "Stable error codes and retry guidance" },
          { label: "Rate limits", href: "/documentation/rate-limits", description: "Limits, backoff and 429 handling" },
          { label: "Changelog", href: "/documentation/changelog", description: "Dated record of shipped changes" },
        ],
      },
    ],
    foot: { label: "Browse the API reference", href: "/api", description: "Request and response shapes for every endpoint." },
  },
  { label: "Pricing", href: "/pricing" },
];

/** Footer columns, rendered by `Footer`. */
const footer: FooterGroup[] = [
  {
    title: "Product",
    links: [
      { label: "Product overview", href: "/product" },
      { label: "How it works", href: "/how-it-works" },
      { label: "Features", href: "/features" },
      { label: "Integrations", href: "/integrations" },
      { label: "Pricing", href: "/pricing" },
    ],
  },
  {
    title: "Developers",
    links: [
      { label: "Documentation", href: "/documentation" },
      { label: "API reference", href: "/api" },
      { label: "Getting started", href: "/documentation/getting-started" },
      { label: "Webhooks", href: "/documentation/webhooks" },
      { label: "Changelog", href: "/documentation/changelog" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Security", href: "/security" },
      { label: "Status", href: "/status" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", href: "/privacy" },
      { label: "Terms", href: "/terms" },
      { label: "Cookies", href: "/cookies" },
    ],
  },
];

export const navigation = { primary, footer };
