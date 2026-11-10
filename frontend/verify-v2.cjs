// 用真实浏览器确认 v2 页面的关键信息确实渲染出来，而不是只通过 HTTP 200。
const { chromium } = require("playwright");

const base = process.argv[2] || "http://127.0.0.1:8089";

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: "zh-CN" });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  page.on("pageerror", (error) => consoleErrors.push("pageerror:" + error.message));

  const report = {};

  await page.goto(`${base}/app/evidence`, { waitUntil: "networkidle" });
  report.evidence = {
    heading: await page.locator("h2").first().innerText(),
    engineText: (await page.locator(".evidence-card").nth(3).innerText()).replace(/\n/g, " | "),
    methodRows: await page.locator("table").first().locator("tbody tr").count(),
    scenarioRows: await page.locator("table").nth(1).locator("tbody tr").count(),
    limits: await page.locator(".limits li").count(),
  };
  await page.screenshot({ path: "verify-evidence.png", fullPage: true });

  await page.goto(`${base}/app/prediction`, { waitUntil: "networkidle" });
  await page.locator(".decision-card").waitFor({ state: "visible", timeout: 15000 });
  const engineSelect = page.locator("select").filter({ has: page.locator('option[value="calibrated-quantile"]') });
  report.prediction = {
    cardTitle: await page.locator("#decision-card-title").innerText(),
    calibratedBand: (await page.locator(".band-labels").innerText()).replace(/\n/g, " | "),
    calibratedMethod: await page.locator(".dc-formula").innerText(),
    costCells: await page.locator(".dc-cost div").count(),
  };

  // 切到未校准对照，界面上的区间和建议量必须跟着变
  await engineSelect.selectOption("quantile");
  await page.waitForFunction(() => document.querySelector(".dc-engine")?.textContent?.includes("未校准"), null, { timeout: 15000 });
  report.prediction.contrastBand = (await page.locator(".band-labels").innerText()).replace(/\n/g, " | ");
  report.prediction.contrastMethod = await page.locator(".dc-formula").innerText();
  await page.screenshot({ path: "verify-prediction.png", fullPage: true });

  report.consoleErrors = consoleErrors;
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch((error) => { console.error("BROWSER_CHECK_FAILED " + error.message); process.exit(1); });