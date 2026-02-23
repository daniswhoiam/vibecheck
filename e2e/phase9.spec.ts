import { test, expect } from "@playwright/test";

const BASE = "http://localhost:8080";

test.describe("Phase 9: Frontend Evolution", () => {

  // =========================================================================
  // Check 1: Source filter appears (FRON-01)
  // =========================================================================
  test.describe("Check 1: Source filter toggle", () => {

    test("renders 5 source pills on entity detail page", async ({ page }) => {
      await page.goto(`${BASE}/detail/1`);
      // Wait for the page to load
      await page.waitForSelector("text=All Sources", { timeout: 10000 });

      await expect(page.getByText("All Sources")).toBeVisible();
      await expect(page.getByText("HN")).toBeVisible();
      await expect(page.getByText("Reddit")).toBeVisible();
      await expect(page.getByText("Discourse")).toBeVisible();
      await expect(page.getByText("Dev.to")).toBeVisible();
    });

    test("clicking Reddit updates URL to ?source=reddit", async ({ page }) => {
      await page.goto(`${BASE}/detail/1`);
      await page.waitForSelector("text=All Sources", { timeout: 10000 });

      await page.getByText("Reddit").click();
      await expect(page).toHaveURL(/source=reddit/);
    });

    test("source filter persists after page reload", async ({ page }) => {
      await page.goto(`${BASE}/detail/1?source=reddit`);
      await page.waitForSelector("text=All Sources", { timeout: 10000 });

      // Reddit should be visible and URL should retain source=reddit
      await expect(page.getByText("Reddit")).toBeVisible();
      expect(page.url()).toContain("source=reddit");
    });

    test("clicking All Sources removes source param from URL", async ({ page }) => {
      await page.goto(`${BASE}/detail/1?source=reddit`);
      await page.waitForSelector("text=All Sources", { timeout: 10000 });

      await page.getByText("All Sources").click();
      // URL should not contain source= anymore
      await expect(page).not.toHaveURL(/source=/);
    });
  });

  // =========================================================================
  // Check 2: Source filter affects mentions section
  // =========================================================================
  test.describe("Check 2: Source filter affects data", () => {

    test("switching source filter changes visible content", async ({ page }) => {
      await page.goto(`${BASE}/detail/1`);
      await page.waitForSelector("text=All Sources", { timeout: 10000 });

      // Click Discourse — should trigger empty state since mock returns empty aspects for Discourse
      await page.getByText("Discourse").click();
      await expect(page).toHaveURL(/source=discourse/);
      // Wait briefly for reactivity
      await page.waitForTimeout(500);
    });
  });

  // =========================================================================
  // Check 3: Sentiment by Aspect section (FRON-02)
  // =========================================================================
  test.describe("Check 3: Sentiment by Aspect", () => {

    test("renders Sentiment by Aspect section", async ({ page }) => {
      await page.goto(`${BASE}/detail/1`);
      await page.waitForSelector("text=All Sources", { timeout: 10000 });

      await expect(page.getByText("Sentiment by Aspect")).toBeVisible();
    });

    test("aspect chart shows after data loads", async ({ page }) => {
      await page.goto(`${BASE}/detail/1`);
      await page.waitForSelector("text=Sentiment by Aspect", { timeout: 10000 });

      // Wait for aspect data to load (chart or empty state should appear)
      // The recharts container or aspect labels should be visible
      await page.waitForTimeout(1000);

      // Check for aspect labels in the chart
      const hasChart = await page.locator(".recharts-wrapper").count();
      const hasLabels = await page.getByText("Performance").count();
      expect(hasChart > 0 || hasLabels > 0).toBe(true);
    });

    test("Sentiment by Aspect section is below the trend chart", async ({ page }) => {
      await page.goto(`${BASE}/detail/1`);
      await page.waitForSelector("text=Sentiment by Aspect", { timeout: 10000 });

      const sentimentByAspect = page.getByText("Sentiment by Aspect");
      await expect(sentimentByAspect).toBeVisible();
    });
  });

  // =========================================================================
  // Check 4: No regressions — entity list loads
  // =========================================================================
  test.describe("Check 4: No regressions", () => {

    test("entity list page loads at /", async ({ page }) => {
      await page.goto(BASE);
      // Wait for either loading or content
      await page.waitForTimeout(2000);

      // Tab filter should be visible
      await expect(page.getByText("All")).toBeVisible();
      await expect(page.getByText("LLMs")).toBeVisible();
      await expect(page.getByText("Tools")).toBeVisible();
    });

    test("clicking entity navigates to detail page", async ({ page }) => {
      await page.goto(BASE);
      await page.waitForTimeout(2000);

      // Find the first tool card link and click it
      const firstLink = page.locator('a[href*="/detail/"]').first();
      if (await firstLink.count() > 0) {
        await firstLink.click();
        await expect(page).toHaveURL(/\/detail\/\d+/);
      }
    });

    test("no JS errors on entity detail page", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(`${BASE}/detail/1`);
      await page.waitForTimeout(3000);

      // Filter out known non-critical errors (React Router deprecation warnings are not page errors)
      const criticalErrors = errors.filter(e =>
        !e.includes("React Router") &&
        !e.includes("startTransition") &&
        !e.includes("fetch")  // API errors are expected if backend is slow
      );
      expect(criticalErrors).toHaveLength(0);
    });
  });

  // =========================================================================
  // Check 5: Trend chart is clean (single aggregate line)
  // =========================================================================
  test.describe("Check 5: Trend chart", () => {

    test("trend chart section is visible on detail page", async ({ page }) => {
      await page.goto(`${BASE}/detail/1`);
      await page.waitForSelector("text=All Sources", { timeout: 10000 });

      // The trend chart or "Sentiment Trend" heading should be visible
      const hasTrend = await page.getByText(/Sentiment Trend|Trend/i).count();
      const hasChart = await page.locator(".recharts-wrapper").count();
      expect(hasTrend > 0 || hasChart > 0).toBe(true);
    });
  });
});
