#!/usr/bin/env python3
"""90 disjoint CLI observations before commit; no production profile fit.
Archived commands used the then-parallel default; final-source replay makes it explicit."""
import hashlib,json,random,re,subprocess
import numpy as np
from run_checks import H,C,env,save,sha
SHAPES=[(150013,4000003,8,'iid'),(80021,2000003,15,'iid'),(5003,10007,8,'iid'),
 (630013,1000003,8,'period'),(300007,2000003,8,'cluster'),(19001,1000003,1,'two')]
def main():
 rng=np.random.default_rng(2026103001);records=[];inputs=[];order=random.Random(2026103002)
 for case,(m,n,L,kind) in enumerate(SHAPES):
  counts=np.full(m,L,dtype=np.int64)
  if kind=='period':counts[(np.arange(m)+13)%97!=0]=0
  if kind=='cluster':counts[m*3//100:]=0
  if kind=='two':counts[3]=150007;counts[m//2]=130003
  path=H/f'data/cal-{case}.mtx'
  with path.open('w') as f:
   f.write(f'%%MatrixMarket matrix coordinate real general\n{m} {n} {int(counts.sum())}\n')
   for row,count in enumerate(counts):
    if not count:continue
    cols=rng.choice(n,size=int(count),replace=False)
    f.writelines(f'{row+1} {int(col)+1} 0.25\n' for col in cols)
  inputs.append(dict(case=case,rows=m,columns=n,length=L,kind=kind,path=str(path),sha256=sha(path)))
  for t in [12,24]:
   for sample in range(3):
    variants=[('v22',['--kernel=v2.2']),('v221',['--kernel=v2.2.1','--v221-validation=parallel'])]
    if case in [0,1]:variants.append(('v221-serial',['--kernel=v2.2.1','--v221-validation=serial']))
    if case==4:variants.append(('v221-rows',['--kernel=v2.2.1','--v221-validation=parallel','--v221-balance=rows']))
    order.shuffle(variants)
    for name,opts in variants:
     cmd=[str(C/'csrspmv'),str(path),*opts,'--repeat=9','--matrix-format=f32','--source-vector-format=f32','--destination-vector-format=f32','-v']
     p=subprocess.run(cmd,env=env(t),capture_output=True,text=True,check=True)
     prep=float(re.search(r'spmv_prepare: ([\d.]+)',p.stdout)[1]);exe=float(re.search(r'csr_matrix_int32_spmv: ([\d.]+)',p.stdout)[1]);cleanup=float(re.search(r'spmv_cleanup: ([\d.]+)',p.stdout)[1])
     records.append(dict(case=case,variant=name,threads=t,repeat=9,sample=sample,prepare_s=prep,execute_s=exe,total_s=prep+exe+cleanup,command=cmd,stdout=p.stdout))
  print('CALIBRATED',case,kind,flush=True)
 assert len(records)==90
 save('calibration.json',dict(seed=2026103001,scope='before source commit; separate from all formal inputs; same-binary policy observations',binary_sha256=sha(C/'csrspmv'),rules_changed=False,inputs=inputs,records=records))
if __name__=='__main__':main()
