import { describe, expect, it } from "vitest";
import { toSessionUser } from "@/lib/auth/session";

describe("session mapping", () => {
  it("keeps tenant identity from the verified backend principal", () => {
    const user = toSessionUser({ user_id: "user-1", username: "operator", tenant_id: "tenant-a", roles: ["operator"], permissions: ["audit.read"] });
    expect(user.tenantId).toBe("tenant-a");
    expect(user.permissions).toContain("audit.read");
  });
});
