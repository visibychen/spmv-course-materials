#!/usr/bin/env python3
"""Verify frozen inputs, source/binaries, raw timings and pairing coverage."""
import ast,csv,hashlib,json,re,subprocess
from collections import Counter,defaultdict
from pathlib import Path
import run_experiments as r
H=r.HERE
def main():
 records=r.records();assert len(records)==1835,len(records)
 expected={'critical':480,'screen':375,'heldout':600,'large':80,'large-sensitivity':60,'ablations':240}
 assert dict(Counter(x['phase'] for x in records))==expected
 keys=[tuple(x[k] for k in r.FIELDS[:6]) for x in records];assert len(keys)==len(set(keys))
 frozen=json.loads((H/'frozen-harness.json').read_text())['sha256']
 for name,digest in frozen.items():assert r.sha(H/name)==digest,name
 source=json.loads((H/'source-provenance.json').read_text())
 archive=H/'build/v21'
 for path,digest in source['source_sha256'].items():assert r.sha(archive/path)==digest,path
 for name,info in json.loads((H/'build.json').read_text()).items():assert r.sha(H/'build'/name/'csrspmv')==info['binary_sha256'],name
 for meta in r.matrices():
  assert r.sha(meta['path'])==meta['sha256'],meta['name']
  if 'expected_path' in meta:assert r.sha(meta['expected_path'])==meta['expected_sha256'],meta['name']
 pairs=defaultdict(list)
 for rec in records:
  path=H/rec['command_file'];cmd=json.loads(path.read_text());tag=path.name.removesuffix('.command.json')
  text=(path.parent/(tag+'.stdout.txt')).read_text();resource=json.loads((path.parent/(tag+'.resource.json')).read_text())
  exe=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',text)
  assert exe and int(exe[2])==int(rec['repeat']) and float(exe[1])==float(rec['execute_s'])
  total=sum(float(rec[k]) for k in ['execute_s','prepare_s','cleanup_s']);assert abs(total-float(rec['total_s']))<1e-12
  assert resource['max_rss_kib']==int(rec['max_rss_kib'])
  assert cmd['environment']=={k:v for k,v in r.env(int(rec['threads'])).items() if k.startswith('OMP_')}
  if rec['variant']=='v21':assert rec['profile_match']=='1'
  if rec['pair']:pairs[rec['pair']].append(rec)
 for pid,group in pairs.items():
  assert len(group)==2 and {x['order'] for x in group}=={'0','1'} and sum(x['variant']=='v21' for x in group)==1,pid
 assert len(pairs)==280
 # All original and v2 source histories remain exact, v2.1 is a direct child.
 git=lambda *args:subprocess.check_output(['git','-C',str(r.CORE),*args],text=True).strip()
 assert git('rev-parse',r.COMMITS['v21']+'^')==r.COMMITS['v2']
 assert git('rev-parse','master')==r.COMMITS['original']
 assert git('rev-parse','optimization/v2')==r.COMMITS['v2']
 assert git('rev-parse','origin/optimization/v2.1')==r.COMMITS['v21']
 assert not git('status','--porcelain')
 # Earlier experiment data must not have been rewritten.
 dirty=subprocess.check_output(['git','-C',str(r.MATERIALS),'diff','--name-only','-z'],text=True).split('\0')
 assert all(not x.startswith(('experiments/2026-10-26-v2/','experiments/2026-10-25')) for x in dirty)
 for f in H.glob('*.py'):ast.parse(f.read_text())
 for f in H.glob('*.json'):json.loads(f.read_text())
 links=0
 for f in H.glob('*.md'):
  for target in re.findall(r'\]\(([^)]+)\)',f.read_text()):
   if re.match('[a-zA-Z]+:',target):continue
   assert (f.parent/target.split('#')[0]).exists(),(f.name,target);links+=1
 result={'status':'passed','formal_processes':len(records),'phase_counts':expected,'unique_measurement_keys':len(keys),
  'adjacent_process_pairs':len(pairs),'inputs_hashed':len(r.matrices()),'raw_stdout_and_total_time_verified':True,
  'frozen_harness_matches':True,'archive_sources_and_binary_hashes_match':True,'source_pushed_before_formal':True,
  'git_parent_is_v2':True,'master_v2_unchanged':True,'core_worktree_clean':True,'earlier_experiments_unchanged':True,
  'relative_links_checked':links,'actual_checked_out_branch':git('branch','--show-current'),
  'limits':['no DRAM bandwidth/host frequency control','calibration and within-process diagnostics are not independent formal repetitions','FP regrouping uses error bounds, not universal bitwise equality']}
 r.save('audit.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
