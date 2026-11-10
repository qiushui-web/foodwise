// 复盘页归因面板：数字来自实验产物，且拒绝因果声明。
const { chromium } = require("playwright");
const base = process.argv[2] || "http://127.0.0.1:8089";
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/app/reports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);

  const panel = page.locator("section, .data-panel, div").filter({ hasText: "能从数据里" }).first();
  const text = await page.locator("main").innerText();
  const report = {
    hasAttributionHeading: text.includes("能从数据里"),
    hasObservedGap: /观测差异\s*\n?\s*[\d.]+ pp/.test(text),
    hasMde: text.includes("可识别下限"),
    hasRequiredDays: text.includes("个营业日"),
    hasNegativeControlWarning: text.includes("没有任何干预上线"),
    hasDescriptiveOnly: text.includes("描述性对照"),
    reviewPanelRestored: text.includes("建议、计划和实际差在哪里"),
    consoleErrors: errors,
    excerpt: text.split("\n").filter((l) => l.includes("pp") || l.includes("营业日")).slice(0, 8),
  };
  await page.screenshot({ path: "verify-reports-attribution.png", fullPage: true });
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
  if (errors.length || !report.hasAttributionHeading || !report.hasNegativeControlWarning) process.exit(1);
})().catch((e) => { console.error("REPORTS_CHECK_FAILED " + e.message); process.exit(1); });