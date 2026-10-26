#!/usr/bin/env python3
"""Run only after all formal timings: extra instrumented/within-process checks."""
import json,subprocess,time
import run_experiments as r
H=r.HERE
def main():
 c=H/'build/v21';objects=[str(c/'src'/f) for f in ['csr.o','matrix_market.o','parse.o','vector.o','spmv_plan.o','spmv_v2.o','spmv_v21.o']]
 cmd=['gcc','-O3','-march=native','-g','-Wall','-fopenmp','-ffp-contract=off','-iquote',str(c/'src'),str(H/'bench_compare.c'),*objects,'-o',str(H/'build/bench-compare')]
 p=subprocess.run(cmd,capture_output=True,text=True);(H/'raw/diagnostic-build.txt').write_text(p.stdout+p.stderr);p.check_returncode()
 r.save('diagnostic-build.json',{'command':cmd,'sha256':r.sha(H/'build/bench-compare')})
 records=[]
 for name,t in [('heldout-two-giants',12),('giant-row',12),('empty99',12),('bcsstk18',12),('random8',12),('large',24)]:
  meta=r.matrix(name);cmd=[str(H/'build/bench-compare'),meta['path'],'9','12',str(H/'profile.txt'),str(int(meta.get('expand_symmetric',False)))]
  p=subprocess.run(cmd,env=r.env(t),capture_output=True,text=True,timeout=600);(H/f'raw/diagnostic-{name}-t{t}.jsonl').write_text(p.stdout);(H/f'raw/diagnostic-{name}-t{t}.stderr.txt').write_text(p.stderr);p.check_returncode()
  data=[json.loads(l) for l in p.stdout.splitlines()];assert len([x for x in data if x['type']=='sample'])==72
  records.append({'matrix':name,'requested_threads':t,'command':cmd,'records':data,'independent_processes':1});print('DIAGNOSTIC',name,t,flush=True)
 r.save('diagnostic.json',records)
 probe=[]
 for name in ['heldout-two-giants','giant-row','empty99','bcsstk18']:
  for backend in ['v21','v21-merge']:
   for instrument in [False,True]:
    cmd=r.command(backend,name,9)+(['--v21-diagnostics'] if instrument else [])
    for sample in range(1,4):
     p=subprocess.run(cmd,env=r.env(12),capture_output=True,text=True,timeout=30);p.check_returncode()
     tag=f'probe-{name}-{backend}-{int(instrument)}-{sample}';(H/f'raw/{tag}.txt').write_text(p.stdout+p.stderr)
     probe.append({'matrix':name,'backend':backend,'instrumented':instrument,'sample':sample,'command':cmd,'stdout':p.stdout})
 r.save('thread-diagnostic.json',probe);print('THREAD DIAGNOSTIC',len(probe),'processes',flush=True)
if __name__=='__main__':main()
