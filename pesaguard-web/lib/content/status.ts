import type { HealthProbe } from "@/lib/api/client";
import { serviceCatalogue, unpublishedIncidentNote } from "@/content/status";
import type { ServiceRow, StatusSnapshot } from "@/types/status";

/**
 * Turns a health probe into what the status page renders.
 *
 * The marketing site can observe exactly one thing: whether the API answers its
 * health endpoint. Everything else is reported as `unknown` with the reason,
 * because claiming a service is healthy without a signal for it would be a
 * fabrication. `live` is true only when the probe actually reached the API.
 */
export function buildStatusSnapshot(probe: HealthProbe): StatusSnapshot {
  const services: ServiceRow[] = serviceCatalogue.map((service) => {
    if (!service.observedByProbe) {
      return {
        name: service.name,
        state: "unknown",
        detail: `${service.detail} ${service.unobservedReason}`,
      };
    }

    return {
      name: service.name,
      state: probe.reachable ? "operational" : "unknown",
      detail: probe.reachable
        ? `${service.detail} Answered by ${probe.endpoint} during this request.`
        : `${service.detail} ${probe.detail}`,
    };
  });

  return {
    live: probe.reachable,
    headline: probe.reachable
      ? "The API answered its health endpoint just now."
      : "No live health signal for this deployment.",
    note: probe.reachable
      ? unpublishedIncidentNote
      : `${probe.detail} Values below are reported as unknown rather than assumed.`,
    checkedAt: probe.checkedAt,
    services,
    incidents: [],
  };
}