const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));

  await page.goto("http://127.0.0.1:8089/app/prediction", { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForSelector(".assistant", { timeout: 20000 });
  await page.locator(".assistant-chip").first().click();
  await page.waitForSelector(".assistant-answer", { timeout: 20000 });

  const answer = (await page.locator(".assistant-text").innerText()).trim();
  const citations = await page.locator(".assistant-cites li").count();
  const action = (await page.locator(".assistant-action").innerText().catch(() => "")).trim();

  // 决策卡上的建议量必须与参谋回答一致，否则就是两套数在打架
  const cardText = (await page.locator(".band-labels span").nth(1).innerText()).trim();
  const cardQuantity = Number(cardText.replace(/[^\d]/g, ""));
  const assistantQuantity = Number((action.match(/建议量\s*(\d+)/) || [])[1] || -1);

  // 第二问：越界问题必须被挡回
  await page.fill(".assistant-ask input", "这个菜还新鲜吗");
  await page.locator(".assistant-ask button").click();
  await page.waitForFunction(
    () => document.querySelector(".assistant-refusal") !== null,
    null,
    { timeout: 20000 });
  const refusal = (await page.locator(".assistant-refusal").innerText()).trim();

  // 成本试算：改损耗率，后悔上界与临界比必须跟着动，但记录仍走主数据
  const readRow = async (label) => {
    const rows = page.locator(".dc-cost div");
    const count = await rows.count();
    for (let i = 0; i < count; i += 1) {
      const dt = (await rows.nth(i).locator("dt").innerText()).trim();
      if (dt === label) return (await rows.nth(i).locator("dd").innerText()).trim();
    }
    return "";
  };
  const readRowSettled = async (label, before = "") => {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      const value = await readRow(label);
      if (value && value !== before) return value;
      await page.waitForTimeout(200);
    }
    return before ? `未变化:${before}` : "";
  };
  const regretBefore = await readRow("后悔上界");
  const ratioBefore = await readRow("临界比 Cu/Co");
  const trial = page.locator(".dc-trial");
  await trial.locator("input").nth(0).fill("13");
  await trial.locator("input").nth(1).fill("5.2");
  await trial.locator("input").nth(2).fill("10");
  await trial.locator("button").first().click();
  const regretAfter = await readRowSettled("后悔上界", regretBefore);
  const ratioAfter = await readRowSettled("临界比 Cu/Co");
  const lossRow = await readRowSettled("制作损耗");

  if (cardQuantity !== assistantQuantity) {
    throw new Error(`决策卡建议量 ${cardQuantity} 与参谋回答 ${assistantQuantity} 不一致`);
  }
  if (!lossRow.includes("10%")) {
    throw new Error(`制作损耗行没有按试算更新：${lossRow}`);
  }
  if (regretBefore === regretAfter) {
    throw new Error(`后悔上界没有随成本变化：${regretBefore}`);
  }
  if (ratioBefore === ratioAfter) {
    throw new Error(`临界比没有随成本变化：${ratioBefore}`);
  }

  await page.screenshot({ path: "output/assistant-panel.png", fullPage: false });
  console.log(JSON.stringify({ answer, citations, action, cardQuantity, assistantQuantity, consistent: true,
    refusal, costTrial: { regretBefore, regretAfter, ratioBefore, ratioAfter, lossRow },
    consoleErrors }, null, 2));
  await browser.close();
})().catch((error) => {
  console.error("FAILED:", error);
  process.exit(1);
});