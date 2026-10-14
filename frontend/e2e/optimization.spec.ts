import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('unknown route and session failure explain the next action', async ({ page }) => {
  await page.goto('/app/no-such-page');
  await expect(page.getByRole('heading', { name: '未找到这个页面' })).toBeVisible();
  await page.route('**/api/v1/session', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ success:false, message:'测试会话故障' }) }));
  await page.goto('/app/stalls');
  await expect(page.getByText('会话加载失败，请刷新页面；导航暂不可用。')).toBeVisible();
  await expect(page.locator('.sidebar nav a')).toHaveCount(0);
});

test('narrow screens and enlarged text keep reports readable', async ({ page }, info) => {
  const output = path.resolve('../docs/screenshots/optimization-implementation-20261013');
  fs.mkdirSync(output, { recursive: true });
  for (const width of [1440,390,320]) {
    await page.setViewportSize({ width, height:900 });
    for (const route of ['reports','insights/demand','stalls']) {
      await page.goto('/app/' + route);
      await expect(page.locator('main .view-head h2')).toBeVisible();
      await expect(page.locator('main .fw-state')).toHaveCount(0);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      expect(overflow, `${width} ${route}`).toBe(false);
      if (info.project.name === 'chromium') await page.screenshot({ path:path.join(output,`${route.replace('/','-')}-${width}.png`), fullPage:true });
    }
  }
  await page.setViewportSize({ width:720, height:450 });
  await page.goto('/app/reports');
  await page.addStyleTag({content:'main *{font-size:200%!important;line-height:1.5!important}'});
  await expect(page.getByRole('heading',{name:'冻结测试集验证'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('mobile drawer closes on Escape and returns keyboard focus', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'Mobile breakpoint only.');
  await page.goto('/app/stalls');
  const button=page.getByRole('button',{name:'打开菜单'});
  await button.click();
  await expect(button).toHaveAttribute('aria-expanded','true');
  await page.keyboard.press('Escape');
  await expect(button).toHaveAttribute('aria-expanded','false');
  await expect(button).toBeFocused();
});
