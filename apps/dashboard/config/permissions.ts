export const permissions = ["transactions.read", "transactions.export", "transactions.reconcile", "reconciliation.read", "reconciliation.execute", "reconciliation.manual_match", "anomalies.read", "anomalies.investigate", "anomalies.resolve", "reports.read", "reports.create", "reports.export", "integrations.read", "integrations.manage", "audit.read", "developer.api_keys.manage", "operations.read", "settings.manage"] as const;

export type Permission = (typeof permissions)[number];

export function hasPermission(granted: readonly string[], required: Permission): boolean {
  return granted.includes(required);
}

export function hasAnyPermission(granted: readonly string[], required: readonly Permission[]): boolean {
  return required.some((permission) => hasPermission(granted, permission));
}

export function hasAllPermissions(granted: readonly string[], required: readonly Permission[]): boolean {
  return required.every((permission) => hasPermission(granted, permission));
}
