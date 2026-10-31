#!/usr/bin/env python3
import json,subprocess,difflib,hashlib
import common as c
H=c.H
def main():
 p=subprocess.run(['make','-j12','CFLAGS='+c.FLAGS],cwd=c.C,capture_output=True,text=True);(H/'raw/precommit-build.txt').write_text(p.stdout+p.stderr);p.check_returncode();c.build_bench()
 cli=[]
 cases=[(['--kernel=v3','--repeat=0'],True),(['--kernel=v3','--repeat=3'],True),(['--kernel','v3','--v3-backend','tile8'],True),(['--kernel=v3','--v3-backend=auto'],True),(['--kernel=v3','--v3-backend=pipeline4'],True),(['--kernel=v3','--v3-backend=csr','--v3-balance=rows'],True),(['--kernel=v3','--v3-serial-threshold=0'],True),(['--kernel=v3','--v3-backend=bad'],False),(['--kernel=v3','--v3-balance=bad'],False),(['--kernel=v3','--v3-serial-threshold=-1'],False),(['--kernel=v3','--v3-serial-threshold=9223372036854775808'],False),(['--kernel=v3','--repeat=-1'],False),(['--kernel=v3','--flops=-1'],False),(['--kernel=v3','--flops=100','--repeat=0'],True),(['--kernel=v3','--v3-backend'],False)]
 for args,ok in cases:
  cmd=[str(c.C/'csrspmv'),str(c.C/'test.mtx'),'-v',*args];p=subprocess.run(cmd,env=c.env(12),capture_output=True,text=True,timeout=20)
  assert (p.returncode==0)==ok,(args,p.stdout,p.stderr);cli.append(dict(command=cmd,expected_success=ok,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
 c.save('precommit-cli.json',cli)
 # Retain an exact reconstruction of calibration production source before the
 # subsequent serial-only compatibility macros; no algorithm/default changed.
 before=json.loads((H/'calibration-source.json').read_text());changes={}
 compat='#ifdef _OPENMP\n#include <omp.h>\n#else\n#define omp_get_max_threads() 1\n#define omp_get_num_threads() 1\n#define omp_get_thread_num() 0\n#define omp_in_parallel() 0\n#endif'
 for path,digest in before.items():
  text=(c.C/path).read_text();original=text.replace(compat,'#include <omp.h>').replace('#ifdef _OPENMP\n            actual_threads=omp_get_num_threads();\n#endif','            actual_threads=omp_get_num_threads();')
  assert hashlib.sha256(original.encode()).hexdigest()==digest,(path,'calibration reconstruction')
  if original!=text:
   changes[path]=dict(before=digest,after=c.sha(c.C/path))
   (H/'raw'/('compatibility-'+path.replace('/','-')+'.patch')).write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile=path+'.calibration',tofile=path)))
 c.save('calibration-compatibility.json',dict(changes=changes,reason='Only NO_OPENMP compatibility; OpenMP computation and selected default unchanged.'))
 print('CLI',len(cli),'PASS',flush=True)
if __name__=='__main__':main()
