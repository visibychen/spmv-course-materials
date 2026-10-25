#!/usr/bin/env python3
"""Standalone unit, sanitizer and portable-ISA-build checks; run off-benchmark."""
import json
import subprocess
import run_experiments as run

HERE=run.HERE
CORE=run.CORE
sources=[str(CORE/'src'/s) for s in ['csr.c','matrix_market.c','vector.c','parse.c',
         'spmv_plan.c','spmv_csr_scalar.c','spmv_csr_pack.c','spmv_sell.c']]
base=['gcc','-g','-Wall','-fopenmp','-ffp-contract=off','-iquote',str(CORE/'src'),
      str(CORE/'tests/test_spmv_plan.c'),*sources,'-Wl,--wrap=malloc','-lm']

def main():
    commands=[]; sanitizer=[]
    for name,flags,threads in [('sanitize',['-O1','-march=native','-fsanitize=address,undefined','-fno-omit-frame-pointer'],[1,12,24]),
                                ('portable',['-O3'],[12])]:
        binary=HERE/f'build/test-{name}'
        cmd=[*base,*flags,'-o',str(binary)]
        p=subprocess.run(cmd,text=True,capture_output=True)
        (HERE/f'raw/{name}-build.txt').write_text(p.stdout+p.stderr);p.check_returncode()
        commands.append(dict(name=name,command=cmd,binary_sha256=run.sha(binary)))
        for t in threads:
            e=run.env(t);e['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
            p=subprocess.run([str(binary)],env=e,text=True,capture_output=True,timeout=60)
            (HERE/f'raw/{name}-{t}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
            assert '850 checks' in p.stdout and not p.stderr
            record=dict(threads=t,exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
            if name=='sanitize':sanitizer.append(record)
    cmd=['make','-B','check','CFLAGS='+run.FLAGS]
    p=subprocess.run(cmd,cwd=CORE,env=run.env(12),capture_output=True,text=True,timeout=60)
    (HERE/'raw/make-check-native.txt').write_text(p.stdout+p.stderr);p.check_returncode()
    commands.append(dict(name='make-check-native',command=cmd,threads=12,exit=p.returncode))
    run.save('correctness-sanitize.json',sanitizer)
    run.save('verification-builds.json',commands)
    print('850 checks each: native=12 threads; ASan/UBSan=1/12/24; portable build=12')

if __name__=='__main__':main()
