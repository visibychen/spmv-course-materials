#!/usr/bin/env python3
import json,subprocess,time
import common as c
H=c.H
def main():
 records=[]
 sources=[c.C/'src'/n for n in ['csr.c','matrix_market.c','parse.c','vector.c','spmv_v3.c']]
 for kind,flags,teams in [('native',['-O3','-march=native','-fopenmp'],[1,12,24]),('portable',['-O3','-fopenmp'],[12]),('sanitize',['-O1','-fopenmp','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie'],[1,12,24]),('no-openmp',['-O3','-Wno-unknown-pragmas'],[1])]:
  dest=H/f'build/test-v3-{kind}'
  cmd=['gcc',*flags,'-g','-Wall','-ffp-contract=off','-iquote',str(c.C/'src'),str(c.C/'tests/test_spmv_v3.c'),*[str(p) for p in sources],'-lm','-o',str(dest)]
  p=subprocess.run(cmd,capture_output=True,text=True);(H/f'raw/build-test-{kind}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
  for t in teams:
   env=c.env(t);env.update(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
   start=time.monotonic();p=subprocess.run([str(dest)],env=env,capture_output=True,text=True,timeout=300)
   (H/f'raw/test-{kind}-{t}.txt').write_text(p.stdout+p.stderr);records.append(dict(build=kind,threads=t,command=cmd,stdout=p.stdout,stderr=p.stderr,returncode=p.returncode,wall_s=time.monotonic()-start,binary_sha256=c.sha(dest)))
   c.save('verification-builds.json',records);print(kind,t,p.stdout.strip(),flush=True);p.check_returncode()
 c.save('verification-source.json',{str(p.relative_to(c.C)):c.sha(p) for p in sorted((c.C/'src').glob('*.[ch]'))})
if __name__=='__main__':main()
