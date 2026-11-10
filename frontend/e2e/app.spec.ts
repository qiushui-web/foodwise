import { expect, test } from "@playwright/test";

test("dashboard shows the data scope and a usable next step", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/app/dashboard");
  await expect(page.getByRole("heading", { name: "经营总览" })).toBeVisible();
  await expect(page.getByText("实际备餐", { exact: true })).toBeVisible();
  await expect(page.locator(".dashboard-summary strong").first()).toHaveText(/\d+/);
  await expect(page.getByRole("heading", { name: "近期备餐与售出" })).toBeVisible();
  const nextStep = page.getByRole("main").getByRole("link", { name: /先录入台账|制定备餐计划/ });
  await expect(nextStep).toHaveAttribute("href", /\/app\/(operations\/feedback|prediction)$/);
  await page.goto("/app/prediction");
  await expect(page.getByRole("heading", { name: "确定下一餐备多少" })).toBeVisible();
  await expect(page.getByLabel("决策引擎")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("mobile navigation opens and business pages are not placeholders", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "This flow validates the mobile menu breakpoint.");
  await page.goto("/app/stalls");
  await expect(page.getByRole("heading", { name: "看清每个档口" })).toBeVisible();
  await page.getByRole("button", { name: "打开菜单" }).click();
  await expect(page.getByRole("navigation", { name: "日常流程" }).getByRole("link")).toHaveCount(4);
  await expect(page.getByRole("navigation", { name: "日常流程" }).getByRole("link", { name: /首次建档/ })).toHaveCount(0);
  await page.getByRole("navigation", { name: "日常流程" }).getByRole("link", { name: /经营复盘/ }).click();
  await expect(page).toHaveURL(/\/app\/reports$/);
  await page.getByRole("button", { name: "打开菜单" }).click();
  await page.locator(".sidebar-foot").getByRole("link", { name: /使用说明/ }).click();
  await expect(page.getByRole("link", { name: /需求分析/ })).toBeVisible();
  await page.getByRole("link", { name: /需求分析/ }).click();
  await expect(page).toHaveURL(/\/app\/insights\/demand$/);
  await expect(page.getByRole("heading", { name: "需求预测分析" }).last()).toBeVisible();
});

test("daily workflow links from a same-day record to remaining food and final review", async ({ page }) => {
  await page.goto("/app/operations/feedback");
  await expect(page.getByRole("main").getByRole("link", { name: /处理剩余/ })).toHaveAttribute("href", /\/app\/offers$/);
  await page.getByRole("main").getByRole("link", { name: /处理剩余/ }).click();
  await expect(page).toHaveURL(/\/app\/offers$/);
  await expect(page.getByRole("main").getByRole("link", { name: /核销订单/ })).toHaveAttribute("href", /\/app\/orders$/);
  await expect(page.getByRole("main").getByRole("link", { name: /回填最终结果/ })).toHaveAttribute("href", /\/app\/operations\/feedback$/);
  await page.goto("/app/about");
  await expect(page.getByRole("link", { name: /需求分析/ })).toHaveAttribute("href", /\/app\/insights\/demand$/);
});

test("all business routes load without console or page errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  const routes = [
    ["/app/dashboard", "经营总览"], ["/app/stalls", "看清每个档口"],
    ["/app/prediction", "确定下一餐备多少"], ["/app/offers", "把剩余风险转化为动作"],
    ["/app/orders", "订单核销"], ["/app/operations/feedback", "把实际经营结果记下来"],
    ["/app/alerts", "经营预警中心"], ["/app/reports", "把经营变化算清楚"],
    ["/app/insights/realtime", "营业快照分析"], ["/app/insights/demand", "需求预测分析"],
    ["/app/insights/waste", "减损场景分析"], ["/app/about", "第一次使用食刻有数"],
  ] as const;
  for (const [route, heading] of routes) {
    await page.goto(route);
    await expect(page.getByRole("heading", { name: heading }).last()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("CSV import requires preview and explicit safety confirmation", async ({ page }) => {
  await page.goto("/app/operations/feedback");
  await page.getByRole("tab", { name: "数据批量导入" }).click();
  const importButton = page.getByRole("button", { name: "确认导入台账" });
  await expect(importButton).toBeDisabled();
  await page.locator('input[type="file"]').setInputFiles({
    name: "invalid.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("business_date,dish_id\n2026-10-01,1\n"),
  });
  await page.getByRole("button", { name: "先预览文件" }).click();
  await expect(page.getByText("缺少必填字段")).toBeVisible();
  await expect(importButton).toBeDisabled();
  await page.locator('input[type="file"]').setInputFiles({
    name: "valid.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("business_date,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather\n2026-10-01,1,10,10,8,1,2,80,晴\n"),
  });
  await page.getByRole("button", { name: "先预览文件" }).click();
  await expect(page.getByText("表头齐全，可以继续核对")).toBeVisible();
  await expect(importButton).toBeDisabled();
  await page.getByRole("textbox", { name: "导入记录人" }).fill("测试操作员");
  await page.getByRole("checkbox", { name: /已核对数据来源/ }).check();
  await expect(importButton).toBeDisabled();
  await page.getByRole("textbox", { name: "来源名称", exact: true }).fill("测试台账");
  await page.getByRole("textbox", { name: "来源提供方", exact: true }).fill("测试提供方");
  await page.getByRole("textbox", { name: "来源地域或范围", exact: true }).fill("合成验证数据");
  await page.getByRole("textbox", { name: "授权或许可引用", exact: true }).fill("待核验");
  await expect(importButton).toBeEnabled();
});

test("pickup code lookup verifies order details before enabling handoff", async ({ page }) => {
  await page.goto("/app/orders");
  await page.getByRole("button", { name: "核对取餐" }).first().click();
  await expect(page.getByRole("status").getByRole("button", { name: "餐品已交付，确认核销" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("取餐码");
  await page.getByRole("textbox", { name: "取餐码" }).fill("000000");
  await page.getByRole("button", { name: "查找订单" }).click();
  await expect(page.getByRole("alert")).toContainText("未找到该取餐码");
  await expect(page.getByRole("status")).toHaveCount(0);
});

test("stale inventory cannot produce an offer and form stays usable", async ({ page }) => {
  await page.goto("/app/offers");
  await page.getByRole("button", { name: "生成建议" }).click();
  await expect(page.getByRole("alert")).toContainText("缺少今天的经营记录");
  await expect(page.getByRole("combobox", { name: "选择菜品" })).toBeVisible();
  await expect(page.getByRole("button", { name: "生成建议" })).toBeEnabled();
});

test("key workbench screens fit the viewport without page overflow", async ({ page }) => {
  for (const route of ["dashboard", "orders", "operations/feedback", "alerts"]) {
    await page.goto(`/app/${route}`);
    await expect(page.locator(".view-head h2, .dashboard-intro h2").first()).toBeVisible();
    const widths = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: window.innerWidth }));
    expect(widths.page, `${route}: ${widths.page}px exceeds ${widths.viewport}px`).toBeLessThanOrEqual(widths.viewport + 1);
  }
});
