export type RealtimeEventType = "transaction.created" | "transaction.updated" | "transaction.failed" | "reconciliation.completed" | "anomaly.detected" | "anomaly.resolved" | "alert.delivered" | "webhook.failed" | "system.degraded" | "system.recovered";
export type RealtimeEvent<T = unknown> = { id: string; type: RealtimeEventType; occurredAt: string; payload: T };
