import type { Permission } from "@/config/permissions";

export type SessionUser = { userId: string; username: string; tenantId: string; roles: string[]; permissions: Permission[] };
