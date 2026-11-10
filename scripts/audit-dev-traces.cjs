/**
 * 统计各业务页面上"模型/工程内部词"的出现次数，用来量化"开发者痕迹"。
 */
const { chromium } = require("playwright");

const BASE = process.argv[2] || "http://127.0.0.1:8089";
const PAGES = [
  ["dashboard", "/app/dashboard"],
  ["prediction", "/app/prediction"],
  ["feedback", "/app/operations/feedback"],
  ["offers", "/app/offers"],
  ["reports", "/app/reports"],
  ["realtime", "/app/insights/realtime"],
  ["demand", "/app/insights/demand"],
  ["about", "/app/about"],
  ["evidence", "/app/evidence"],
];
const TERMS = ["区间", "临界比", "regret", "模型", "校准", "覆盖", "分位", "样本", "版本", "P95", "置信", "损耗", "残余", "接口", "engine", "API"];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[name="username"]', "admin");
  await page.fill('input[name="password"]', "1234567890");
  await Promise.all([page.waitForURL(/\/app\//), page.click('button[type="submit"], input[type="submit"]')]);

  const rows = [];
  for (const [name, route] of PAGES) {
    await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(400);
    const text = await page.locator("main").innerText();
    const hits = TERMS.map((term) => [term, (text.split(term).length - 1)]).filter(([, n]) => n > 0);
    rows.push({ page: name, totalTerms: hits.reduce((sum, [, n]) => sum + n, 0), chars: text.length, hits });
  }
  rows.sort((a, b) => b.totalTerms - a.totalTerms);
  for (const row of rows) {
    console.log(`${row.page.padEnd(11)} 术语 ${String(row.totalTerms).padStart(3)} 次 / 正文 ${row.chars} 字  ${row.hits.map(([t, n]) => t + "×" + n).join(" ")}`);
  }
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });