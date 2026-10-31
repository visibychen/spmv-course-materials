#!/usr/bin/env python3
"""New holdout inputs and independent full-vector checks, outside performance."""
import gzip,json,subprocess
import numpy as np
import run_experiments as run
H=run.HERE
SHAPES=[('v222-block1',310009,1300003,8,'block1'),('v222-block4',330013,1500007,8,'block4'),
 ('v222-block8',350003,1700009,8,'block8'),('v222-block9',370003,1900013,8,'block9'),
 ('v222-block90',390019,2100011,8,'block90'),('v222-block88',410009,2300009,8,'block88'),
 ('v222-block64',240007,700001,64,'block4'),('v222-block65',240011,700003,65,'block4'),
 ('v222-period101',380003,1500013,8,'period101'),('v222-iid',100003,2000003,8,'iid'),
 ('v222-small',19001,40009,8,'iid'),('v222-zero',550003,1700003,0,'iid')]
REAL=[] # All10 existing real matrices remain in the68-input regression set.
def synthetic(name,m,n,L,kind):
 seed=2026103109+sum((i+1)*ord(c) for i,c in enumerate(name));rng=np.random.default_rng(seed)
 counts=np.full(m,L,dtype=np.int64)
 if kind.startswith('block'):
  label=int(kind[5:]);nr=label if label in [1,4,8,9] else 1;ratio=.90 if label==90 else .88 if label==88 else .95
  counts[:]=0
  for g in range(nr):
   lo=g*m//nr;hi=(g+1)*m//nr;live=int((hi-lo)*(1-ratio));counts[lo:lo+live]=L
 if kind=='two':counts[0]=170009;counts[m//2]=130003
 if kind=='six':counts[np.linspace(0,m-1,6,dtype=int)]=33001
 if kind=='one':counts[m//2]=400009
 if kind=='empty99':counts[np.arange(m)%100!=0]=0
 if kind=='empty90':counts[m//10:]=0
 if kind=='period97':counts[(np.arange(m)+29)%97!=0]=0
 if kind=='period101':counts[(np.arange(m)+17)%101!=0]=0
 if kind=='random91':counts[rng.random(m)<.91]=0
 if kind=='empty50':counts[rng.random(m)<.5]=0
 if kind=='longtail':counts[:1291]=773
 path=H/f'data/{name}.mtx';expected=H/f'data/{name}.expected.f32';sums=np.zeros(m,dtype=np.float32)
 with path.open('w') as f:
  f.write(f'%%MatrixMarket matrix coordinate real general\n% new v2.2.2 holdout seed {seed}\n{m} {n} {int(counts.sum())}\n')
  for i,l in enumerate(counts):
   l=int(l)
   if not l:continue
   if kind=='banded':cols=(np.arange(l,dtype=np.int64)+i*3)%n
   else:cols=np.sort(rng.choice(min(n,4096) if kind=='hot' else n,size=l,replace=False))
   vals=rng.integers(1,5,size=l).astype(np.float32)*np.float32(.25);sums[i]=np.sum(vals,dtype=np.float32)
   f.writelines(f'{i+1} {int(j)+1} {float(v):.2f}\n' for j,v in zip(cols,vals))
 sums.tofile(expected)
 return dict(name=name,group='new-heldout',path=str(path),expected_path=str(expected),rows=m,columns=n,
  nonzeros=int(counts.sum()),profile=kind,seed=seed,sha256=run.sha(path),expected_sha256=run.sha(expected),license='project generated; GPL-3.0-or-later')
def inputs():
 records=[]
 for m in json.loads((run.OLD/'matrices.json').read_text()):
  if m['group']=='calibration':continue
  assert run.sha(m['path'])==m['sha256'];m['prior_group']=m['group'];m['group']='development';records.append(m)
 for s in SHAPES:records.append(synthetic(*s));print('GENERATED',s[0],flush=True)
 for collection,name in REAL:
  archive=H/f'data/nist-{name}.mtx.gz';path=H/f'data/{name}.mtx'
  with gzip.open(archive,'rb') as f:path.write_bytes(f.read())
  header=[]
  with path.open() as f:
   first=next(f).strip();header.append(first)
   for line in f:
    header.append(line.rstrip())
    if not line.startswith('%'):dims=list(map(int,line.split()));break
  records.append(dict(name=name,group='new-real',path=str(path),rows=dims[0],columns=dims[1],nonzeros=dims[2],
   stored_nonzeros=dims[2],field=first.split()[3],symmetry=first.split()[4],expand_symmetric=first.split()[4]!='general',
   url=f'https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/{collection}/{name}.mtx.gz',
   metadata_url=f'https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/{collection}/{name}.html',
   sha256=run.sha(path),archive_sha256=run.sha(archive),matrix_header=header,accessed_on='2026-10-27',
   license='No standalone license stated on NIST metadata page; local use only, MTX not redistributed',
   modifications='Decompressed bytes unchanged; runtime f32 conversion, symmetric expansion equally applied'))
  print('NEW REAL',name,dims,flush=True)
 run.save('matrices.json',records)
 print('INPUTS',len(records),flush=True)
def vector(path):
 with open(path) as f:
  for l in f:
   if not l.startswith('%'):m=int(l.split()[0]);break
  arr=np.loadtxt(f,dtype=np.float32,ndmin=1)
 assert arr.size==m;return arr
def reference(meta,R):
 if 'expected_path' in meta:return np.fromfile(meta['expected_path'],dtype=np.float32)*np.float32(R),None
 vals=np.loadtxt(meta['path'],comments='%',skiprows=len(meta['matrix_header']),ndmin=2)
 i=vals[:,0].astype(np.int64)-1;j=vals[:,1].astype(np.int64)-1;v=vals[:,2].astype(np.float32).astype(np.float64);m=meta['rows']
 sums=np.bincount(i,weights=v,minlength=m);ab=np.bincount(i,weights=np.abs(v),minlength=m);count=np.bincount(i,minlength=m)
 if meta['expand_symmetric']:
  off=i!=j;sums+=np.bincount(j[off],weights=v[off],minlength=m)
  ab+=np.bincount(j[off],weights=np.abs(v[off]),minlength=m);count+=np.bincount(j[off],minlength=m)
 meta['expanded_nonzeros_verified']=int(count.sum())
 return R*sums,(count+32)*np.finfo(np.float32).eps*ab*max(R,1)*16+1e-30
def verify():
 metas=run.matrices();real_names={m['name'] for m in metas if 'expected_path' not in m}
 old=json.loads((H/'correctness.json').read_text()) if (H/'correctness.json').exists() else []
 result=[r for r in old if r.get('matrix') not in real_names and r.get('kind')!='compatibility']
 done={(r['matrix'],r['variant']) for r in result}
 for meta in metas:
  ref,bound=reference(meta,3)
  variants=['original','v2','v22','v222']+(['v222-runs-off','v222-runs-on'] if meta['group']=='new-heldout' else [])
  for variant in variants:
   if (meta['name'],variant) in done:continue
   out=H/'data/check-output.mtx';cmd=run.command(variant,meta['name'],3,out)
   # The upstream writer uses fixed decimal places. Nine places turn 3e-10
   # into zero on SHERMAN3, for original and every optimized backend alike.
   # Fifty places round-trip even subnormal f32; no solver change is needed.
   if 'expected_path' not in meta:cmd+=['--destination-vector-prec=50']
   p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,timeout=600)
   (H/f'raw/correct-{meta["name"]}-{variant}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
   got=vector(out);error=np.abs(got.astype(np.float64)-ref);assert got.shape==ref.shape
   assert np.all(error<=(0 if bound is None else bound)),(meta['name'],variant,float(error.max()))
   result.append(dict(matrix=meta['name'],variant=variant,repeat=3,requested_threads=12,values=int(got.size),
    max_absolute_error=float(error.max(initial=0)),exact=bound is None,serialization_precision=50 if bound is not None else 9,command=cmd));out.unlink()
   run.save('correctness.json',result);print('CORRECT',meta['name'],variant,flush=True)
 run.save('matrices.json',metas)
 # Check scalar/double/integer/complex/pattern compatibility against original.
 typed=H/'data/typed.mtx';files=[H/f'data/typed-{v}.mtx' for v in range(4)]
 for field,values in [('real',['1.25','-2.5','3']),('integer',['1','-2','3']),('complex',['1 2','-2 1','3 -1']),('pattern',['','',''])]:
  for fmt in (['f32','f64'] if field=='real' else [None]):
   for sym in ['general','symmetric']:
    typed.write_text(f'%%MatrixMarket matrix coordinate {field} {sym}\n3 3 3\n'+''.join(f'{i} {j} {v}'.rstrip()+'\n' for i,j,v in zip([1,2,3],[1,1,2],values)))
    for index,name in enumerate(['original','v2','v22','v222']):
     folder,opts=run.VARIANTS[name];cmd=[str(H/'build'/folder/'csrspmv'),str(typed),*opts,'--repeat=3','--destination-vector='+str(files[index])]
     if fmt:cmd+=['--matrix-format='+fmt,'--source-vector-format='+fmt,'--destination-vector-format='+fmt]
     if sym=='symmetric':cmd+=['--include-symmetric-part']
     p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,timeout=15);p.check_returncode()
    data=lambda path:[l for l in path.read_text().splitlines() if not l.startswith('%')]
    assert all(data(files[0])==data(f) for f in files[1:]);result.append(dict(kind='compatibility',field=field,format=fmt,symmetry=sym))
 run.save('correctness.json',result);print('CORRECTNESS records',len(result),flush=True)
