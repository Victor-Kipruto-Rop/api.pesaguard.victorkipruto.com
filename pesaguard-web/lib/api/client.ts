import { siteConfig } from "@/config/site";

/** What a backend health probe is expected to return, for typed consumption on the status page. */
export type HealthProbe = {
  reachable: boolean;
  status: string;
  detail: string;
  endpoint?: string;
  checkedAt?: string;
};

/**
 * Health probe for the API.
 *
 * Returns a live signal only when `PESAGUARD_API_URL` is configured and the
 * `/health` endpoint answers. Otherwise reports unreachable with the reason,
 * so the status page never claims availability it has not measured.
 */
export async function getBackendHealth(): Promise<HealthProbe> {
  const baseUrl = process.env.PESAGUARD_API_URL;
  const endpoint = baseUrl ? `${baseUrl.replace(/\/$/, "")}/health` : undefined;
  if (!baseUrl) {
    return {
      reachable: false,
      status: "No live health signal for this deployment.",
      detail: "No API URL was configured for the marketing site.",
      endpoint,
      checkedAt: new Date().toISOString(),
    };
  }

  try {
    const response = await fetch(endpoint as string, {
      next: { revalidate: 30, tags: ["status"] },
      signal: AbortSignal.timeout(6000),
    });

    if (response.ok) {
      const body = (await response.json().catch(() => ({}))) as { status?: string };
      return {
        reachable: true,
        status: body.status ?? "All systems operational",
        detail: `Answered by ${endpoint} during this request.`,
        endpoint,
        checkedAt: new Date().toISOString(),
      };
    }

    return {
      reachable: false,
      status: "Monitoring service health",
      detail: `API returned ${response.status} ${response.statusText} on /health.`,
      endpoint,
      checkedAt: new Date().toISOString(),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "health probe error";
    return {
      reachable: false,
      status: "Monitoring service health",
      detail: `API health endpoint could not be reached. Detail: ${message}.`,
      endpoint,
      checkedAt: new Date().toISOString(),
    };
  }
}

export { siteConfig };

