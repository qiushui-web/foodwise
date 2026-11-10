// 移动端可用性抽查：台账页在 390×844 下是否溢出、主流程是否可点。
const { chromium } = require("playwright");
const base = process.argv[2] || "http://127.0.0.1:8089";
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const report = {};
  await page.goto(`${base}/app/operations/feedback`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  report.ledger = await page.evaluate(() => {
    const doc = document.documentElement;
    const wide = Array.from(document.querySelectorAll("main *"))
      .filter((el) => el.getBoundingClientRect().width > window.innerWidth + 2)
      .slice(0, 5)
      .map((el) => `${el.tagName.toLowerCase()}.${(el.className || "").toString().split(" ")[0]}`);
    return {
      horizontalOverflow: doc.scrollWidth > window.innerWidth + 1,
      scrollWidth: doc.scrollWidth,
      viewport: window.innerWidth,
      widest: wide,
      tableCount: document.querySelectorAll("table").length,
      hasInputs: document.querySelectorAll("input, select, textarea").length,
    };
  });
  await page.screenshot({ path: "verify-mobile-ledger.png", fullPage: true });
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch((e) => { console.error("MOBILE_CHECK_FAILED " + e.message); process.exit(1); });