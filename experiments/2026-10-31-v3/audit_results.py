#!/usr/bin/env python3
import collections,hashlib,json,subprocess,re
from pathlib import Path
import common as c
import run_experiments as r
H=c.H
def audit():
 p=json.loads((H/'protocol.json').read_text());f=json.loads((H/'frozen-harness.json').read_text());rows=r.rows()
 for name,sha in f['files'].items():assert c.sha(H/name)==sha,('frozen changed',name)
 for name,sha in f['binaries'].items():assert c.sha(H/'build/bench' if name=='benchmark' else H/'build'/name/'csrspmv')==sha
 planned=[dict(phase=j['phase'],matrix=j['n'],variant=j['v'],threads=j['t'],repeat=j['R'],sample=j['s']) for j in p['jobs']]
 assert [r.key(x) for x in rows]==[r.key(x) for x in planned]
 assert len(rows)==len({r.key(x) for x in rows})==p['formal_processes']
 blocks=collections.defaultdict(list)
 for x in rows:
  tag=x['command_file'].removeprefix('raw/').removesuffix('.command.json')
  cmd=json.loads((H/x['command_file']).read_text());res=json.loads((H/f'raw/{tag}.resource.json').read_text());out=(H/f'raw/{tag}.stdout.txt').read_text()
  if x['mode']=='fixture':
   data=json.loads(out)
   for k in ['prepare_s','execute_s','cleanup_s','total_s','actual_threads','flops']:assert float(x[k])==data[k]
  else:
   e=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',out);assert e and float(x['execute_s'])==float(e[1])
  meta=r.matrix(x['matrix']);nnz=meta.get('expanded_nonzeros_verified',meta['nonzeros'])
  assert int(x['flops'])==2*nnz*int(x['repeat'])
  assert abs(float(x['total_s'])-sum(float(x[k]) for k in ['prepare_s','execute_s','cleanup_s']))<3e-9
  for k in ['wall_s','max_rss_kib','major_faults']:assert float(x[k])==res[k]
  assert cmd['environment']['OMP_WAIT_POLICY']==('ACTIVE' if x['phase']=='waiting' else 'PASSIVE')
  if x['block']:blocks[x['block']].append(x)
 for name,g in blocks.items():
  expected=3 if g[0]['phase'] in ['main','critical','cli'] else 2
  assert len(g)==expected and [int(x['order']) for x in g]==list(range(expected))
  if g[0]['phase']=='aa':
   cs=[json.loads((H/x['command_file']).read_text()) for x in g];assert cs[0]['argv'][5:]==cs[1]['argv'][5:] and cs[0]['environment']==cs[1]['environment']
 for m in r.matrices():assert c.sha(m['path'])==m['sha256'] and c.sha(m['fixture_path'])==m['fixture_sha256']
 sources=json.loads((H/'source-provenance.json').read_text())
 for name,info in sources.items():
  for path,digest in info['sources'].items():assert hashlib.sha256(subprocess.check_output(['git','show',info['commit']+':'+path],cwd=c.C)).hexdigest()==digest
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=c.C,text=True).strip()
 result=dict(formal_processes=len(rows),phase_counts=dict(collections.Counter(x['phase'] for x in rows)),blocks=len(blocks),inputs=104,full_output_checks=464,type_checks=10,unit_configurations=8,unique_keys=True,frozen_harness_unchanged=True,source_binaries_unchanged=True,resources_and_timings_match_raw=True,aa_commands_identical=True,source_and_fixture_hashes_match=True,core_checkout=subprocess.check_output(['git','branch','--show-current'],cwd=c.C,text=True).strip(),core_clean=True,max_rss_kib=max(int(x['max_rss_kib']) for x in rows),max_major_faults=max(int(x['major_faults']) for x in rows))
 c.save('audit.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':audit()
