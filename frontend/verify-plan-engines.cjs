// 计划页完整链路：生成建议 → 决策卡 → 可打印执行单；引擎选择器只保留两个。
const { chromium } = require("playwright");
const base = process.argv[2] || "http://127.0.0.1:8089";
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/app/prediction`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);

  const engineOptions = await page.locator('label:has-text("决策引擎") select').locator("option").allTextContents();

  await page.getByRole("button", { name: /生成备餐建议/ }).click();
  await page.waitForTimeout(1600);

  const text = await page.locator("main").innerText();
  const report = {
    engineOptions,
    engineOptionCount: engineOptions.length,
    hasNoRuleOption: !engineOptions.some((label) => label.includes("规则")),
    hasIntervalBand: text.includes("区间"),
    hasCriticalRatio: text.includes("临界比"),
    hasDecisionCard: text.includes("建议备餐") || text.includes("首锅") || text.includes("补餐"),
    hasPrintSheet: (await page.locator(".print-sheet").count()) > 0 || text.includes("备餐执行单"),
    hasPrintButton: text.includes("打印执行单"),
    consoleErrors: errors,
  };
  await page.screenshot({ path: "verify-plan-engines.png", fullPage: true });
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
  if (errors.length || !report.hasNoRuleOption || !report.hasDecisionCard || !report.hasPrintSheet) process.exit(1);
})().catch((e) => { console.error("PLAN_CHECK_FAILED " + e.message); process.exit(1); });