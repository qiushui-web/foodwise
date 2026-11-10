const { chromium } = require("playwright");
const routes = ["dashboard", "prediction", "orders", "stalls", "onboarding", "reports", "offers",
  "operations/feedback", "alerts", "insights/realtime", "insights/demand", "insights/waste", "about", "evidence"];
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  for (const route of routes) {
    await page.goto(`http://127.0.0.1:8089/app/${route}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const text = await page.locator("#main-content").innerText();
    const latin = text.split("\n").filter((line) => (line.match(/[A-Za-z]{3,}\s+[A-Za-z]{3,}\s+[A-Za-z]{3,}/) || []).length > 0);
    if (latin.length) console.log(`--- ${route}\n` + latin.slice(0, 6).join("\n"));
  }
  await browser.close();
})();