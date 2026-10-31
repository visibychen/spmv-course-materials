#!/usr/bin/env python3
import json,subprocess,time
from pathlib import Path
import numpy as np
import common as c
H=c.H
SHAPES=[('v3-u8-small',100019,1000003,8,'iid'),('v3-u8-wide',600013,6000011,8,'iid'),
 ('v3-ragged78',170003,1400003,8,'ragged78'),('v3-ragged89',180001,1800007,8,'ragged89'),
 ('v3-short2',400009,1600013,2,'iid'),('v3-short4',300007,1700021,4,'iid'),('v3-short16',140009,1900003,16,'iid'),
 ('v3-tail7',131079,2000003,8,'iid'),('v3-local-mix',200003,2100011,8,'mixed'),
 ('v3-rectangle',65543,4000009,8,'iid'),('v3-empty99',200009,1200011,8,'empty99'),('v3-zero',530009,17,0,'iid')]
def synthetic(name,m,n,L,kind):
 seed=2026103149+sum((i+1)*ord(ch) for i,ch in enumerate(name));rng=np.random.default_rng(seed);counts=np.full(m,L,dtype=np.int64)
 if kind=='ragged78':counts=7+np.arange(m)%2
 if kind=='ragged89':counts=8+np.arange(m)%2
 if kind=='mixed':counts[np.arange(m)%64==0]=0;counts[np.arange(m)%64==1]=1;counts[np.arange(m)%64==2]=9
 if kind=='empty99':counts[np.arange(m)%100!=0]=0
 path=H/f'data/{name}.mtx';expected=H/f'data/{name}.expected.f32';sums=np.zeros(m,dtype=np.float32)
 with path.open('w') as f:
  f.write(f'%%MatrixMarket matrix coordinate real general\n% v3 holdout seed {seed}\n{m} {n} {int(counts.sum())}\n')
  for row,length in enumerate(counts):
   L=int(length)
   if not L:continue
   columns=rng.integers(0,n,size=L);values=rng.integers(1,5,size=L).astype(np.float32)*np.float32(.25)
   sums[row]=values.sum(dtype=np.float32)
   f.writelines(f'{row+1} {int(j)+1} {float(v):.2f}\n' for j,v in zip(columns,values))
 sums.tofile(expected)
 return dict(name=name,rows=m,columns=n,nonzeros=int(counts.sum()),path=str(path),expected_path=str(expected),group='new-heldout',profile=kind,seed=seed,sha256=c.sha(path),expected_sha256=c.sha(expected),license='project generated; GPL-3.0-or-later')
def create():
 metas=[]
 for m in json.loads((c.M/'experiments/2026-10-31-v2.2.2/matrices.json').read_text()):
  assert c.sha(m['path'])==m['sha256'];m['prior_group']=m['group'];m['group']='development';metas.append(m)
 for shape in SHAPES:metas.append(synthetic(*shape));print('GENERATED',shape[0],flush=True)
 for m in metas:
  out=H/f'data/{m["name"]}.csr';cmd=[str(H/'build/bench'),'export',m['path'],str(out),str(int(m.get('expand_symmetric',False)))]
  start=time.monotonic();p=subprocess.run(cmd,env=c.env(12),capture_output=True,text=True,timeout=600);p.check_returncode()
  m['fixture_path']=str(out);m['fixture_sha256']=c.sha(out);m['fixture_build_wall_s']=time.monotonic()-start;m['fixture_command']=cmd
  print('FIXTURE',m['name'],flush=True)
 c.save('matrices.json',metas)
def reference(m,R):
 if 'expected_path' in m:return np.fromfile(m['expected_path'],dtype=np.float32)*np.float32(R),None
 vals=np.loadtxt(m['path'],comments='%',skiprows=len(m['matrix_header']),ndmin=2)
 i=vals[:,0].astype(np.int64)-1;j=vals[:,1].astype(np.int64)-1;v=vals[:,2].astype(np.float32).astype(np.float64)
 sums=np.bincount(i,weights=v,minlength=m['rows']);ab=np.bincount(i,weights=np.abs(v),minlength=m['rows']);counts=np.bincount(i,minlength=m['rows'])
 if m.get('expand_symmetric'):
  off=i!=j;sums+=np.bincount(j[off],weights=v[off],minlength=m['rows']);ab+=np.bincount(j[off],weights=np.abs(v[off]),minlength=m['rows']);counts+=np.bincount(j[off],minlength=m['rows'])
 m['expanded_nonzeros_verified']=int(counts.sum())
 return sums*R,(counts+32)*np.finfo(np.float32).eps*ab*max(R,1)*16+1e-30
def text_vector(path):
 with Path(path).open() as f:
  for line in f:
   if not line.startswith('%'):m=int(line.split()[0]);break
  a=np.loadtxt(f,dtype=np.float32,ndmin=1)
 assert a.size==m;return a
def verify():
 metas=json.loads((H/'matrices.json').read_text());records=[]
 for m in metas:
  ref,bound=reference(m,3);lim=0 if bound is None else bound
  variants=['original','v2','v3']+(['v3-tile','v3-pipeline','v3-csr','v3-nosimd'] if m['group']=='new-heldout' else [])
  for v in variants:
   out=H/'data/verify.bin';cmd=[str(H/'build/bench'),'run',m['fixture_path'],str(c.VARIANTS[v]),'3',str(out)]
   p=subprocess.run(cmd,env=c.env(12),capture_output=True,text=True,timeout=600);p.check_returncode();got=np.fromfile(out,dtype=np.float32);error=np.abs(got.astype(np.float64)-ref)
   assert got.shape==ref.shape and np.all(error<=lim),(m['name'],v,float(error.max()))
   records.append(dict(matrix=m['name'],variant=v,kind='fixture',repeat=3,values=int(got.size),max_absolute_error=float(error.max(initial=0)),output_sha256=c.sha(out),command=cmd))
   (H/f'raw/correct-{m["name"]}-{v}.txt').write_text(p.stdout+p.stderr)
   if v=='v3':fixture_output=got.copy()
  out=H/'data/verify-cli.mtx';cmd=[str(c.C/'csrspmv'),m['path'],'--kernel=v3','--matrix-format=f32','--source-vector-format=f32','--destination-vector-format=f32','--repeat=3','--destination-vector='+str(out),'--destination-vector-prec=50','-v']
  if m.get('expand_symmetric'):cmd+=['--include-symmetric-part']
  p=subprocess.run(cmd,env=c.env(12),capture_output=True,text=True,timeout=600);p.check_returncode();got=text_vector(out);error=np.abs(got.astype(np.float64)-ref);diff=np.abs(got.astype(np.float64)-fixture_output)
  assert got.shape==ref.shape and np.all(error<=lim) and np.all(diff<=2*lim),(m['name'],'CLI',float(error.max()))
  records.append(dict(matrix=m['name'],variant='v3',kind='production-cli',repeat=3,values=int(got.size),max_absolute_error=float(error.max(initial=0)),max_fixture_difference=float(diff.max(initial=0)),command=cmd))
  (H/f'raw/correct-cli-{m["name"]}.txt').write_text(p.stdout+p.stderr)
  c.save('correctness.json',records);print('VERIFIED',m['name'],flush=True)
 c.save('matrices.json',metas)
 print('FULL CHECKS',len(records),flush=True)
if __name__=='__main__':
 import sys
 globals()[sys.argv[1]]()
