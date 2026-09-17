import { describe, expect, it } from "vitest";
import { safePostLoginDestination } from "@/lib/auth/redirect";

describe("post-login redirects", () => {
  it("allows same-origin paths", () => expect(safePostLoginDestination("/transactions?status=flagged")).toBe("/transactions?status=flagged"));
  it("rejects external and protocol-relative destinations", () => {
    expect(safePostLoginDestination("https://example.com")).toBe("/overview");
    expect(safePostLoginDestination("//example.com")).toBe("/overview");
  });
});
