// 证据页归因区：确认渲染的是磁盘产物里的真实数字，且明确写着“不可识别”。
const { chromium } = require("playwright");
const base = process.argv[2] || "http://127.0.0.1:8089";
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const consoleErrors = [];
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  page.on("pageerror", (err) => consoleErrors.push(err.message));

  await page.goto(`${base}/app/evidence`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);

  const api = await (await page.request.get(`${base}/api/v1/model/evidence`)).json();
  const attr = api.data.attributionExperiment || {};
  const section = page.locator("section.panel", { hasText: "归因与负对照" });
  const rows = await section.locator("tbody tr").count();
  const text = await section.innerText();
  const report = {
    apiProtocol: attr.protocol,
    apiRecoveryKeys: Object.keys(attr.recovery || {}),
    apiVerdict: attr.real_ledger?.verdict,
    sectionRows: rows,
    hasNotIdentifiable: text.includes("不可识别"),
    hasNegativeControl: text.includes("负对照"),
    hasItsBias: text.includes(String(attr.recovery?.["effect_-5pct"]?.its?.bias?.toFixed?.(2) ?? "")),
    mde: attr.real_ledger?.min_detectable_effect_pp,
    requiredDays: attr.real_ledger?.required_days_for_5pp,
    textHead: text.split("\n").slice(0, 6),
    consoleErrors,
  };
  await page.screenshot({ path: "verify-attribution.png", fullPage: true });
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
  if (consoleErrors.length || rows < 6 || !report.hasNotIdentifiable) process.exit(1);
})().catch((e) => { console.error("ATTRIBUTION_CHECK_FAILED " + e.message); process.exit(1); });