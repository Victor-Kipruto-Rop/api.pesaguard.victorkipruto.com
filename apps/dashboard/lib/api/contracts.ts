import { serverRequest } from "@/lib/api/server";

export type BackendTransaction = { trans_id: string; trans_amount: string | number; msisdn?: string; business_short_code?: string; trans_time?: string; created_at?: string; matched_record?: { internal_ref?: string; amount?: string | number; phone_number?: string; status?: string; synced_at?: string } | null };
export type Discrepancy = { id: string; trans_id?: string; anomaly_type?: string; status?: string; severity?: string; resolved: boolean; details?: unknown; assignee?: string; notes?: string; timeline?: unknown[]; detected_at?: string; sla_status?: string; sla_remaining_minutes?: number | null };
export type Provider = { id: string; name: string; provider_type?: string; status?: string; connection_status?: string; health_status?: string; metadata?: unknown };
export type Webhook = { id: string; url: string; event_types?: string[]; active: boolean; created_at?: string };
export type Report = { id: string; report_type?: string; period_start?: string; period_end?: string; status?: string; content?: unknown };
export type AuditEvent = { id: string; actor?: string; action?: string; details?: unknown; created_at?: string };
export type Settings = Record<string, unknown> & { preferred_locale?: string; deployment_region?: string };
export type DeadLetter = { id: string; reason?: string; error_detail?: string; processed?: boolean; created_at?: string };
export type ReconciliationReport = { report_period_days: number; generated_at: string; summary: { total_incidents: number; resolved: number; open: number; resolution_rate: number; average_resolution_minutes: number }; by_severity: Record<string, number>; by_status: Record<string, number>; critical_count: number; sla_compliant_percentage: number };

export async function getTransactions(tenantId: string) { return serverRequest<{ tenant_id: string; items: BackendTransaction[] }>(`/v1/customers/${encodeURIComponent(tenantId)}/transactions`); }
export async function getTransaction(tenantId: string, transactionId: string) { return serverRequest<BackendTransaction & { tenant_id: string }>(`/v1/customers/${encodeURIComponent(tenantId)}/transactions/${encodeURIComponent(transactionId)}`); }
export async function getDiscrepancies(params: { status?: string; severity?: string; resolved?: "open" | "resolved"; page?: number; perPage?: number } = {}) { const query = new URLSearchParams(); if (params.status) query.set("status", params.status); if (params.severity) query.set("severity", params.severity); if (params.resolved) query.set("resolved", params.resolved); if (params.page) query.set("page", String(params.page)); if (params.perPage) query.set("per_page", String(params.perPage)); return serverRequest<{ page: number; per_page: number; total: number; items: Discrepancy[] }>(`/discrepancies?${query}`); }
export async function getProviders() { return serverRequest<{ providers: Provider[] }>("/providers"); }
export async function getWebhooks(tenantId: string) { return serverRequest<{ tenant_id: string; webhooks: Webhook[] }>(`/webhooks?tenant_id=${encodeURIComponent(tenantId)}`); }
export async function getReports(tenantId: string) { return serverRequest<{ tenant_id: string; items: Report[] }>(`/v1/customers/${encodeURIComponent(tenantId)}/reports`); }
export async function getAudit(tenantId: string) { return serverRequest<{ tenant_id: string; items: AuditEvent[] }>(`/v1/customers/${encodeURIComponent(tenantId)}/audit`); }
export async function getSettings() { return serverRequest<Settings>("/v1/settings"); }
export async function getDeadLetters(tenantId: string) { return serverRequest<{ tenant_id: string; items: DeadLetter[] }>(`/v1/customers/${encodeURIComponent(tenantId)}/deadletters`); }
export async function getReconciliationReport(days = 7) { return serverRequest<ReconciliationReport>(`/analytics/reconciliation-report?days=${days}`); }
