import { describe, expect, it } from "vitest";
import { hasAllPermissions, hasAnyPermission, hasPermission } from "@/config/permissions";

describe("permission helpers", () => {
  const granted = ["transactions.read", "audit.read"];
  it("checks one permission", () => expect(hasPermission(granted, "transactions.read")).toBe(true));
  it("checks any permission", () => expect(hasAnyPermission(granted, ["settings.manage", "audit.read"])).toBe(true));
  it("requires every permission", () => expect(hasAllPermissions(granted, ["transactions.read", "audit.read"])).toBe(true));
});
