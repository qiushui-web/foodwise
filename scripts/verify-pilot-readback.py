from pathlib import Path
import urllib.request,json,base64,argparse
p=argparse.ArgumentParser();p.add_argument('--stage',required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1]; evidence=root/'docs/validation/landing-20261016'
password=(root/'.local-validation/landing-20261016/test-password.txt').read_text().strip()
auth='Basic '+base64.b64encode(('foodwise-admin:'+password).encode()).decode()
before=json.loads((evidence/'pre-restart-snapshot.json').read_text(encoding='utf-8'))
checks=[]
for path,expected in before.items():
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18096/api/v1'+path,headers={'Authorization':auth}),timeout=15) as r: actual=json.load(r)['data']
 assert actual==expected, 'Readback mismatch: '+path
 checks.append({'path':path,'equal':True})
report={'stage':a.stage,'checks':checks,'dataNature':'isolated synthetic acceptance; no field evidence'}
(evidence/(a.stage+'-readback.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report))
