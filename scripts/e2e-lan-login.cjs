/**
 * 局域网验收：用浏览器走一遍"打开地址 → 登录页 → admin 登录 → 业务页"的完整路径。
 * 跑法：node scripts/e2e-lan-login.cjs [http://10.177.73.82:8089]
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.argv[2] || "http://10.177.73.82:8089";
const OUTPUT = path.join(__dirname, "..", "output");
fs.mkdirSync(OUTPUT, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const consoleErrors = [];
  const failedRequests = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));
  page.on("requestfailed", (request) =>
    failedRequests.push(`${request.url()} :: ${request.failure()?.errorText}`));

  const report = { base: BASE };

  // 1) 根地址必须自己跳到登录页，而不是吐 401
  const rootResponse = await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 30000 });
  report.rootStatus = rootResponse.status();
  report.afterRootUrl = page.url();
  await page.waitForSelector("form", { timeout: 15000 });
  report.loginTitle = (await page.title()).trim();
  await page.screenshot({ path: path.join(OUTPUT, "lan-login.png"), fullPage: false });

  // 2) 正确账号登录
  await page.fill('input[name="username"]', "admin");
  await page.fill('input[name="password"]', "1234567890");
  await Promise.all([
    page.waitForURL(/\/app\/dashboard/, { timeout: 20000 }),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);
  await page.waitForLoadState("networkidle");
  report.dashboardUrl = page.url();
  report.dashboardTitle = (await page.title()).trim();
  await page.screenshot({ path: path.join(OUTPUT, "lan-dashboard.png"), fullPage: false });

  // 3) 关键业务页依次打开
  const pages = ["/app/prediction", "/app/evidence", "/app/stalls"];
  report.pages = {};
  for (const route of pages) {
    const response = await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 30000 });
    const heading = await page.locator("h1, h2").first().innerText().catch(() => "");
    report.pages[route] = {
      status: response.status(),
      heading: heading.replace(/\s+/g, " ").trim().slice(0, 60),
    };
  }
  await page.screenshot({ path: path.join(OUTPUT, "lan-evidence.png"), fullPage: false });

  report.consoleErrors = consoleErrors;
  report.failedRequests = failedRequests;
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch((error) => {
  console.error("FAILED:", error.message);
  process.exit(1);
});