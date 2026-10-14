import { expect, test } from '@playwright/test';

const prefix=process.env.FOODWISE_PREFIX_TEST_URL;
test.skip(!prefix || !process.env.FOODWISE_TEST_PASSWORD, 'Disposable authenticated instance required.');
test.use({ baseURL:prefix || 'http://127.0.0.1:18089' });
test('writes refresh aggregates, predictions persist, discounts publish and orders verify once',async ({ playwright })=>{
  const api=await playwright.request.newContext({baseURL:prefix!,httpCredentials:{username:'foodwise-admin',password:process.env.FOODWISE_TEST_PASSWORD!}});
  const post=async (endpoint:string,data:unknown,key=crypto.randomUUID())=>api.post('/foodwise/api/v1'+endpoint,{data,headers:{'Idempotency-Key':key}});
  const before=await (await api.get('/foodwise/api/v1/analytics/metadata')).json();
  const exported=await api.get('/foodwise/api/v1/operations/export');
  expect(exported.ok()).toBeTruthy(); expect(await exported.text()).toContain('营业日期,餐次,档口');
  const dishPage=await (await api.get('/foodwise/api/v1/dishes?page=1&size=1')).json();
  expect(dishPage.data.items).toHaveLength(1);expect(dishPage.data.total).toBeGreaterThan(1);
  const dish=dishPage.data.items[0];
  const today=new Intl.DateTimeFormat('sv-SE').format(new Date());
  const qty=100;
  const key=crypto.randomUUID();
  const body={businessDate:today,mealPeriod:'晚餐',dishId:dish.id,plannedQty:qty,preparedQty:qty,soldQty:70,discountSoldQty:0,leftoverQty:30,revenue:700,weather:'晴',eventTag:'本地测试',recommendationAdopted:false,safetyConfirmed:true,operatorName:'验收测试',note:'独立H2实例'};
  const saved=await post('/operations/feedback',body,key);expect(saved.ok()).toBeTruthy();
  const repeated=await post('/operations/feedback',body,key);expect(repeated.status()).toBe(409);
  const after=await (await api.get('/foodwise/api/v1/analytics/metadata')).json();
  const updated=(await saved.json()).data.updated; expect(after.data.records).toBe(before.data.records+(updated?0:1));
  const predicted=await post('/predictions',{dishId:dish.id,weather:'晴',examWeek:false,campusEvent:false,engine:'rule',targetDate:new Intl.DateTimeFormat('sv-SE').format(new Date(Date.now()+86400000)),mealPeriod:'晚餐'});
  expect(predicted.ok()).toBeTruthy();expect((await predicted.json()).data.prediction.predictionId).toBeGreaterThan(0);
  const recommendation=await post('/intelligence/offers/recommend',{dishId:dish.id});expect(recommendation.ok()).toBeTruthy();
  const rec=(await recommendation.json()).data;
  const offer=await post('/offers',{dishId:dish.id,quantity:rec.recommendedQty,offerPrice:rec.recommendedPrice,startTime:'00:00',endTime:'23:59:59',safetyConfirmed:true});expect(offer.ok()).toBeTruthy();
  const orders=await (await api.get('/foodwise/api/v1/orders')).json();const pending=orders.data.items.find((r:{status:string})=>r.status==='待取餐');expect(pending).toBeTruthy();
  expect((await post(`/orders/${pending.id}/verify`,{})).ok()).toBeTruthy();
  expect((await post(`/orders/${pending.id}/verify`,{})).ok()).toBe(false);
  await api.dispose();
});

test('analyst can read but cannot submit operational writes',async ({playwright})=>{
  const api=await playwright.request.newContext({baseURL:prefix!,httpCredentials:{username:'foodwise-analyst',password:process.env.FOODWISE_TEST_PASSWORD!}});
  expect((await api.get('/foodwise/api/v1/analytics/backtest')).ok()).toBeTruthy();
  expect((await api.post('/foodwise/api/v1/predictions',{data:{dishId:1,weather:'晴'},headers:{'Idempotency-Key':crypto.randomUUID()}})).status()).toBe(403);
  await api.dispose();
});

test('CSV preview then mixed import reports accepted and rejected rows',async ({page})=>{
  await page.goto('/foodwise/login');
  await page.locator('input[name="username"]').fill('foodwise-admin');
  await page.locator('input[name="password"]').fill(process.env.FOODWISE_TEST_PASSWORD!);
  await page.getByRole('button',{name:'登录经营工作台'}).click();
  await page.goto('/foodwise/app/operations/feedback');
  await page.getByRole('tab',{name:'CSV 批量导入'}).click();
  const date=new Intl.DateTimeFormat('sv-SE').format(new Date(Date.now()-86400000));
  await page.locator('input[type="file"]').setInputFiles({name:'mixed.csv',mimeType:'text/csv',buffer:Buffer.from(`business_date,meal_period,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather\n${date},早餐,1,10,10,8,0,2,80,晴\n${date},晚餐,1,10,10,8,0,9,80,晴\n`)});
  await page.getByRole('button',{name:'先预览文件'}).click();
  await expect(page.getByText('表头齐全，可以继续核对')).toBeVisible();
  await page.getByRole('textbox',{name:'导入记录人'}).fill('验收测试');
  await page.getByRole('checkbox',{name:/已核对 CSV 来源/}).check();
  await page.getByRole('button',{name:'确认导入台账'}).click();
  await expect(page.getByText('导入完成：1 行成功，1 行被拒绝')).toBeVisible();
  await expect(page.getByText(/第3行: 数量不守恒/)).toBeVisible();
});
