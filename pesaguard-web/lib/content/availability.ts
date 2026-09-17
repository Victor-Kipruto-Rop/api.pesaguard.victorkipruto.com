import type { Availability } from "@/types/content";

/**
 * Human labels for capability status.
 *
 * These strings appear on badges, cards and spec tables. They are deliberately
 * plain: a reader should never have to guess whether something exists.
 */
export const availabilityLabels: Record<Availability, string> = {
  available: "Available now",
  pilot: "Pilot only",
  "in-progress": "In progress",
  planned: "Planned",
  "not-started": "Not started",
};

/** Badge modifier class for each availability value. */
export const availabilityClasses: Record<Availability, string> = {
  available: "badge badge-live",
  pilot: "badge badge-pending",
  "in-progress": "badge badge-pending",
  planned: "badge badge-planned",
  "not-started": "badge badge-neutral",
};

/** Longer explanation used in lists and spec tables. */
export const availabilityNotes: Record<Availability, string> = {
  available: "Shipped and in use with the pilot customer.",
  pilot: "Shipped, limited to pilot customers, and still being hardened.",
  "in-progress": "Actively being built. No release date is committed.",
  planned: "On the roadmap. No release date is committed.",
  "not-started": "Not started. Named only so the scope is unambiguous.",
};

export function availabilityLabel(availability: Availability): string {
  return availabilityLabels[availability];
}

export function availabilityClass(availability: Availability): string {
  return availabilityClasses[availability];
}

export function availabilityNote(availability: Availability): string {
  return availabilityNotes[availability];
}