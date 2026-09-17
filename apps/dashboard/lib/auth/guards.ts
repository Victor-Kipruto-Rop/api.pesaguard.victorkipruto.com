import type { Permission } from "@/config/permissions";

export function canAccessRoute(granted: readonly string[], required?: Permission): boolean {
  return !required || granted.includes(required);
}
