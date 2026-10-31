import hashlib,json,os,subprocess,io,tarfile
from pathlib import Path
H=Path(__file__).resolve().parent;M=H.parents[1];C=M.parent/'csrspmv'
FLAGS='-O3 -march=native -g -Wall -iquote src -fopenmp'
COMMITS={'original':'9352c865044f4c8b344d6fe5a277200a89f7a08b','v2':'9b652e8da85b7a1ad255e0b4f8ddadc5e0558f1a'}
VARIANTS={'original':0,'v2':1,'v3':2,'v3-tile':3,'v3-pipeline':4,'v3-csr':5,'v3-rows':6,'v3-nosimd':7,'v3-auto':8,'aa-a':1,'aa-b':1}
def save(n,x):(H/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def env(t,wait='PASSIVE'):
 e={k:v for k,v in os.environ.items() if not k.startswith(('OMP_','GOMP_'))}
 e.update(OMP_NUM_THREADS=str(t),OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='spread',OMP_WAIT_POLICY=wait,LC_ALL='C')
 return e
def build_legacy():
 result={}
 for n,commit in COMMITS.items():
  dest=H/'build'/n;dest.mkdir(exist_ok=True)
  with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',commit],cwd=C))) as tf:tf.extractall(dest)
  p=subprocess.run(['make','-j12','CFLAGS='+FLAGS],cwd=dest,capture_output=True,text=True);(H/f'raw/build-{n}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
  result[n]=dict(commit=commit,binary_sha256=sha(dest/'csrspmv'))
 save('legacy-build.json',result)
def build_bench(current=True):
 v3=C if current else H/'build/v3'
 includes=[H/'build/original/src',H/'build/v2/src',v3/'src']
 objects=[H/'build/original/src'/f'{n}.o' for n in ['csr','matrix_market','parse','vector']]
 objects += [H/'build/v2/src'/f'{n}.o' for n in ['spmv_plan','spmv_v2']]+[v3/'src/spmv_v3.o']
 cmd=['gcc',*FLAGS.split(),'-Werror','-ffp-contract=off',*[v for p in includes for v in ['-iquote',str(p)]],str(H/'bench.c'),*[str(p) for p in objects],'-o',str(H/'build/bench')]
 p=subprocess.run(cmd,capture_output=True,text=True);(H/'raw/build-bench.txt').write_text(p.stdout+p.stderr);p.check_returncode()
 save('bench-build.json',dict(command=cmd,binary_sha256=sha(H/'build/bench'),object_sha256={str(p):sha(p) for p in objects}))
 print('BENCH BUILT',flush=True)
if __name__=='__main__':
 build_legacy();build_bench()
