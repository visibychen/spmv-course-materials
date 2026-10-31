#!/usr/bin/env python3
"""Supplementary full output checks of the stronger compiler control."""
import json,subprocess
import numpy as np
import run_experiments as r
from verify_and_inputs import reference,vector
H=r.HERE;checks=[]
for name in ['large','random8','new-iid8','v222-block1']:
 m=r.matrix(name);ref,bound=reference(m,3);out=H/'data/supplementary-control-output.mtx';cmd=r.command('original-novec',name,3,out)
 p=subprocess.run(cmd,env=r.env(24 if name=='large' else 12),capture_output=True,text=True,timeout=600);p.check_returncode()
 (H/f'raw/supplementary-control-{name}.txt').write_text(p.stdout+p.stderr)
 got=vector(out);error=np.abs(got.astype(np.float64)-ref);assert got.shape==ref.shape and np.all(error<=(0 if bound is None else bound));out.unlink()
 checks.append(dict(matrix=name,variant='original-novec',repeat=3,values=int(got.size),max_absolute_error=float(error.max(initial=0)),command=cmd));r.save('supplementary-control-checks.json',checks)
 print('CONTROL CORRECT',name,flush=True)
proof={}
for name in ['original','v2','v22','v222','original-novec']:
 src=H/'build'/name/'src/csr.o';dump=H/'build'/f'csr-{name}.text';copy=H/'build'/f'csr-{name}-copy.o'
 subprocess.run(['objcopy','--dump-section',f'.text={dump}',str(src),str(copy)],check=True,capture_output=True)
 proof[name]=dict(csr_source_sha256=r.sha(H/'build'/name/'src/csr.c'),object_text_sha256=r.sha(dump),object_text_bytes=dump.stat().st_size)
r.save('csr-object-proof.json',dict(objects=proof,production_text_identical=len({proof[n]['object_text_sha256'] for n in ['original','v2','v22','v222']})==1,limit='Only CSR object .text before relocation; does not prove final addresses/cache/state identical. Novec is intentionally different.'))
