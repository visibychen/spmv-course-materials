#!/usr/bin/env python3
import collections,json,time
import common as c
import run_experiments as r
H=c.H
assert not (H/'measurements.csv').exists()
jobs=r.schedule();keys=[(j['phase'],j['n'],j['v'],j['t'],j['R'],j['s']) for j in jobs];assert len(keys)==len(set(keys))
for i,j in enumerate(jobs):
 if j['block']:assert (i>0 and jobs[i-1]['block']==j['block']) or (i+1<len(jobs) and jobs[i+1]['block']==j['block'])
assert len(r.matrices())==104
assert len(json.loads((H/'correctness.json').read_text()))==464
assert len(json.loads((H/'verification-builds.json').read_text()))==8
assert json.loads((H/'fixed-build-proof.json').read_text())['equal_loadable_computation_sections']
p=dict(date='2026-10-31',design_commit='b67c63744afcabe09412e6364e5b4c18837829f7',code_commit='e83160bf4da3b20f154f81dfbe43fad532764145',parent=c.COMMITS['original'],best=c.COMMITS['v2'],code_pushed_before_formal=True,metrics='P+R real calls E+D, fixture loading excluded identically for all; wall recorded; fixture I/O not v3 gain',main_driver='same executable and CSR loader, one selected backend per process',fixture_mode='standard CSR snapshot from fixed original converter; source and fixture SHA retained',primary_blocks=20,aa_pairs=12,mechanism_pairs=10,cli_blocks=5,cross12_pairs=10,seed=2026103151,bootstrap_seed=2026103153,bootstrap_draws=20000,input_count=104,formal_processes=len(jobs),phase_counts=dict(collections.Counter(x['phase'] for x in jobs)),unit_configurations=8,correctness_records=464,type_compatibility_records=10,acceptance='research/2026-10-31-spmv-v3/验证计划.md and frozen analyze_results.py',cross12_note='Predeclared extra matched control if best measured original team is12; otherwise do not extrapolate.',no_retuning_after_formal=True,jobs=jobs)
c.save('protocol.json',p)
files=list(H.glob('*.py'))+list(H.glob('*.c'))+[H/n for n in ['protocol.json','matrices.json','bench-build.json','fixed-build-proof.json','source-provenance.json']]
binaries={'benchmark':c.sha(H/'build/bench'),**{v:c.sha(H/'build'/v/'csrspmv') for v in ['original','v2','v3']}}
c.save('frozen-harness.json',dict(unix_time=time.time(),files={p.name:c.sha(p) for p in files},binaries=binaries))
print(json.dumps(dict(formal_processes=len(jobs),phase_counts=p['phase_counts'],blocks=len({x['block'] for x in jobs if x['block']})),indent=2))
