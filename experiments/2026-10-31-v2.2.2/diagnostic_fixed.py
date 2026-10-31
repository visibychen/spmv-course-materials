#!/usr/bin/env python3
"""Three independent processes per condition; within-process rotations are correlated."""
import json,subprocess
import run_experiments as r
H=r.HERE
def main():
 src=H/'build/v222';dest=H/'build/bench_compare'
 objects=[str(p) for p in sorted((src/'src').glob('*.o')) if p.name not in ['main.o','program_options.o']]
 cmd=['gcc',*r.FLAGS.split(),'-ffp-contract=off','-iquote',str(src/'src'),str(H/'bench_compare_fixed.c'),*objects,'-o',str(dest)]
 p=subprocess.run(cmd,capture_output=True,text=True);(H/'raw/build-diagnostic-fixed.txt').write_text(p.stdout+p.stderr);p.check_returncode()
 result=[]
 for name,t in [('v222-block1',12),('v222-block8',12),('v22-empty90',12),('empty99',12),('bcsstk18',12),('random8',12),('heldout-two-giants',12),('large',24)]:
  for sample in range(1,4):
   m=r.matrix(name);argv=[str(dest),m['path'],'9','12',str(int(m.get('expand_symmetric',False)))]
   p=subprocess.run(argv,env=r.env(t),capture_output=True,text=True,timeout=300);p.check_returncode();records=[json.loads(s) for s in p.stdout.splitlines()]
   (H/f'raw/diagnostic-{name}-{sample}.txt').write_text(p.stdout+p.stderr)
   result.append(dict(matrix=name,threads=t,sample=sample,command=argv,records=records));r.save('diagnostic.json',result)
   print('DIAGNOSTIC',name,sample,flush=True)
 r.save('diagnostic-build.json',dict(command=cmd,binary_sha256=r.sha(dest),independent_processes=len(result),within_process_rounds=12,backends=6))
if __name__=='__main__':main()
