#!/usr/bin/env python3
"""Same-binary warmed diagnostic; never mixed with CLI timings."""
import json,subprocess,sys
from pathlib import Path
import run_experiments as run
H=run.HERE
def build():
    v1=H/'build/v1';v2=H/'build/v2'
    defines=['-D'+x+'=bench_'+x for x in ['spmv_plan_prepare','spmv_plan_execute','spmv_plan_free','spmv_kernel_name']]
    commands=[];objects=[]
    for src in [v1/'src'/n for n in ['spmv_plan.c','spmv_csr_scalar.c','spmv_csr_pack.c','spmv_sell.c']]+[H/'bench_v1_adapter.c']:
        obj=H/'build'/('bench-'+src.stem+'.o')
        cmd=['gcc','-O3','-march=native','-g','-Wall','-fopenmp','-iquote',str(v1/'src'),*defines]
        if src.name in ['spmv_csr_pack.c','spmv_sell.c']:cmd+=['-ffp-contract=off']
        cmd+=['-c',str(src),'-o',str(obj)]
        p=subprocess.run(cmd,capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr
        commands.append(cmd);objects.append(obj)
    cmd=['gcc','-O3','-march=native','-g','-Wall','-fopenmp','-iquote',str(v2/'src'),str(H/'bench_compare.c'),
      *map(str,objects),*[str(v2/'src'/n) for n in ['csr.o','vector.o','matrix_market.o','parse.o','spmv_plan.o','spmv_v2.o']],'-lm','-o',str(H/'build/bench_compare')]
    p=subprocess.run(cmd,capture_output=True,text=True);p.check_returncode();assert not p.stderr,p.stderr
    commands.append(cmd);run.save('diagnostic-build.json',dict(commands=commands,binary_sha256=run.sha(H/'build/bench_compare')))
    print('diagnostic built',flush=True)
def main():
    if sys.argv[1]=='build':build();return
    all_records=[]
    for n,t in [('random8',12),('heavy-clustered',12),('giant-row',12),('giant-row',24),('large',1),('large',12),('large',24)]:
        target=H/f'raw/diagnostic-{n}-t{t}.jsonl'
        cmd=[str(H/'build/bench_compare'),run.matrix(n)['path'],'9','10']
        if not target.exists():
            p=subprocess.run(cmd,env=run.env(t),capture_output=True,text=True,timeout=900)
            (H/f'raw/diagnostic-{n}-t{t}.stderr.txt').write_text(p.stderr);p.check_returncode();target.write_text(p.stdout)
        rows=[json.loads(l) for l in target.read_text().splitlines()]
        assert sum(x['type']=='sample' for x in rows)==50
        all_records.append(dict(matrix=n,threads=t,command=cmd,raw=str(target.relative_to(H)),records=rows))
        print('diagnostic',n,t,'50 balanced samples',flush=True)
        run.save('diagnostic.json',all_records)
if __name__=='__main__':main()
