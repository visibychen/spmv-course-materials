#!/usr/bin/env python3
"""Audit archived commands, output-derived timings, matrices, pairs and hashes."""
import collections,hashlib,json,subprocess,re
import run_experiments as r
H=r.HERE
def main():
 rows=r.records();protocol=json.loads((H/'protocol.json').read_text());expected=protocol['formal_counts']
 counts=dict(collections.Counter(x['phase'] for x in rows));assert counts==expected,(counts,expected)
 keys=[tuple(x[k] for k in r.FIELDS[:6]) for x in rows];assert len(set(keys))==len(rows)
 blocks=collections.defaultdict(list)
 for row_index,x in enumerate(rows):
  assert abs(float(x['total_s'])-sum(float(x[k]) for k in ['prepare_s','execute_s','cleanup_s']))<1e-12
  cmdpath=H/x['command_file'];cmd=json.loads(cmdpath.read_text());tag=cmdpath.name.removesuffix('.command.json')
  stdout=(cmdpath.parent/f'{tag}.stdout.txt').read_text();stderr=(cmdpath.parent/f'{tag}.stderr.txt').read_text()
  resource=json.loads((cmdpath.parent/f'{tag}.resource.json').read_text())
  assert cmd['argv'][5:]==r.command(x['variant'],x['matrix'],int(x['repeat']))
  e=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',stdout);assert e
  assert float(e[1])==float(x['execute_s']) and int(e[2])==int(x['repeat'])
  meta=r.matrix(x['matrix']);nnz=meta.get('expanded_nonzeros_verified',meta['nonzeros'])
  assert int(e[3])==2*nnz*int(x['repeat'])
  assert cmd['environment']=={k:v for k,v in r.env(int(x['threads'])).items() if k.startswith('OMP_')}
  for k,v in resource.items():assert float(x[k])==v
  assert 1<=int(x['actual_threads'])<=int(x['threads'])
  if x['pair']:blocks[x['pair']].append((row_index,x))
 assert len(blocks)==820
 for pair,indexed in blocks.items():
  assert len(indexed)==2 and indexed[1][0]==indexed[0][0]+1
  rs=[v for i,v in indexed]
  assert len(rs)==2 and sorted(x['order'] for x in rs)==['0','1']
  assert sum(x['variant']=='v221' for x in rs)==1
 for item in json.loads((H/'matrices.json').read_text()):
  assert r.sha(item['path'])==item['sha256']
  if 'expected_path' in item:assert r.sha(item['expected_path'])==item['expected_sha256']
 for key,item in json.loads((H/'build.json').read_text()).items():assert r.sha(H/'build'/key/'csrspmv')==item['binary_sha256']
 frozen=json.loads((H/'frozen-harness.json').read_text())
 for name,digest in frozen['files'].items():assert r.sha(H/name)==digest,name
 correct=json.loads((H/'correctness.json').read_text());assert len(correct)==489
 assert len([x for x in correct if x.get('kind')=='compatibility'])==10
 assert {x['matrix'] for x in correct if x.get('variant')=='v221'}=={m['name'] for m in r.matrices()}
 checks=json.loads((H/'verification-builds.json').read_text());assert len(checks)==21
 for x in checks:
  assert ('PASS v2.2.1: 1032' if x['test']=='v221' else 'PASS v2.2: 1007' if x['test']=='v22' else 'PASS v2: 5368') in x['stdout']
  assert r.sha(x['command'][-1])==x['sha256']
 diag=json.loads((H/'diagnostic.json').read_text());assert len(diag)==8
 assert all(len([r for r in d['records'] if r['type']=='sample'])==128 for d in diag)
 decision=json.loads((H/'decision.json').read_text())
 branch=subprocess.check_output(['git','branch','--show-current'],cwd=r.CORE,text=True).strip()
 assert branch==('optimization/v2.2.1' if decision['accepted_as_robust_upgrade'] else 'optimization/v2')
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=r.CORE,text=True).strip()
 for ref,commit in [('master',r.COMMITS['original']),('optimization/v2',r.COMMITS['v2']),('optimization/v2.2',r.COMMITS['v22']),('optimization/v2.2^',r.COMMITS['v2']),('optimization/v2.2.1',r.COMMITS['v221']),('optimization/v2.2.1^',r.COMMITS['v22'])]:
  assert subprocess.check_output(['git','rev-parse',ref],cwd=r.CORE,text=True).strip()==commit
 journal=(r.MATERIALS/'项目日志.md').read_bytes();log=json.loads((H/'project-log-update.json').read_text())
 prefix=subprocess.check_output(['git','show','f6e247a:项目日志.md'],cwd=r.MATERIALS)
 assert journal[:len(prefix)]==prefix and hashlib.sha256(prefix).hexdigest()==log['prefix_sha256']
 assert len(journal)-len(prefix)==log['appended_bytes'] and r.sha(r.MATERIALS/'项目日志.md')==log['final_sha256']
 assert all(x['selected']=='empty-runs' and x['index_retry']=='1' for x in rows if x['phase']=='critical' and x['matrix'] in r.MISSES and x['variant']=='v221')
 result=dict(formal_processes=len(rows),phase_counts=counts,unique_keys=True,paired_blocks=len(blocks),
  inputs=80,full_vector_and_compatibility_checks=len(correct),frozen_harness_unchanged=True,
  source_binaries_unchanged=True,resources_and_timings_match_raw=True,core_checkout=branch,core_clean=True,
  limitations='SHA verifies local bytes; timings remain conditional on the recorded machine/load, not a reproducibility guarantee.')
 r.save('audit.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
