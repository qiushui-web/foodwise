"""Disposable local pilot UI/API validation. Never use against a real pilot database."""
from pathlib import Path
from datetime import date,timedelta
from uuid import uuid4
import argparse, json, os
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/playwright/landing-20261016';OUT.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--confirm-disposable',action='store_true',help='Acknowledge all writes are to a disposable synthetic validation database')
args=parser.parse_args()
if not args.confirm_disposable: parser.error('--confirm-disposable is required; do not run against a real pilot database')
BASE=os.environ.get('FOODWISE_VALIDATION_BASE_URL','http://127.0.0.1:18096').rstrip('/')
if urlparse(BASE).hostname not in ('127.0.0.1','localhost','::1'): parser.error('Only loopback validation is allowed')
password=(ROOT/'.local-validation/landing-20261016/test-password.txt').read_text().strip()
report={'dataNature':'synthetic isolated acceptance only; not Hebei field evidence','views':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(http_credentials={'username':'foodwise-admin','password':password})
    api=context.request
    def get(path):
        r=api.get(BASE+'/api/v1'+path); assert r.ok,(r.status,r.text());return r.json()['data']
    def post(path,body,status=200,key=None):
        r=api.post(BASE+'/api/v1'+path,data=body,headers={'Idempotency-Key':key or str(uuid4())});assert r.status==status,(r.status,r.text());return r.json()
    assert get('/dishes')['total']==0, 'Use a new disposable empty pilot database, not an existing run'
    assert get('/stalls')['total']==0
    assert get('/orders')['total']==0
    assert get('/operations/feedback')['total']==0
    report['emptyBusinessTables']=True
    unauth=p.request.new_context()
    report['unauthenticatedStatus']=unauth.get(BASE+'/api/v1/dishes').status
    assert report['unauthenticatedStatus']==401
    unauth.dispose()
    page=context.new_page();page.goto(BASE+'/login');page.wait_for_load_state('networkidle')
    page.locator('input[name="username"]').fill('foodwise-admin')
    page.locator('input[name="password"]').fill(password)
    page.get_by_role('button',name='登录经营工作台').click()
    page.wait_for_url('**/app/dashboard')
    page.goto(BASE+'/app/onboarding');page.wait_for_load_state('networkidle')
    page.screenshot(path=str(OUT/'01-empty-onboarding.png'),full_page=True)
    fields={'学校名称':'隔离验收学校（构造）','学校代码/内部编号':'SYNTH-20261016','授权材料引用':'构造测试，无真实校园授权','档口名称':'验收档口（构造）','负责人':'验收人员','菜品名称':'验收菜品（构造）','售价（元）':'10','单位成本（元）':'6','操作人':'本地验收'}
    for label,value in fields.items(): page.get_by_label(label,exact=True).fill(value)
    page.get_by_role('button',name='保存建档',exact=True).click()
    expect(page.get_by_text('建档完成，编号已生成')).to_be_visible()
    dish=get('/dishes')['items'][0]['id']
    yesterday=(date.today()-timedelta(days=1)).isoformat()
    body=dict(businessDate=yesterday,mealPeriod='午餐',dishId=dish,plannedQty=100,preparedQty=100,soldQty=80,discountSoldQty=0,leftoverQty=20,revenue=800,weather='晴',eventTag='构造验收',recommendationAdopted=False,safetyConfirmed=True,operatorName='验收人员',note='非河北现场实采')
    post('/operations/feedback',body)
    for width,height in ((1440,1000),(390,844)):
        page.set_viewport_size({'width':width,'height':height});errors=[];failed=[]
        def on_console(msg):
            if msg.type in ('error','warning'): errors.append(msg.text)
        def on_error(error): errors.append(str(error))
        def on_response(r):
            if r.status>=400: failed.append({'url':r.url,'status':r.status})
        page.on('console',on_console);page.on('pageerror',on_error);page.on('response',on_response)
        page.goto(BASE+'/app/prediction');page.wait_for_load_state('networkidle')
        expect(page.get_by_label('可用库存（份）')).to_have_value('')
        page.get_by_role('combobox',name='餐次',exact=True).select_option('午餐')
        for label,value in {'可用库存（份）':'63','当餐产能上限（份）':'50','最小批量（份）':'10','提前期（分钟）':'20','开始准备':'10:00','开餐时间':'11:00','结束营业':'13:00'}.items(): page.get_by_label(label,exact=True).fill(value)
        page.get_by_role('button',name='生成备餐建议',exact=True).click()
        expect(page.get_by_role('button',name='生成并留档备餐计划')).to_be_enabled()
        page.get_by_role('button',name='生成并留档备餐计划').click()
        expect(page.get_by_text('计划已留档',exact=False)).to_be_visible()
        expect(page.get_by_role('button',name='确认执行计划',exact=True)).to_be_enabled()
        page.get_by_role('button',name='重新读回计划').click()
        expect(page.get_by_text('已从数据库读回本次备餐计划。')).to_be_visible()
        page.get_by_role('button',name='确认执行计划',exact=True).click()
        expect(page.get_by_text('执行计划已保存，闭餐后再填写实际结果。')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'horizontal overflow'
        page.screenshot(path=str(OUT/f'02-plan-{width}.png'),full_page=True)
        page.get_by_label('可用库存（份）').fill('0')
        expect(page.get_by_role('button',name='确认执行计划',exact=True)).to_be_disabled()
        page.get_by_role('button',name='生成并留档备餐计划').click()
        expect(page.locator('.plan-kpis strong').nth(2)).to_have_text('0 份')
        page.screenshot(path=str(OUT/f'03-zero-stock-{width}.png'),full_page=True)
        report['views'].append({'width':width,'overflow':False,'console':errors,'failedResources':failed,'zeroStock':True,'roundTripAndDecision':True})
        assert not errors and not failed,(errors,failed)
        page.remove_listener('console',on_console);page.remove_listener('pageerror',on_error);page.remove_listener('response',on_response)
    tomorrow=(date.today()+timedelta(days=1)).isoformat()
    pred=post('/predictions',dict(dishId=dish,weather='晴',examWeek=False,campusEvent=False,targetDate=tomorrow,mealPeriod='午餐',engine='rule',sourceNature='构造验收；非河北现场'))['data']['prediction']['predictionId']
    params=dict(stockServings=20,capacityServings=30,minimumBatch=10,leadMinutes=20,preparationStart='10:00',serviceStart='11:00',serviceEnd='13:00')
    key=str(uuid4());saved=post(f'/predictions/{pred}/preparation-plans',params,key=key)['data']
    post(f'/predictions/{pred}/preparation-plans',params,status=409,key=key)
    post('/predictions/999999/preparation-plans',params,status=400)
    post(f'/predictions/{pred}/preparation-plans',{**params,'stockServings':-1},status=400)
    post(f'/predictions/{pred}/feedback',dict(dishId=dish,targetDate=tomorrow,mealPeriod='午餐',adopted=True,adjustedQty=21,reason='超出约束测试'),status=400)
    assert get('/preparation-plans/'+str(saved['id']))==saved
    report['api']={'idempotency409':True,'missingPrediction400':True,'negativeInput400':True,'overCapacityDecision400':True,'roundTrip':True}
    report['persisted']={'dishId':dish,'planId':saved['id'],'predictionId':pred,'plannedTotal':saved['plan']['plannedTotal']}
    snapshot={path:get(path) for path in ('/dishes','/stalls','/orders','/operations/feedback',f'/preparation-plans/{saved["id"]}',f'/predictions/{pred}/replay')}
    (ROOT/'docs/validation/landing-20261016/pre-restart-snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    context.close();browser.close()
(ROOT/'docs/validation/landing-20261016/browser-flow.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
