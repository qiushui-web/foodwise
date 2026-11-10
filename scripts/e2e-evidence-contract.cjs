const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));

  await page.goto("http://127.0.0.1:8089/app/evidence", { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForSelector(".assistant-contract", { timeout: 20000 });

  const stats = await page.locator(".contract-stats li").allInnerTexts();
  const rows = await page.locator(".assistant-contract tbody tr").count();
  const codes = await page.locator(".assistant-contract tbody tr td:first-child").allInnerTexts();
  const examples = await page.locator(".assistant-contract tbody tr td.examples").allInnerTexts();
  const note = (await page.locator(".assistant-contract .source-note").first().innerText()).trim();

  const refusedSum = await page.evaluate(() => {
    const rows = [...document.querySelectorAll(".assistant-contract tbody tr")];
    return rows.reduce((sum, row) => sum + Number(row.lastElementChild.textContent.trim()), 0);
  });

  if (rows !== 5) throw new Error(`拒绝码应为 5 行，实际 ${rows}`);
  if (refusedSum !== 26) throw new Error(`五类拒绝条数之和应为 26，实际 ${refusedSum}`);
  if (!note.includes("50") || !note.includes("26")) {
    throw new Error(`来源说明没有带出 50/26：${note}`);
  }
  if (!examples.some((text) => text.includes("「"))) {
    throw new Error("示例问法没有渲染出来");
  }

  for (const selector of [".panel.limits", ".commands", ".negative-control"]) {
    if (await page.locator(selector).count() === 0) throw new Error(`证据页缺少区块 ${selector}`);
  }

  await page.locator(".assistant-contract").scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.locator(".assistant-contract").screenshot({ path: "output/evidence-contract.png" });
  console.log(JSON.stringify({
    stats, rows, codes, refusedSum,
    firstExample: examples[0]?.split("\n")[0],
    consoleErrors,
  }, null, 2));
  await browser.close();
})().catch((error) => {
  console.error("FAILED:", error.message);
  process.exit(1);
});