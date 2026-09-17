/** Runtime state of one PesaGuard service, shown on the status page. */
export type ServiceState = "operational" | "degraded" | "outage" | "unknown";

/** A health signal a reader can act on. */
export type ServiceRow = {
  name: string;
  state: ServiceState;
  detail: string;
};

/** A recorded incident. The list is empty until a real incident exists. */
export type Incident = {
  id: string;
  title: string;
  startedAt: string;
  resolvedAt?: string;
  impact: string;
  summary: string;
};

/** What the status page renders. */
export type StatusSnapshot = {
  /** True when the values came from a live backend health probe. */
  live: boolean;
  headline: string;
  note: string;
  checkedAt?: string;
  services: ServiceRow[];
  incidents: Incident[];
};
