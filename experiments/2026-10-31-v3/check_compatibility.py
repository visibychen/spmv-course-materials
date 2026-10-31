#!/usr/bin/env python3
import json,subprocess,shutil
import common as c
from inputs import text_vector
H=c.H;records=[]
for field,values in [('real',['1.25','-2.5','3']),('integer',['1','-2','3']),('complex',['1 2','-2 1','3 -1']),('pattern',['','',''])]:
 for fmt in (['f32','f64'] if field=='real' else [None]):
  for sym in ['general','symmetric']:
   path=H/'data/typed.mtx';path.write_text(f'%%MatrixMarket matrix coordinate {field} {sym}\n3 3 3\n'+''.join(f'{i} {j} {v}'.rstrip()+'\n' for i,j,v in zip([1,2,3],[1,1,2],values)))
   outputs=[]
   for version in ['original','v3']:
    exe=H/'build/original/csrspmv' if version=='original' else c.C/'csrspmv';out=H/f'data/typed-{version}.mtx'
    cmd=[str(exe),str(path),'--repeat=3','--destination-vector='+str(out),'--destination-vector-prec=50','-v']
    if version=='v3':cmd+=['--kernel=v3']
    if fmt:cmd+=['--matrix-format='+fmt,'--source-vector-format='+fmt,'--destination-vector-format='+fmt]
    if sym=='symmetric':cmd+=['--include-symmetric-part']
    p=subprocess.run(cmd,env=c.env(12),capture_output=True,text=True,timeout=30);p.check_returncode();outputs.append([x for x in out.read_text().splitlines() if not x.startswith('%')])
   assert outputs[0]==outputs[1];records.append(dict(field=field,format=fmt,symmetry=sym,match=True))
c.save('compatibility.json',records);print('TYPE/SYMMETRY',len(records),'PASS')
# Production serial-only build is isolated; native working build stays intact.
dest=H/'build/no-openmp';dest.mkdir(exist_ok=True)
shutil.copytree(c.C/'src',dest/'src',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.o'));shutil.copy2(c.C/'Makefile',dest/'Makefile')
cmd=['make','-j12','NO_OPENMP=1','CFLAGS=-O3 -g -Wall -Wno-unknown-pragmas -iquote src']
p=subprocess.run(cmd,cwd=dest,capture_output=True,text=True);(H/'raw/build-no-openmp-cli.txt').write_text(p.stdout+p.stderr);p.check_returncode()
out=H/'data/no-openmp.mtx';argv=[str(dest/'csrspmv'),str(c.C/'test.mtx'),'--kernel=v3','--repeat=3','--destination-vector='+str(out),'-v']
p=subprocess.run(argv,capture_output=True,text=True);p.check_returncode();assert text_vector(out).tolist()==[9,3,9,6]
c.save('no-openmp-cli.json',dict(command=argv,stdout=p.stdout,stderr=p.stderr,binary_sha256=c.sha(dest/'csrspmv'),correct=True));print('NO_OPENMP CLI PASS')
