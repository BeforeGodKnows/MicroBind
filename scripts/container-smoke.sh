#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T frontend wget -qO- http://127.0.0.1:8080/api/health
docker compose exec -T api python - <<'PY'
import json,os,time,urllib.request
from pathlib import Path
token=Path('/run/secrets/api_token').read_text().strip()
def request(path,body=None):
    r=urllib.request.Request('http://127.0.0.1:8000/api'+path,
       data=json.dumps(body).encode() if body is not None else None,
       headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with urllib.request.urlopen(r,timeout=20) as f:return json.load(f)
kind='verify' if os.getenv('MICROBIND_VERIFY_ENABLED')=='1' else 'scan'
job=request('/jobs',{'project_id':'demo','kind':kind,'repair':True,'smart':False})
start=time.monotonic()
while time.monotonic()-start < 1800:
    job=request('/jobs/'+job['id'])
    if job['status'] not in ('queued','running'):break
    time.sleep(2)
assert job['status']=='succeeded',job
r=request('/jobs/'+job['id']+'/result')
assert r['before']['summary']['suspected']==8
assert r['after']['summary'].get('suspected',0)==0
assert r['repair']['applied']['patch_count']==8
if kind=='verify':
    assert r['verification']['passed']
    assert r['verification']['after']['summary']['unauthorized_effects_observed']==0
assert r['smart']['status']=='disabled'
assert all(e['status']=='succeeded' for e in r['skill_events'])
assert len(request('/skills'))==5
for sample in ['sample-neo-http','sample-neo-role','sample-litemall']:
    j=request('/jobs',{'project_id':sample,'repair':False,'smart':False})
    start=time.monotonic()
    while time.monotonic()-start < 120:
        j=request('/jobs/'+j['id'])
        if j['status'] not in ('queued','running'):break
        time.sleep(1)
    assert j['status']=='succeeded',j
    result=request('/jobs/'+j['id']+'/result')
    assert result['smart']['status']=='disabled'
    if sample=='sample-neo-http':assert result['before']['summary']['rpc_edges']==5
    if sample=='sample-neo-role':assert result['before']['assessment']['status']=='no_operation_evidence'
    if sample=='sample-litemall':assert result['before']['summary']['needs_review']==7
print(json.dumps({'job_id':job['id'],'kind':kind,'passed':True,'patches':8,'upstream_samples_checked':3}))
PY
