import { expect, test } from "@playwright/test";

const prefixUrl = process.env.FOODWISE_PREFIX_TEST_URL;
test.skip(!prefixUrl || !process.env.FOODWISE_TEST_PASSWORD, "Run against a context-path instance with test credentials.");
test.use({ baseURL: prefixUrl || "http://127.0.0.1:18089" });

test("foodwise prefix keeps login, assets, API, and subpages isolated", async ({ page }) => {
  const leakedPaths: string[] = [];
  const failedResponses: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin === new URL(prefixUrl!).origin && !url.pathname.startsWith("/foodwise/")) {
      leakedPaths.push(url.pathname);
    }
  });
  page.on("response", (response) => {
    if (response.url().startsWith(prefixUrl!) && response.status() >= 400) {
      failedResponses.push(response.status() + " " + response.url());
    }
  });

  await page.goto("/foodwise/login");
  await expect(page.getByRole("heading", { name: "进入经营工作台" })).toBeVisible();
  await expect(page.locator("form")).toHaveAttribute("action", "/foodwise/login");
  await page.locator('input[name="username"]').fill("foodwise-admin");
  await page.locator('input[name="password"]').fill(process.env.FOODWISE_TEST_PASSWORD!);
  await page.getByRole("button", { name: "登录经营工作台" }).click();
  await expect(page).toHaveURL(new RegExp("/foodwise/app/dashboard$"));
  await expect(page.getByRole("heading", { name: "经营驾驶舱" })).toBeVisible();

  const routes = ["stalls", "prediction", "offers", "orders", "operations/feedback", "alerts", "reports", "insights/realtime", "insights/demand", "insights/waste", "about"];
  for (const route of routes) {
    await page.goto("/foodwise/app/" + route);
    await expect(page.locator("main .view-head h2, main .about-view h2").last()).toBeVisible();
  }
  expect(leakedPaths).toEqual([]);
  expect(failedResponses).toEqual([]);
});
