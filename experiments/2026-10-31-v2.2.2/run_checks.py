#!/usr/bin/env python3
"""Independent unit/sanitizer configurations before the source commit."""
import hashlib,json,os,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parent;C=H.parents[1].parent/'csrspmv'
def save(name,x):(H/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def env(t):
 e={k:v for k,v in os.environ.items() if not k.startswith(('OMP_','GOMP_'))}
 e.update(OMP_NUM_THREADS=str(t),OMP_DYNAMIC='FALSE',OMP_WAIT_POLICY='PASSIVE',OMP_PLACES='cores',OMP_PROC_BIND='spread',ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
 return e
def main():
 records=[];sources=[str(C/'src'/n) for n in ['csr.c','matrix_market.c','parse.c','vector.c','spmv_plan.c','spmv_v2.c','spmv_v22.c','spmv_v222.c']]
 for kind,flags,teams in [('native',['-O3','-march=native'],[1,12,24]),('portable',['-O3'],[12]),('sanitize',['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie'],[1,12,24])]:
  for version in ['v2','v22','v222']:
   dest=H/f'build/test-{version}-{kind}'
   cmd=['gcc',*flags,'-g','-Wall','-fopenmp','-ffp-contract=off','-iquote',str(C/'src'),str(C/f'tests/test_spmv_{version}.c'),*sources,'-Wl,--wrap=malloc','-lm','-o',str(dest)]
   p=subprocess.run(cmd,capture_output=True,text=True);(H/f'raw/build-test-{version}-{kind}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
   for t in teams:
    start=time.monotonic();p=subprocess.run([str(dest)],env=env(t),capture_output=True,text=True,timeout=240)
    (H/f'raw/test-{version}-{kind}-{t}.txt').write_text(p.stdout+p.stderr)
    records.append(dict(test=version,build=kind,threads=t,command=cmd,stdout=p.stdout,stderr=p.stderr,returncode=p.returncode,wall_s=time.monotonic()-start,sha256=sha(dest)))
    save('verification-builds.json',records);print(version,kind,t,p.stdout.strip(),flush=True);p.check_returncode()
 save('verification-source.json',{str(p.relative_to(C)):sha(p) for p in sorted((C/'src').glob('*.[ch]'))})
if __name__=='__main__':main()
