import { test, expect } from "@playwright/test";
test("documentation has a sidebar", async ({ page }) => { await page.goto("/documentation"); await expect(page.getByRole("link", { name: "Transactions" })).toBeVisible(); });
