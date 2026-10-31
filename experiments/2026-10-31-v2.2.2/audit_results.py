#!/usr/bin/env python3
"""Verify archived bytes, complete schedule, raw timings, environments and refs."""
import collections,hashlib,json,re,subprocess
import run_experiments as r
H=r.HERE

def audit():
 p=json.loads((H/'protocol.json').read_text());f=json.loads((H/'frozen-harness.json').read_text());rows=r.records()
 for name,digest in f['files'].items():assert r.sha(H/name)==digest,('frozen file changed',name)
 for name,digest in f['binaries'].items():assert r.sha(H/'build'/name/'csrspmv')==digest,('binary changed',name)
 def key(x):return tuple(str(x[k]) for k in ['phase','matrix','variant','threads','repeat','sample'])
 planned=[dict(phase=j['phase'],matrix=j['n'],variant=j['v'],threads=j['t'],repeat=j['R'],sample=j['s']) for j in p['jobs']]
 assert [key(x) for x in rows]==[key(x) for x in planned]
 assert len({key(x) for x in rows})==len(rows)==p['formal_processes']
 pairs=collections.defaultdict(list)
 for x in rows:
  tag=x['command_file'].removeprefix('raw/').removesuffix('.command.json')
  out=(H/f'raw/{tag}.stdout.txt').read_text();resource=json.loads((H/f'raw/{tag}.resource.json').read_text());cmd=json.loads((H/x['command_file']).read_text())
  e=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',out);assert e
  assert float(e[1])==float(x['execute_s']) and int(e[2])==int(x['repeat'])
  m=r.matrix(x['matrix']);nnz=m.get('expanded_nonzeros_verified',m['nonzeros']);assert int(e[3])==2*nnz*int(x['repeat'])
  prep=re.search(r'spmv_prepare: ([\d.]+)',out);cleanup=re.search(r'spmv_cleanup: ([\d.]+)',out)
  assert float(x['prepare_s'])==(float(prep[1]) if prep else 0)
  assert float(x['cleanup_s'])==(float(cleanup[1]) if cleanup else 0)
  assert abs(float(x['total_s'])-sum(float(x[k]) for k in ['prepare_s','execute_s','cleanup_s']))<1e-12
  for k in ['wall_s','max_rss_kib','major_faults']:assert float(x[k])==resource[k]
  assert cmd['environment']['OMP_WAIT_POLICY']==('ACTIVE' if x['phase']=='waiting' else 'PASSIVE')
  if x['pair']:pairs[x['pair']].append(x)
 for pid,g in pairs.items():
  assert len(g)==2 and [x['order'] for x in g]==['0','1']
  if g[0]['phase']=='aa':
   commands=[json.loads((H/x['command_file']).read_text()) for x in g]
   assert commands[0]['argv'][5:]==commands[1]['argv'][5:] and commands[0]['environment']==commands[1]['environment']
 for m in r.matrices():assert r.sha(m['path'])==m['sha256']
 source=json.loads((H/'source-provenance.json').read_text());proof={}
 for name,info in source.items():
  for path,digest in info['sources'].items():
   data=subprocess.check_output(['git','show',info['commit']+':'+path],cwd=r.CORE)
   assert hashlib.sha256(data).hexdigest()==digest
 for path in ['src/csr.c','src/spmv_v2.c','src/spmv_v22.c','tests/test_spmv_v2.c','tests/test_spmv_v22.c']:
  a=subprocess.check_output(['git','show',p['parent']+':'+path],cwd=r.CORE)
  b=subprocess.check_output(['git','show',p['core_commit']+':'+path],cwd=r.CORE)
  assert a==b;proof[path]=hashlib.sha256(a).hexdigest()
 r.save('executor-source-proof.json',dict(unchanged=proof,limit='Same source is not identical object bytes: sizeof(plan), relocation and final link layout can differ.'))
 core_branch=subprocess.check_output(['git','branch','--show-current'],cwd=r.CORE,text=True).strip()
 core_clean=not subprocess.check_output(['git','status','--porcelain'],cwd=r.CORE,text=True).strip();assert core_clean
 result=dict(formal_processes=len(rows),phase_counts=dict(collections.Counter(x['phase'] for x in rows)),paired_blocks=len(pairs),inputs=len(r.matrices()),full_vector_and_compatibility_checks=len(json.loads((H/'correctness.json').read_text())),unit_configurations=len(json.loads((H/'verification-builds.json').read_text())),unique_keys=True,frozen_harness_unchanged=True,source_binaries_unchanged=True,resources_and_timings_match_raw=True,aa_commands_identical=True,all_input_hashes_match=True,core_checkout=core_branch,core_clean=core_clean,max_rss_kib=max(int(x['max_rss_kib']) for x in rows),max_major_faults=max(int(x['major_faults']) for x in rows))
 r.save('audit.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':audit()
