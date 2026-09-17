import { test, expect } from "@playwright/test";
test("home navigation reaches product", async ({ page }) => { await page.goto("/"); await expect(page.getByRole("link", { name: "Product" })).toBeVisible(); await page.getByRole("link", { name: "Product" }).click(); await expect(page).toHaveURL(/\/product$/); });
