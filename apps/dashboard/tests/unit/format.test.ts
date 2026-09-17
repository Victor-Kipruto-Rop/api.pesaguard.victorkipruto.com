import { describe, expect, it } from "vitest";
import { formatCurrency, formatDate, formatPercentage } from "@/lib/utils/format";

describe("financial formatters", () => {
  it("formats currency without accepting invalid numbers", () => {
    expect(formatCurrency("1200.50")).toContain("1,200.50");
    expect(formatCurrency("not-a-number")).toBe("Not available");
  });

  it("formats percentages", () => expect(formatPercentage("99.8")).toBe("99.80%"));
  it("handles invalid dates explicitly", () => expect(formatDate("invalid")).toBe("Not available"));
});
