"""Measure sequential loopback GET latency; never a production load claim."""
import argparse, base64, json, math, os, platform, time
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url',default='http://127.0.0.1:18096')
    p.add_argument('--samples',type=int,default=30)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    if urlparse(a.base_url).hostname not in ('127.0.0.1','localhost','::1'): p.error('Only loopback URLs are allowed')
    if not 5 <= a.samples <= 500: p.error('samples must be 5..500')
    headers={}
    if os.environ.get('FOODWISE_TEST_PASSWORD'):
        headers['Authorization']='Basic '+base64.b64encode(('foodwise-admin:'+os.environ['FOODWISE_TEST_PASSWORD']).encode()).decode()
    rows=[]
    for endpoint in ('/api/v1/dishes','/api/v1/onboarding/readiness','/api/v1/reports'):
        durations=[]
        for i in range(a.samples+3):
            start=time.perf_counter()
            with urlopen(Request(a.base_url+endpoint,headers=headers),timeout=15) as r:
                body=json.load(r)
                if r.status!=200 or not body.get('success'): raise RuntimeError('Unexpected API response')
            if i>=3: durations.append((time.perf_counter()-start)*1000)
        durations.sort()
        rows.append(dict(endpoint=endpoint,samples=a.samples,p50_ms=durations[math.ceil(a.samples*.5)-1],p95_ms=durations[math.ceil(a.samples*.95)-1],max_ms=max(durations)))
    report=dict(scope='local sequential authenticated GET; includes HTTP Basic verification; not production/concurrent prediction latency',platform=platform.platform(),python=platform.python_version(),warmups=3,rows=rows)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
