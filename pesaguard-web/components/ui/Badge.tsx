import type { ReactNode } from "react";
import { availabilityLabel, availabilityNotes } from "@/lib/content/availability";
import { cn } from "@/lib/utils/cn";
import type { Availability } from "@/types/content";
import type { ServiceState } from "@/types/status";

type BadgeTone = "live" | "pending" | "planned" | "neutral" | "lime" | "ink";

const toneClasses: Record<BadgeTone, string> = {
  live: "badge badge-live",
  pending: "badge badge-pending",
  planned: "badge badge-planned",
  neutral: "badge badge-neutral",
  lime: "badge badge-lime",
  ink: "badge badge-ink",
};

/** Small status pill for feature lists, navigation and spec tables. */
export function Badge({
  children,
  tone = "neutral",
  dot = false,
  className,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span className={cn(toneClasses[tone], className)}>
      {dot ? <span aria-hidden="true" className="badge-dot" /> : null}
      {children}
    </span>
  );
}

const availabilityTone: Record<Availability, BadgeTone> = {
  available: "live",
  pilot: "pending",
  "in-progress": "pending",
  planned: "planned",
  "not-started": "neutral",
};

/**
 * Availability badge for any capability we describe.
 *
 * Labels come from `lib/content/availability` so a capability is never
 * described one way in the header and another way on a page.
 */
export function AvailabilityBadge({
  availability,
  showNote = false,
}: {
  availability: Availability;
  showNote?: boolean;
}) {
  return (
    <span className="cluster">
      <Badge dot={availability === "available"} tone={availabilityTone[availability]}>
        {availabilityLabel(availability)}
      </Badge>
      {showNote ? <span className="small muted">{availabilityNotes[availability]}</span> : null}
    </span>
  );
}

const stateTone: Record<ServiceState, BadgeTone> = {
  operational: "live",
  degraded: "pending",
  outage: "pending",
  unknown: "neutral",
};

const stateLabel: Record<ServiceState, string> = {
  operational: "Operational",
  degraded: "Degraded",
  outage: "Outage",
  unknown: "Unknown",
};

const stateDotClass: Record<ServiceState, string> = {
  operational: "status-dot status-dot-pulse",
  degraded: "status-dot status-dot-amber",
  outage: "status-dot status-dot-red",
  unknown: "status-dot status-dot-muted",
};

/** Health indicator used by the status board. */
export function StatusDot({ state }: { state: ServiceState }) {
  return (
    <span className="cluster">
      <span aria-hidden="true" className={stateDotClass[state]} />
      <Badge tone={stateTone[state]}>{stateLabel[state]}</Badge>
    </span>
  );
}

/** Human label for a service state, shared with the status page. */
export function serviceStateLabel(state: ServiceState): string {
  return stateLabel[state];
}
