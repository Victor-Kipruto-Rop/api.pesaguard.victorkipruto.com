/**
 * Content types for the PesaGuard marketing site.
 *
 * Pages render from typed content modules in `content/` so page files stay thin
 * and wording lives in one place. Anything describing the product's real status
 * carries an `Availability` value so the UI can label it honestly instead of
 * implying a capability we do not ship yet.
 */

/** How real a capability is today. Rendered by `AvailabilityBadge`. */
export type Availability =
  /** Shipped and in use with the pilot customer. */
  | "available"
  /** Shipped, limited to pilot customers, still hardening. */
  | "pilot"
  /** Actively being built. */
  | "in-progress"
  /** On the roadmap with no committed date. */
  | "planned"
  /** Not started. Named only so readers know it is out of scope today. */
  | "not-started";

/** A step in a delivery timeline. */
export type TimelineEntry = {
  when: string;
  title: string;
  body: string;
  state?: "done" | "active" | "todo";
};

/** A single prose block inside a page body. */
export type PageSection = {
  eyebrow?: string;
  title: string;
  body: string;
  items?: string[];
  note?: string;
  availability?: Availability;
};

/** Label/value pair used by `SpecList` fact tables. */
export type SpecRow = {
  label: string;
  value: string;
};

export type FaqItem = {
  question: string;
  answer: string;
};

export type RelatedLink = {
  label: string;
  href: string;
  description: string;
};

export type CallToAction = {
  eyebrow?: string;
  title: string;
  body: string;
  primary: RelatedLink;
  secondary?: RelatedLink;
};

/**
 * The rendered shape of a long-form page (product, security, legal, about...).
 * `PageTemplate` consumes this shape and nothing else.
 */
export type PageData = {
  title: string;
  description: string;
  label?: string;
  /** Longer intro shown under the hero heading. */
  lede?: string;
  /** Honest status line for pages that describe scoped capabilities. */
  status?: {
    availability: Availability;
    label: string;
    note: string;
  };
  /** Figures shown in a stat band. Only use numbers we can evidence. */
  metrics?: MetricBlock[];
  /** Card grid shown above the prose sections. */
  features?: FeatureBlock[];
  /** Capability rows shown above the prose sections. */
  capabilities?: CapabilityBlock[];
  /** Linear process, rendered as a step flow. */
  steps?: StepBlock[];
  /** Honest contrast between PesaGuard and a common alternative. */
  comparison?: ComparisonRow[];
  /** Commercial plans, rendered on the pricing page. */
  plans?: PlanBlock[];
  /** Numbered principles, rendered as a pillar grid. */
  pillars?: PillarBlock[];
  sections: PageSection[];
  spec?: SpecRow[];
  faq?: FaqItem[];
  timeline?: TimelineEntry[];
  related?: RelatedLink[];
  cta?: CallToAction;
};
/** A payment rail or channel and how far along our support for it really is. */
export type IntegrationSummary = {
  name: string;
  href: string;
  availability: Availability;
  summary: string;
  /** Where the claim comes from, so the page can show its evidence. */
  evidence: string;
};
/**
 * Icon selector for content-driven blocks.
 *
 * Content modules are plain data, so they name an icon instead of importing a
 * component. `components/sections/Icon.tsx` maps these keys to lucide icons.
 */
export type IconKey =
  | "reconcile"
  | "monitor"
  | "shield"
  | "alert"
  | "report"
  | "audit"
  | "data"
  | "webhook"
  | "lock"
  | "chart"
  | "clock"
  | "users"
  | "terminal"
  | "check"
  | "flow";

/** A single figure with its label. Rendered by `StatBand`. */
export type MetricBlock = {
  value: string;
  label: string;
};

/** Card in a feature grid. */
export type FeatureBlock = {
  index?: string;
  title: string;
  body: string;
  href?: string;
  linkLabel?: string;
  iconKey?: IconKey;
  tone?: "plain" | "dark";
};

/** Row in a capability list: heading, explanation and optional bullet points. */
export type CapabilityBlock = {
  index?: string;
  title: string;
  body: string;
  items?: string[];
  availability?: Availability;
  href?: string;
  linkLabel?: string;
};

/** Step in a linear process. */
export type StepBlock = {
  step: string;
  title: string;
  body: string;
  detail?: string;
};

/** Side-by-side contrast between what PesaGuard does and a common alternative. */
export type ComparisonRow = {
  label: string;
  ours: string;
  others: string;
  /** Set when the PesaGuard column is itself the limitation, e.g. M-Pesa only. */
  oursNegative?: boolean;
};

/** Commercial plan. `price` stays a string so "From" and "Talk to us" both fit. */
export type PlanBlock = {
  name: string;
  price: string;
  cadence?: string;
  summary: string;
  features: string[];
  note?: string;
  featured?: boolean;
  cta: RelatedLink;
};

/** Numbered principle or architecture pillar. */
export type PillarBlock = {
  index: string;
  title: string;
  body: string;
};
