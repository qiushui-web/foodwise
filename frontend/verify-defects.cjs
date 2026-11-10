// 六个已知缺陷的浏览器 / HTTP 双重复核。
const { chromium } = require("playwright");
const base = process.argv[2] || "http://127.0.0.1:8089";

(async () => {
  const report = {};
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

  // 缺陷1：时间戳带 +08:00
  const health = await (await page.request.get(`${base}/api/health`)).json();
  report.health = { timestamp: health.timestamp, timezone: health.timezone };

  // 缺陷4：登录标题不重复
  await page.goto(`${base}/login`, { waitUntil: "networkidle" });
  report.loginTitle = await page.title();

  // 缺陷2/3：命名与英文
  await page.goto(`${base}/app/insights/realtime`, { waitUntil: "networkidle" });
  report.realtime = {
    title: await page.title(),
    heading: await page.locator("h2").first().innerText(),
    kicker: await page.locator(".kicker").first().innerText(),
    sidebarHasEntry: await page.locator('.sidebar a[href$="/app/insights/realtime"]').count(),
  };

  await page.goto(`${base}/app/insights/demand`, { waitUntil: "networkidle" });
  report.demand = {
    heading: await page.locator("h2").first().innerText(),
    kicker: await page.locator(".panel .kicker").first().innerText(),
    unitLine: (await page.locator(".panel .source-note").first().innerText()).split("\n")[0],
    hasEnglishUnit: (await page.locator("#main-content").innerText()).includes("scaled store sales"),
  };

  // 缺陷6：分析页入口
  report.nav = {
    insightsLinks: await page.locator('.sidebar nav[aria-label="分析视图"] a').count(),
    evidenceLink: await page.locator('.sidebar a[href$="/app/evidence"]').count(),
  };

  // 缺陷5：软 404
  const bad = await page.request.get(`${base}/app/no-such-page`, { failOnStatusCode: false });
  const good = await page.request.get(`${base}/app/evidence`, { failOnStatusCode: false });
  report.statusCodes = { unknown: bad.status(), known: good.status() };

  // 总览动作清单
  await page.goto(`${base}/app/dashboard`, { waitUntil: "networkidle" });
  report.dashboard = {
    actions: await page.locator(".next-content .action-link").allInnerTexts(),
    evidenceFooter: await page.locator(".next-content .action-more").innerText(),
  };
  await page.screenshot({ path: "verify-dashboard.png", fullPage: true });

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch((error) => { console.error("DEFECT_CHECK_FAILED " + error.message); process.exit(1); });