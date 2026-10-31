#!/usr/bin/env python3
import collections,json,subprocess,time
from pathlib import Path
import run_experiments as r
H=r.HERE
assert not (H/'measurements.csv').exists(), 'Do not overwrite frozen archive'
jobs=r.schedule();counts=dict(collections.Counter(j['phase'] for j in jobs))
keys=[(j['phase'],j['n'],j['v'],j['t'],j['R'],j['s']) for j in jobs];assert len(keys)==len(set(keys))
for i,j in enumerate(jobs):
 if j['pair']:
  assert (i>0 and jobs[i-1]['pair']==j['pair']) or (i+1<len(jobs) and jobs[i+1]['pair']==j['pair'])
assert len(r.matrices())==92
assert len(json.loads((H/'verification-builds.json').read_text()))==21
correct=json.loads((H/'correctness.json').read_text());assert len({x['matrix'] for x in correct if 'matrix' in x})==92
source={}
for name,info in json.loads((H/'build.json').read_text()).items():
 dest=H/'build'/name
 source[name]=dict(commit=info['commit'],binary_sha256=r.sha(dest/'csrspmv'),sources={str(p.relative_to(dest)):r.sha(p) for p in sorted((dest/'src').glob('*.[ch]'))})
r.save('source-provenance.json',source)
protocol=dict(date='2026-10-31',design_commit='77bbb9c26b25679be1b0495bc83b6c221a7e1e6b',core_commit=r.COMMITS['v222'],parent=r.COMMITS['v22'],core_pushed_before_formal=True,commits=r.COMMITS,formal_counts=counts,formal_processes=len(jobs),pairs=sum(bool(j['pair']) for j in jobs)//2,inputs=92,metric='per-process prepare + R execute + cleanup; wall separate',ratio='paired candidate/control, median with 20000 bootstrap percentile 95% CI per condition',seed=2026103107,wait_policy='PASSIVE except separately labelled waiting phase ACTIVE',new_targets=r.TARGETS,aa='12 adjacent pairs of identical v2 executable and options, aliases only',timing_precision='E retains upstream 6 decimal seconds; P/D 9; resource wall 0.01s',acceptance_source='research/2026-10-31-spmv-v2.2.2/验证计划.md',no_retuning_after_formal=True,jobs=jobs)
r.save('protocol.json',protocol)
files=list(H.glob('*.py'))+list(H.glob('*.c'))+[H/n for n in ['protocol.json','matrices.json','build.json','source-provenance.json']]
r.save('frozen-harness.json',dict(unix_time=time.time(),files={p.name:r.sha(p) for p in files},binaries={n:info['binary_sha256'] for n,info in json.loads((H/'build.json').read_text()).items()}))
print(json.dumps(dict(formal_processes=len(jobs),pairs=protocol['pairs'],phase_counts=counts),indent=2))
