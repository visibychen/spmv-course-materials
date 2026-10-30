#!/usr/bin/env python3
"""After formal timings only:8 independent processes,128 rotated samples each."""
import json,subprocess
import run_experiments as r
H=r.HERE
def main():
 c=H/'build/v221';objects=[str(c/'src'/n) for n in ['csr.o','matrix_market.o','parse.o','vector.o','spmv_plan.o','spmv_v2.o','spmv_v22.o','spmv_v221.o']]
 cmd=['gcc','-O3','-march=native','-g','-Wall','-fopenmp','-ffp-contract=off','-iquote',str(c/'src'),str(H/'bench_compare.c'),*objects,'-o',str(H/'build/bench-compare')]
 p=subprocess.run(cmd,capture_output=True,text=True);(H/'raw/diagnostic-build.txt').write_text(p.stdout+p.stderr);p.check_returncode()
 r.save('diagnostic-build.json',dict(command=cmd,sha256=r.sha(H/'build/bench-compare')))
 records=[]
 for name,t in [('random8',12),('new-iid8',12),('v22-empty99',12),('v22-empty90',12),('heldout-two-giants',12),('empty99',12),('bcsstk18',12),('large',24)]:
  meta=r.matrix(name);cmd=[str(H/'build/bench-compare'),meta['path'],'9','16',str(int(meta.get('expand_symmetric',False)))]
  p=subprocess.run(cmd,env=r.env(t),capture_output=True,text=True,timeout=600)
  (H/f'raw/diagnostic-{name}-t{t}.jsonl').write_text(p.stdout);(H/f'raw/diagnostic-{name}-t{t}.stderr.txt').write_text(p.stderr);p.check_returncode()
  data=[json.loads(line) for line in p.stdout.splitlines()];assert sum(x['type']=='sample' for x in data)==128
  records.append(dict(matrix=name,requested_threads=t,command=cmd,records=data,independent_processes=1));print('DIAGNOSTIC',name,flush=True)
 r.save('diagnostic.json',records)
if __name__=='__main__':main()
