"use client";

import { hasAllPermissions, hasAnyPermission, hasPermission, type Permission } from "@/config/permissions";

export function usePermissions(granted: readonly string[] = []) {
  return { can: (permission: Permission) => hasPermission(granted, permission), canAny: (required: readonly Permission[]) => hasAnyPermission(granted, required), canAll: (required: readonly Permission[]) => hasAllPermissions(granted, required) };
}
