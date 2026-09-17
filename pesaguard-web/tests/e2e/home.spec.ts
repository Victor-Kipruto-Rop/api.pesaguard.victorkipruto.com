import { test, expect } from "@playwright/test";
test("home has an accessible main heading", async ({ page }) => { await page.goto("/"); await expect(page.getByRole("heading", { level: 1 })).toContainText("money in motion"); });
