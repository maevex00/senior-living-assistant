import { test, expect } from "@playwright/test";

test("demo ranks five, explains scores, previews CRM and invalidates stale results", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Launch Demo/ }).click();
  await expect(
    page.getByRole("heading", { name: "Communities to consider" }),
  ).toBeVisible();
  await expect(page.locator("article.recommendation")).toHaveCount(5);
  await page
    .locator("article.recommendation")
    .first()
    .getByText("Why this community · score breakdown")
    .click();
  await expect(
    page
      .locator("article.recommendation")
      .first()
      .getByText("affordability", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Preview CRM save" }).click();
  await expect(page.getByText("Demo: no external CRM write.")).toBeVisible();
  await page.getByLabel("Monthly budget ($) *").fill("1000");
  await expect(page.locator("article.recommendation")).toHaveCount(0);
  await page.getByRole("button", { name: /Find matching communities/ }).click();
  await expect(
    page.getByRole("heading", { name: "No eligible communities" }),
  ).toBeVisible();
});

test("manual incomplete profile gets deterministic questions", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Find matching communities/ }).click();
  await expect(page.getByText("A few details are still needed")).toBeVisible();
  await expect(
    page.getByText("What is the maximum monthly budget?", { exact: true }),
  ).toBeVisible();
});

test("text fallback and live simulation are labeled honestly", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Text / transcript" }).click();
  await page.getByLabel("Consultation notes").fill("Monthly budget $4,500");
  await page.getByRole("button", { name: "Extract profile" }).click();
  await expect(page.getByLabel("Monthly budget ($) *")).toHaveValue("4500");
  await expect(
    page.getByText(/Offline mode extracts budget only/),
  ).toBeVisible();
  await page
    .getByRole("tab", { name: "Live consultation", exact: true })
    .click();
  await page.getByRole("button", { name: "Simulate consultation" }).click();
  await expect(page.getByText(/Offline simulation loaded/)).toBeVisible();
  await expect(page.getByLabel("Resident name")).toHaveValue(
    "Margaret Johnson",
  );
});

test("mobile form stays within viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "The client conversation" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
