import { describe, expect, it } from "vitest";
const routes = ["/", "/product", "/solutions", "/features", "/security", "/integrations", "/pricing", "/documentation", "/api", "/about", "/contact", "/status", "/privacy", "/terms", "/cookies"];
describe("public route contract", () => { it("keeps the primary routes explicit", () => { expect(routes).toHaveLength(15); expect(routes).toContain("/status"); }); });
