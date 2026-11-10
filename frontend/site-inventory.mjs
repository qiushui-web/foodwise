// Site content inventory: capture every routed page, its visible text and a screenshot.
// Usage: node site-inventory.mjs  (run from frontend/, app served at http://localhost:8089)
import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

const BASE = process.env.SITE_BASE || "http://localhost:8089";
const OUT = path.resolve(
  "..",
  ".local-validation",
  "site-audit-20261027"
);

const pages = [
  ["login", "/login"],
  ["dashboard", "/app/dashboard"],
  ["onboarding", "/app/onboarding"],
  ["stalls", "/app/stalls"],
  ["prediction", "/app/prediction"],
  ["feedback", "/app/operations/feedback"],
  ["offers", "/app/offers"],
  ["orders", "/app/orders"],
  ["alerts", "/app/alerts"],
  ["reports", "/app/reports"],
  ["insights-realtime", "/app/insights/realtime"],
  ["insights-demand", "/app/insights/demand"],
  ["insights-waste", "/app/insights/waste"],
  ["about", "/app/about"],
  ["notfound", "/app/not-a-real-page"],
];

await fs.mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, locale: "zh-CN" });
const page = await context.newPage();

const report = [];
for (const [name, route] of pages) {
  const consoleErrors = [];
  const onConsole = (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  };
  page.on("console", onConsole);
  const response = await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(700);

  const data = await page.evaluate(() => {
    const clean = (value) => (value || "").replace(/\s+/g, " ").trim();
    const main = document.querySelector("main") || document.body;
    const headings = [...main.querySelectorAll("h1,h2,h3,h4,h5")].map((el) => ({
      tag: el.tagName.toLowerCase(),
      text: clean(el.textContent),
    }));
    const nav = [...document.querySelectorAll("nav a, aside a")].map((a) => clean(a.textContent)).filter(Boolean);
    const links = [...main.querySelectorAll("a")].map((a) => clean(a.textContent)).filter(Boolean);
    const buttons = [...main.querySelectorAll("button")].map((b) => clean(b.textContent)).filter(Boolean);
    const details = [...main.querySelectorAll("details > summary")].map((s) => clean(s.textContent));
    const tableHeaders = [...main.querySelectorAll("th")].map((t) => clean(t.textContent));
    const paragraphs = [...main.querySelectorAll("p, li, .kicker, .source-note, small")]
      .map((el) => clean(el.textContent))
      .filter((t) => t.length > 1);
    return {
      title: document.title,
      eyebrow: clean(document.querySelector(".kicker")?.textContent),
      headings,
      nav: [...new Set(nav)],
      links: [...new Set(links)],
      buttons: [...new Set(buttons)],
      details: [...new Set(details)],
      tableHeaders: [...new Set(tableHeaders)],
      paragraphs: [...new Set(paragraphs)],
      h1: clean(document.querySelector("h1")?.textContent),
    };
  });

  const shot = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: shot, fullPage: true });

  report.push({
    name,
    route,
    status: response ? response.status() : null,
    finalUrl: page.url(),
    consoleErrors,
    ...data,
  });
  page.off("console", onConsole);
}

// Mobile pass for the two most important screens
await page.setViewportSize({ width: 390, height: 844 });
for (const [name, route] of [["dashboard", "/app/dashboard"], ["prediction", "/app/prediction"]]) {
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `mobile-390-${name}.png`), fullPage: true });
}

await fs.writeFile(path.join(OUT, "inventory.json"), JSON.stringify(report, null, 2), "utf8");
console.log("captured", report.length, "pages into", OUT);
await browser.close();