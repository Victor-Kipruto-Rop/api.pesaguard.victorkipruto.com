import { apiClient } from "@/lib/api/client";

export function resolveDiscrepancy(id: string, note?: string) { return apiClient.backend<{ status: "resolved"; id: string }>(`/discrepancies/${encodeURIComponent(id)}/resolve`, { method: "POST", body: JSON.stringify({ note }) }); }
export function addDiscrepancyNote(id: string, note: string) { return apiClient.backend<{ status: "saved"; notes: string }>(`/discrepancies/${encodeURIComponent(id)}/notes`, { method: "POST", body: JSON.stringify({ note }) }); }
export function assignDiscrepancy(id: string, assignee: string) { return apiClient.backend<{ status: "assigned"; assignee: string }>(`/discrepancies/${encodeURIComponent(id)}/assign`, { method: "POST", body: JSON.stringify({ assignee }) }); }
export function replayDeadLetter(id: string, reason: string) { return apiClient.backend<{ status: string; id: string }>(`/api/v1/operations/dead-letters/${encodeURIComponent(id)}/replay`, { method: "POST", body: JSON.stringify({ reason }) }); }
export function updateSettings(values: Record<string, unknown>) { return apiClient.backend<Record<string, unknown>>("/v1/settings", { method: "POST", body: JSON.stringify(values) }); }
export function updateProvider(id: string, values: Record<string, unknown>) { return apiClient.backend<Record<string, unknown>>(`/providers/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(values) }); }
export function updateWebhook(id: string, values: Record<string, unknown>) { return apiClient.backend<Record<string, unknown>>(`/webhooks/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(values) }); }
