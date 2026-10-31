#!/usr/bin/env python3
"""Independent finite calibration before the code commit, never formal inputs."""
import csv,json,math,random,statistics,struct,subprocess,time
import numpy as np
import common as c
H=c.H
SHAPES=[('cal-u8-a',80003,900001,8),('cal-u8-b',170003,4000003,8),('cal-u8-c',260003,6500011,8),('cal-u8-d',400009,9000011,8),
        ('cal-short2',240019,900007,2),('cal-short4',180013,1900003,4),('cal-short16',110017,2900003,16),('cal-ragged',100019,3900007,0)]
def main():
 c.build_bench();exe=H/'build/calibration-bench';exe.write_bytes((H/'build/bench').read_bytes());exe.chmod(0o755)
 metas=[]
 for name,m,n,L in SHAPES:
  seed=2026103141+sum(ord(ch) for ch in name);rng=np.random.default_rng(seed)
  counts=np.full(m,L,dtype=np.int64) if L else 7+2*(np.arange(m)%2)
  rp=np.r_[0,np.cumsum(counts)].astype('<i8');nz=int(rp[-1])
  j=rng.integers(0,n,size=nz,dtype=np.int32);v=rng.integers(1,5,size=nz).astype('<f4')*.25
  path=H/f'data/{name}.csr'
  with path.open('wb') as f:
   f.write(struct.pack('<8sQQQ',b'V3CSR01\0',m,n,nz));rp.tofile(f);j.tofile(f);v.tofile(f)
  metas.append(dict(name=name,rows=m,columns=n,nonzeros=nz,seed=seed,path=str(path),sha256=c.sha(path),source='independent direct CSR generator in calibrate.py'))
 c.save('calibration-inputs.json',metas)
 c.save('calibration-source.json',{str(p.relative_to(c.C)):c.sha(p) for p in sorted((c.C/'src').glob('*.[ch]'))})
 records=[];rng=random.Random(2026103142)
 blocks=[(m,t,k) for m in metas for t in [1,12,24] for k in range(1,4)];rng.shuffle(blocks)
 for m,t,k in blocks:
  modes=[('auto',8),('tile8',3),('pipeline4',4),('csr',5)];rng.shuffle(modes)
  for order,(name,mode) in enumerate(modes):
   cmd=[str(exe),'run',m['path'],str(mode),'9'];p=subprocess.run(cmd,env=c.env(t),capture_output=True,text=True,timeout=60);p.check_returncode()
   metrics=json.loads(p.stdout);assert metrics['flops']==2*m['nonzeros']*9
   records.append(dict(matrix=m['name'],threads=t,sample=k,mode=name,order=order,command=cmd,**metrics))
  c.save('calibration.json',dict(binary_sha256=c.sha(exe),records=records,seed=2026103142))
 ratios=[]
 for m in metas[4:]:
  for t in [1,12,24]:
   med=lambda mode:statistics.median(r['total_s'] for r in records if r['matrix']==m['name'] and r['threads']==t and r['mode']==mode)
   ratios.append(dict(matrix=m['name'],threads=t,auto_over_tile=med('auto')/med('tile8')))
 geo=math.exp(statistics.mean(math.log(x['auto_over_tile']) for x in ratios));worst=max(x['auto_over_tile'] for x in ratios)
 selected='auto' if geo<=.97 and worst<=1.10 else 'tile8'
 c.save('calibration-decision.json',dict(selected_default=selected,geomean_auto_over_tile_non8=geo,worst_group_auto_over_tile=worst,rule='auto iff geomean<=0.97 and every group<=1.10; otherwise tile8; frozen before formal',ratios=ratios,observations=len(records)))
 print('CALIBRATION',len(records),'DEFAULT',selected,'GEOMEAN',geo,'WORST',worst,flush=True)
 for m in metas[:4]:
  for t in [1,12,24]:
   med=lambda mode:statistics.median(r['total_s'] for r in records if r['matrix']==m['name'] and r['threads']==t and r['mode']==mode)
   print(m['name'],t,'tile/csr',round(med('tile8')/med('csr'),3),'pipeline/csr',round(med('pipeline4')/med('csr'),3))
if __name__=='__main__':main()
