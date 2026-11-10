/**
 * 按考卷里同一批页面、同一视口（1920×1080）重拍当前站点，用于和 20261014 截图逐页比对。
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.argv[2] || "http://127.0.0.1:8089";
const OUTPUT = path.join(__dirname, "..", "output", "current-1920");
fs.mkdirSync(OUTPUT, { recursive: true });

const PAGES = [
  ["dashboard", "/app/dashboard"],
  ["stalls", "/app/stalls"],
  ["prediction", "/app/prediction"],
  ["offers", "/app/offers"],
  ["orders", "/app/orders"],
  ["alerts", "/app/alerts"],
  ["reports", "/app/reports"],
  ["realtime", "/app/insights/realtime"],
  ["demand", "/app/insights/demand"],
  ["waste", "/app/insights/waste"],
  ["about", "/app/about"],
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[name="username"]', "admin");
  await page.fill('input[name="password"]', "1234567890");
  await Promise.all([page.waitForURL(/\/app\//), page.click('button[type="submit"], input[type="submit"]')]);

  const report = {};
  for (const [name, route] of PAGES) {
    const response = await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUTPUT, `${name}.png`) });
    report[name] = response.status();
  }
  console.log(JSON.stringify({ statuses: report, consoleErrors: errors }, null, 2));
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });