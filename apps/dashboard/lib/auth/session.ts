import type { SessionUser } from "@/types/user";

export function toSessionUser(value: { user_id: string; username: string; tenant_id: string; roles: string[]; permissions: string[] }): SessionUser {
  return { userId: value.user_id, username: value.username, tenantId: value.tenant_id, roles: value.roles, permissions: value.permissions as SessionUser["permissions"] };
}
