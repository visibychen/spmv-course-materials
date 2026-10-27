#!/usr/bin/env python3
"""Post-timing provenance and conditional checkout; never rewrites history."""
import json,re,subprocess
import run_experiments as r
H=r.HERE
def git(*args,cwd=None):return subprocess.check_output(['git',*args],cwd=cwd or r.CORE,text=True).strip()
def proof():
 evidence={};sources={}
 for name,digest in json.loads((H/'source-provenance.json').read_text())['source_sha256'].items():
  assert r.sha(H/'build/v22'/name)==digest,name
 for name in ['original','v2','v22']:
  folder=H/'build'/name;target=H/'build'/f'csr-text-{name}.bin'
  cmd=['objcopy','--dump-section','.text='+str(target),str(folder/'src/csr.o')]
  subprocess.run(cmd,check=True,capture_output=True)
  evidence[name]=dict(csr_source_sha256=r.sha(folder/'src/csr.c'),csr_text_sha256=r.sha(target),csr_text_bytes=target.stat().st_size,command=cmd)
  if name!='original':sources[name]=r.sha(folder/'src/spmv_v2.c')
 assert len({v['csr_source_sha256'] for v in evidence.values()})==1
 assert len({v['csr_text_sha256'] for v in evidence.values()})==1
 assert sources['v2']==sources['v22']
 r.save('csr-object-proof.json',dict(versions=evidence,v2_source_sha256=sources,
  interpretation='csr.c and spmv_v2.c unchanged. csr.o .text identical before relocation; this does not prove equal final addresses, relocations, cache states or timings.'))
 command=['objdump','-d','-M','intel','--disassemble=csr_matrix_int32_spmv',str(H/'build/original/csrspmv')]
 (H/'raw/assembly-original-csr.txt').write_text(subprocess.check_output(command,text=True))
 r.save('assembly-index.json',{p.name:dict(bytes=p.stat().st_size,sha256=r.sha(p),has_instructions=bool(re.search(r'^\s+[0-9a-f]+:',p.read_text(),re.M))) for p in (H/'raw').glob('assembly-*')})
 # Preserve calibration input identity without shipping the generated matrices.
 cal=json.loads((H/'calibration.json').read_text());paths=sorted({x['command'][1] for x in cal['records']})
 r.save('calibration-inputs.json',[dict(path=p,sha256=r.sha(p)) for p in paths])
 print('Proved source/text identity; saved calibration input hashes')
def checkout():
 d=json.loads((H/'decision.json').read_text());assert not git('status','--porcelain')
 before=git('branch','--show-current');assert before=='optimization/v2.2'
 if not d['accepted_as_robust_upgrade']:
  generated=r.CORE/'tests/test_spmv_v22'
  if generated.exists():
   assert generated.resolve().parent==(r.CORE/'tests').resolve()
   assert generated.open('rb').read(4)==b'\x7fELF'
   generated.unlink()
  subprocess.run(['git','switch','optimization/v2'],cwd=r.CORE,check=True)
  subprocess.run(['make','clean'],cwd=r.CORE,check=True,capture_output=True)
  p=subprocess.run(['make','-j12','CFLAGS='+r.FLAGS],cwd=r.CORE,capture_output=True,text=True)
  (H/'raw/restore-v2-build.txt').write_text(p.stdout+p.stderr);p.check_returncode()
  m=r.matrix('wide');cmd=[str(r.CORE/'csrspmv'),m['path'],'--kernel=v2','--repeat=1','-v']
  p=subprocess.run(cmd,env=r.env(12),capture_output=True,text=True,check=True)
  (H/'raw/restore-v2-smoke.txt').write_text(p.stdout+p.stderr)
 assert not git('status','--porcelain')
 r.save('git-provenance.json',dict(core_commit=r.COMMITS['v22'],core_parent=git('rev-parse',r.COMMITS['v22']+'^'),
  core_branch='optimization/v2.2',core_remote_tracking=git('rev-parse','origin/optimization/v2.2'),
  core_before_checkout=before,core_final_checkout=git('branch','--show-current'),core_final_head=git('rev-parse','HEAD'),core_clean=True,
  master=git('rev-parse','master'),v2=git('rev-parse','optimization/v2'),
  materials_branch=git('branch','--show-current',cwd=r.MATERIALS),materials_parent=git('rev-parse','HEAD',cwd=r.MATERIALS),
  design_commit='645b2928f2bd009452f88ef72b5180894e0d8e14',
  result_commit_title='2026.10.27v2.2实验记录',result_commit='See enclosing Git commit; no self-reference',
  no_history_rewrite=True,no_master_merge=True))
 print('Checkout decision applied:',git('branch','--show-current'))
if __name__=='__main__':
 import sys
 {'proof':proof,'checkout':checkout}[sys.argv[1]]()
