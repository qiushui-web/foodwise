const { chromium } = require('../frontend/node_modules/playwright');
const fs = require('fs'); const path = require('path');
const root = 'E:/食刻有数/计划书/计划书照片/网站截图';
const out = path.join(root,'当前版本_20261109');
const previous=JSON.parse(fs.readFileSync(path.join(root,'当前版本_20261109/截图索引.json'),'utf8').replace(/^\uFEFF/,''));
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch();
 const context=await browser.newContext({viewport:{width:1600,height:1000},deviceScaleFactor:2,locale:'zh-CN',reducedMotion:'reduce'});
 const page=await context.newPage(); const errors=[]; const records=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8098/login',{waitUntil:'networkidle'});
 await page.locator('input[name="username"]').fill('admin');
 await page.locator('input[name="password"]').fill('1234567890');
 await Promise.all([page.waitForURL(/\/app\//),page.locator('button[type="submit"]').click()]);
 for(const item of previous.screenshots.filter(s=>s.file.endsWith('_页面.png'))){
  await page.goto('http://127.0.0.1:8098'+item.route,{waitUntil:'networkidle'});
  await page.evaluate(async()=>{await document.fonts.ready; await Promise.all(Array.from(document.images).map(i=>i.decode().catch(()=>{})));});
  await page.waitForTimeout(700);
  const file=item.file.replace('_桌面','_页面');
  await page.screenshot({path:path.join(out,file),fullPage:false,animations:'disabled'});
  records.push({file,route:item.route,viewport:{width:1600,height:1000},pixels:{width:3200,height:2000},nature:'本地演示界面；正常桌面视口，未拼接、未拉伸、未修改页面内容'});
  console.log(file);
 }
 await page.setViewportSize({width:1600,height:1200});
 for(const [file,route,selector] of [['16_备餐建议_操作特写.png','/app/prediction','.result-panel'],['17_经营记录_录入表单.png','/app/operations/feedback','form'],['18_经营复盘_记录对照.png','/app/reports','.panel'],['19_首次建档_信息填写.png','/app/onboarding','form.form']]){
  await page.goto('http://127.0.0.1:8098'+route,{waitUntil:'networkidle'});
  await page.evaluate(()=>document.fonts.ready); await page.waitForTimeout(500);
  const el=page.locator(selector).first(); const box=await el.boundingBox();
  await el.screenshot({path:path.join(out,file),animations:'disabled'});
  records.push({file,route,kind:'操作区域原生截图',cssSize:{width:box.width,height:box.height},nature:'本地演示界面，未修改内容；用于说明书局部讲解'});
 }
 fs.writeFileSync(path.join(out,'截图索引.json'),JSON.stringify({date:'2026-11-09',screenshots:records,errors},null,2));
 await browser.close(); if(errors.length) throw Error(errors.join('\n'));
})().catch(e=>{console.error(e);process.exit(1)});
