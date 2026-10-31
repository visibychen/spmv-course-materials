#!/usr/bin/env python3
import io,json,subprocess,tarfile
import common as c
H=c.H;commit='e83160bf4da3b20f154f81dfbe43fad532764145'
def section(path,name,tag):
 dump=H/'build'/f'{tag}-{name}.bin';copy=H/'build'/f'{tag}-{name}-copy'
 subprocess.run(['objcopy','--dump-section',f'.{name}={dump}',str(path),str(copy)],capture_output=True,check=True)
 return c.sha(dump)
def main():
 c.save('verified-benchmark-sections.json',{n:section(H/'build/bench',n,'verified') for n in ['text','rodata','data']})
 dest=H/'build/v3';dest.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',commit],cwd=c.C))) as tf:tf.extractall(dest)
 p=subprocess.run(['make','-j12','CFLAGS='+c.FLAGS],cwd=dest,capture_output=True,text=True);(H/'raw/build-v3.txt').write_text(p.stdout+p.stderr);p.check_returncode()
 c.build_bench(current=False)
 before=json.loads((H/'verified-benchmark-sections.json').read_text());after={n:section(H/'build/bench',n,'fixed') for n in before}
 assert before==after,(before,after)
 c.save('fixed-build-proof.json',dict(code_commit=commit,verified_sections=before,fixed_sections=after,equal_loadable_computation_sections=True,production_binary_sha256=c.sha(dest/'csrspmv'),benchmark_sha256=c.sha(H/'build/bench')))
 sources={}
 for name,sha in {**c.COMMITS,'v3':commit}.items():
  root=H/'build'/name;sources[name]=dict(commit=sha,binary_sha256=c.sha(root/'csrspmv'),sources={str(p.relative_to(root)):c.sha(p) for p in sorted((root/'src').glob('*.[ch]'))})
 c.save('source-provenance.json',sources)
 env={}
 for cmd in [['lscpu'],['uname','-a'],['gcc','--version'],['free','-b']]:env[' '.join(cmd)]=subprocess.check_output(cmd,text=True)
 env['OMP']={k:v for k,v in c.env(24).items() if k.startswith('OMP_')};env['fixture_format']='V3CSR01, little-endian header u64 rows/columns/nnz; i64 row_ptr, i32 column_indices, f32 values, no numerical conversion beyond original f32 CSR constructor'
 c.save('environment.json',env)
 print('FIXED SOURCE AND BENCHMARK VERIFIED')
if __name__=='__main__':main()
