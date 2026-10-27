#!/usr/bin/env python3
"""Run after formal timings; one rotated process per configuration."""
import json,subprocess
import run_experiments as r
H=r.HERE
def main():
 c=H/'build/v22';objects=[str(c/'src'/f) for f in ['csr.o','matrix_market.o','parse.o','vector.o','spmv_plan.o','spmv_v2.o','spmv_v22.o']]
 cmd=['gcc','-O3','-march=native','-g','-Wall','-fopenmp','-ffp-contract=off','-iquote',str(c/'src'),str(H/'bench_compare.c'),*objects,'-o',str(H/'build/bench-compare')]
 p=subprocess.run(cmd,capture_output=True,text=True);(H/'raw/diagnostic-build.txt').write_text(p.stdout+p.stderr);p.check_returncode()
 r.save('diagnostic-build.json',{'command':cmd,'sha256':r.sha(H/'build/bench-compare')})
 records=[]
 for name,t in [('heldout-two-giants',12),('giant-row',12),('empty99',12),('bcsstk18',12),('wide',12),('large',24)]:
  meta=r.matrix(name);R=100 if name=='wide' else 9
  cmd=[str(H/'build/bench-compare'),meta['path'],str(R),'12',str(int(meta.get('expand_symmetric',False)))]
  p=subprocess.run(cmd,env=r.env(t),capture_output=True,text=True,timeout=600);(H/f'raw/diagnostic-{name}-t{t}.jsonl').write_text(p.stdout);(H/f'raw/diagnostic-{name}-t{t}.stderr.txt').write_text(p.stderr);p.check_returncode()
  data=[json.loads(l) for l in p.stdout.splitlines()];assert len([x for x in data if x['type']=='sample'])==72
  records.append({'matrix':name,'requested_threads':t,'command':cmd,'records':data,'independent_processes':1});print('DIAGNOSTIC',name,t,flush=True)
 r.save('diagnostic.json',records)
if __name__=='__main__':main()
