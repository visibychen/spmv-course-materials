#!/usr/bin/env python3
"""Reproducible v1 experiment, Linux/WSL + GCC. No concurrent benchmarks.
Usage: python3 run_experiments.py build|generate|correctness|pilot|formal|large|amortization|summarize
Raw records are append-only; restarting skips completed keys.
"""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
import numpy as np

HERE = Path(__file__).resolve().parent
MATERIALS = HERE.parents[1]
CORE = MATERIALS.parent / 'csrspmv'
BASE = MATERIALS / 'experiments/2026-10-25-baseline'
ORIGINAL = '9352c865044f4c8b344d6fe5a277200a89f7a08b'
FLAGS = '-O3 -march=native -g -Wall -iquote src -fopenmp'
SEED = 20261025
for directory in ['build', 'data', 'raw']:
    (HERE / directory).mkdir(exist_ok=True)

def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
    return h.hexdigest()

def env(threads):
    e={k:v for k,v in os.environ.items() if not k.startswith(('OMP_','GOMP_'))}
    e.update(OMP_NUM_THREADS=str(threads), OMP_DYNAMIC='FALSE', OMP_PLACES='cores',
             OMP_PROC_BIND='spread', OMP_WAIT_POLICY='PASSIVE', LC_ALL='C')
    return e

VARIANTS = {
    'original': ('original', []),
    'original-novec': ('original-novec', []),
    'csr-scalar': ('v1', ['--kernel=csr-scalar']),
    'csr-pack': ('v1', ['--kernel=csr-pack']),
    'sell8': ('v1', ['--kernel=sell', '--sell-chunk=8']),
    'sell16': ('v1', ['--kernel=sell', '--sell-chunk=16']),
    'v1-original': ('v1', ['--kernel=original']),
}
PRIMARY = ['original','csr-scalar','csr-pack','sell8','sell16']

# Equal row profile across random/banded/hot8, plus short/long row sweep.
CASES = [(f'random{l}', min(1000000,max(8192,2000000//l)),12000000,l,'random')
         for l in [1,2,4,7,8,9,15,16,17,32,64,256]] + [
    ('banded8',250000,12000000,8,'banded'),
    ('hot8',250000,12000000,8,'hot'),
    ('heavy-clustered',100000,12000000,4,'clustered'),
    ('heavy-scattered',100000,12000000,4,'scattered'),
    ('giant-row',100000,2000000,1,'giant'),
    ('empty99',1000000,12000000,0,'empty99'),
    ('zero',100000,12000000,0,'zero'),
    ('cache-small',256,256,8,'random'),
    ('wide',101,12000000,8,'random'),
    ('tall',1000000,64,8,'hot'),
]

def matrix(name):
    return BASE/'data/large_random.mtx' if name=='large' else HERE/f'data/{name}.mtx'

def expected(name):
    return BASE/'data/large_expected.f32' if name=='large' else HERE/f'data/{name}.expected.f32'

def build():
    metadata={}
    for variant in ['original','original-novec','v1']:
        target=HERE/'build'/variant
        target.mkdir(exist_ok=True)
        if variant.startswith('original'):
            data=subprocess.check_output(['git','-C',str(CORE),'archive',ORIGINAL])
            with tarfile.open(fileobj=io.BytesIO(data)) as tf: tf.extractall(target)
        else:
            for src in list((CORE/'src').glob('*.c'))+list((CORE/'src').glob('*.h'))+[CORE/'Makefile']:
                dest=target/src.relative_to(CORE); dest.parent.mkdir(exist_ok=True)
                shutil.copyfile(src,dest)
        flags=FLAGS+(' -fno-tree-loop-vectorize -fno-tree-slp-vectorize' if variant=='original-novec' else '')
        subprocess.run(['make','clean'],cwd=target,check=True,capture_output=True)
        cmd=['make','-j12','CFLAGS='+flags+' -fopt-info-vec-all='+str(HERE/f'raw/vectorization-{variant}.txt')]
        p=subprocess.run(cmd,cwd=target,text=True,capture_output=True)
        (HERE/f'raw/build-{variant}.txt').write_text(p.stdout+p.stderr); p.check_returncode()
        metadata[variant]={'command':cmd,'flags':flags,'binary_sha256':sha(target/'csrspmv')}
        if variant=='v1':
            for fn in ['spmv_scalar_f32','spmv_pack_f32','spmv_sell8_f32','spmv_sell16_f32']:
                p=subprocess.run(['objdump','-d','-M','intel','--disassemble='+fn,str(target/'csrspmv')],text=True,capture_output=True,check=True)
                (HERE/f'raw/assembly-{fn}.txt').write_text(p.stdout)
    cmd=['gcc','-O3','-std=c11','-Wall',str(HERE/'generate_cases.c'),'-o',str(HERE/'build/generate_cases')]
    subprocess.run(cmd,check=True)
    source={str(p.relative_to(CORE)):sha(p) for p in sorted((CORE/'src').glob('*')) if p.suffix in ['.c','.h']}
    source['Makefile']=sha(CORE/'Makefile')
    save('build.json',metadata)
    save('source-provenance.json',{'original_commit':ORIGINAL,'branch':subprocess.check_output(['git','-C',str(CORE),'branch','--show-current'],text=True).strip(),'source_sha256':source,'generator_sha256':sha(HERE/'generate_cases.c')})
    environment={}
    for cmd in [['lscpu'],['uname','-a'],['gcc','--version'],['free','-b'],['git','-C',str(CORE),'status','--short']]:
        environment[' '.join(cmd)]=subprocess.check_output(cmd,text=True)
    environment['omp']= {k:v for k,v in env(12).items() if k.startswith(('OMP_','GOMP_'))}
    environment['start_time']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
    save('environment.json',environment)
    probe=BASE/'omp_probe.c'
    subprocess.run(['gcc','-O2','-fopenmp',str(probe),'-o',str(HERE/'build/omp_probe')],check=True)
    for t in [1,12,24]:
        p=subprocess.run([str(HERE/'build/omp_probe')],env=env(t),capture_output=True,text=True,check=True)
        (HERE/f'raw/omp-{t}.txt').write_text(p.stdout+p.stderr)
    print('built',list(metadata),flush=True)

def generate():
    records=[]
    for name,m,n,l,profile in CASES:
        cmd=[str(HERE/'build/generate_cases'),str(HERE/'data'/name),str(m),str(n),str(l),profile]
        if not matrix(name).exists(): subprocess.run(cmd,check=True)
        with matrix(name).open() as f:
            header=[next(f) for _ in range(3)][-1].split()
        records.append(dict(name=name,rows=m,columns=n,nonzeros=int(header[2]),length=l,profile=profile,
                            file_bytes=matrix(name).stat().st_size,sha256=sha(matrix(name)),expected_sha256=sha(expected(name)),command=cmd))
        print('input',name,header,flush=True)
    old=json.loads((BASE/'matrix.json').read_text())
    records.append(dict(name='large',rows=12000000,columns=12000000,nonzeros=96000000,
                        profile='8 segment-random entries/row; reused original baseline input',
                        file_bytes=matrix('large').stat().st_size,sha256=sha(matrix('large')),
                        expected_sha256=sha(expected('large')),baseline_metadata=old))
    save('matrices.json',records)

def command(variant,name,repeat,output=None):
    folder,options=VARIANTS[variant]
    cmd=[str(HERE/'build'/folder/'csrspmv'),str(matrix(name)),*options,
         '--matrix-format=f32','--source-vector-format=f32','--destination-vector-format=f32',
         '--repeat='+str(repeat),'-v']
    if output: cmd+=['--destination-vector='+str(output),'--destination-vector-prec=9']
    return cmd

def read_vector(path):
    with Path(path).open() as f:
        for line in f:
            if line.startswith('%'): continue
            dims=tuple(map(int,line.split())); break
        result=np.loadtxt(f,dtype=np.float32,ndmin=1)
    assert result.size==dims[0]
    return result

def correctness():
    results=[]
    names=['random1','random8','random17','random256','banded8','hot8','heavy-clustered','heavy-scattered','giant-row','empty99','zero','cache-small','wide','tall','large']
    for name in names:
        reference=np.fromfile(expected(name),dtype=np.float32)*np.float32(3)
        for variant in PRIMARY+(['v1-original'] if name=='cache-small' else []):
            out=HERE/'data/check-output.mtx'
            cmd=command(variant,name,3,out)
            p=subprocess.run(cmd,env=env(12),capture_output=True,text=True,timeout=180)
            (HERE/f'raw/correctness-{name}-{variant}.txt').write_text(p.stdout+p.stderr); p.check_returncode()
            got=read_vector(out)
            assert got.shape==reference.shape
            error=float(np.max(np.abs(got-reference),initial=0))
            assert error==0,(name,variant,error)
            results.append(dict(matrix=name,variant=variant,threads=12,repeat=3,values=got.size,max_absolute_error=error))
            out.unlink(); print('correct',name,variant,flush=True)
            save('correctness.json',results)
    # Existing type/symmetry behavior is tested against the archived original.
    tiny=HERE/'data/typed.mtx'; vout=HERE/'data/check-v1.mtx'; bout=HERE/'data/check-original.mtx'
    for field,values,extra in [('real',['1.25','-2.5','3.0'],[]),('integer',['1','-2','3'],[]),
                               ('pattern',['','',''],[]),('complex',['1 2','-2 1','3 -1'],[]),
                               ('real',['1.25','-2.5','3.0'],['--include-symmetric-part'])]:
        sym='symmetric' if extra else 'general'
        tiny.write_text(f'%%MatrixMarket matrix coordinate {field} {sym}\n3 3 3\n'+''.join(f'{r} {c} {v}'.rstrip()+'\n' for r,c,v in zip([1,2,3],[1,1,2],values)))
        for dtype in (['f32','f64'] if field=='real' else [None]):
            for variant in ['original','sell16']:
                folder,opts=VARIANTS[variant]
                cmd=[str(HERE/'build'/folder/'csrspmv'),str(tiny),*opts,*extra,'--repeat=3','--destination-vector='+str(bout if variant=='original' else vout)]
                if dtype: cmd+=['--matrix-format='+dtype,'--source-vector-format='+dtype,'--destination-vector-format='+dtype]
                p=subprocess.run(cmd,env=env(12),text=True,capture_output=True,timeout=15); p.check_returncode()
            def contents(p): return [x for x in p.read_text().splitlines() if not x.startswith('%')]
            assert contents(bout)==contents(vout)
            results.append(dict(matrix='typed-'+field,format=dtype,symmetric=bool(extra),same_as_original=True))
    for flag in ['--kernel=bad','--sell-chunk=7','--sell-chunk=8garbage','--sell-memory-mib=-1','--repeat=-1','--flops=-1','--sell-memory-mib','--kernel']:
        cmd=[str(HERE/'build/v1/csrspmv'),str(matrix('cache-small')),flag]
        p=subprocess.run(cmd,env=env(1),capture_output=True,text=True,timeout=5)
        assert p.returncode!=0,flag
        results.append(dict(invalid_option=flag,exit=p.returncode))
    for variant in ['original','sell16']:
        cmd=command(variant,'zero',1)+['--flops=1']
        try:
            p=subprocess.run(cmd,env=env(1),capture_output=True,text=True,timeout=2)
            assert variant!='original' and p.returncode!=0
            results.append(dict(matrix='zero',variant=variant,flops=1,exit=p.returncode))
        except subprocess.TimeoutExpired:
            assert variant=='original';results.append(dict(matrix='zero',variant=variant,flops=1,timeout_seconds=2))
    for f in [tiny,vout,bout]:
        if f.exists(): f.unlink()
    save('correctness.json',results)

FIELDS=['phase','matrix','variant','threads','repeat','sample','execute_s','ms_per_spmv','prepare_s','selected','reason','extra_bytes','slots','wall_s','max_rss_kib','major_faults','command_file']

def records():
    path=HERE/'measurements.csv'
    return list(csv.DictReader(path.open())) if path.exists() else []

def measure(phase,name,variant,t,r,sample):
    key=(phase,name,variant,str(t),str(r),str(sample))
    if any(tuple(row[k] for k in FIELDS[:6])==key for row in records()): return
    tag=f'{phase}-{name}-{variant}-t{t}-r{r}-s{sample}'
    cmd=command(variant,name,r)
    resource=HERE/f'raw/{tag}.resource.json'
    full=['/usr/bin/time','-f','{"wall_s":%e,"max_rss_kib":%M,"major_faults":%F}', '-o',str(resource),*cmd]
    save(f'raw/{tag}.command.json',{'argv':full,'environment':{k:v for k,v in env(t).items() if k.startswith(('OMP_','GOMP_'))}})
    p=subprocess.run(full,env=env(t),text=True,capture_output=True,timeout=900)
    (HERE/f'raw/{tag}.stdout.txt').write_text(p.stdout)
    (HERE/f'raw/{tag}.stderr.txt').write_text(p.stderr)
    p.check_returncode()
    match=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',p.stdout)
    assert match,p.stdout
    seconds=float(match[1]); assert int(match[2])==r
    prep=re.search(r'spmv_prepare: ([\d.]+) seconds requested=(\S+) selected=(\S+) reason=(\S+) chunk=(\d+) slots=(\d+) extra_bytes=(\d+)',p.stdout)
    usage=json.loads(resource.read_text())
    row=dict(phase=phase,matrix=name,variant=variant,threads=t,repeat=r,sample=sample,
             execute_s=seconds,ms_per_spmv=seconds*1000/r,prepare_s=float(prep[1]) if prep else 0,
             selected=prep[3] if prep else 'original',reason=prep[4] if prep else 'original-source',
             extra_bytes=int(prep[7]) if prep else 0, slots=int(prep[6]) if prep else 0,
             **usage,command_file=f'raw/{tag}.command.json')
    path=HERE/'measurements.csv'; exists=path.exists()
    with path.open('a',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n')
        if not exists:writer.writeheader()
        writer.writerow(row)
    print(f'{tag}: {row["ms_per_spmv"]:.3f} ms, P={row["prepare_s"]:.3f}s, {row["selected"]}/{row["reason"]}',flush=True)

def run_phase(phase):
    if phase=='pilot':
        jobs=[('random8',v,t,9) for v in PRIMARY for t in [1,12,24]]; samples=1
    elif phase=='formal':
        jobs=[(n,v,12,100 if n in ['zero','cache-small','wide'] else 9) for n,*_ in CASES for v in PRIMARY]
        multi=['random1','random8','random256','banded8','hot8','heavy-clustered','heavy-scattered','giant-row','empty99','cache-small']
        jobs += [(n,v,t,100 if n=='cache-small' else 9) for n in multi for v in PRIMARY for t in [1,24]]
        # Source unchanged dispatcher overhead, and original full-build novec.
        jobs += [('random8',v,t,9) for v in ['original-novec','v1-original'] for t in [1,12,24]]
        samples=5
    elif phase=='large':
        jobs=[('large',v,t,9) for v in PRIMARY for t in [1,12,24]]
        jobs += [('large','original-novec',24,9),('large','v1-original',24,9)]
        samples=5
    elif phase=='amortization':
        jobs=[('large',v,24,r) for v in ['original','sell8','sell16'] for r in [1,100]]
        samples=5
    else: raise ValueError(phase)
    rng=random.Random(SEED+sum(map(ord,phase)))
    # Every round contains all conditions, in fixed shuffled order.
    for sample in range(1,samples+1):
        order=jobs.copy();rng.shuffle(order)
        for name,variant,t,r in order:measure(phase,name,variant,t,r,sample)
    summarize()

def summarize():
    groups={}
    for row in records():
        if row['phase']=='pilot':continue
        key=tuple(row[k] for k in ['phase','matrix','variant','threads','repeat'])
        groups.setdefault(key,[]).append(row)
    summary=[]
    for key,rows in sorted(groups.items()):
        ms=[float(r['ms_per_spmv']) for r in rows]
        item=dict(zip(['phase','matrix','variant','threads','repeat'],key))
        item.update(samples=len(rows),median_ms=statistics.median(ms),min_ms=min(ms),max_ms=max(ms),
                    prepare_median_s=statistics.median(float(r['prepare_s']) for r in rows),
                    compute_total_median_s=statistics.median(float(r['prepare_s'])+float(r['execute_s']) for r in rows),
                    wall_median_s=statistics.median(float(r['wall_s']) for r in rows),
                    peak_rss_kib=max(int(r['max_rss_kib']) for r in rows),
                    extra_bytes=max(int(r['extra_bytes']) for r in rows),
                    selected=','.join(sorted({r['selected'] for r in rows})),
                    reason=','.join(sorted({r['reason'] for r in rows})))
        summary.append(item)
    save('summary.json',summary)
    if summary:
        with (HERE/'summary.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(summary[0]),lineterminator='\n');writer.writeheader();writer.writerows(summary)
    print('summary:',len(summary),'conditions;',len(records()),'process records',flush=True)

if __name__=='__main__':
    stage=sys.argv[1]
    if stage in ['build','generate','correctness','summarize']:globals()[stage]()
    else:run_phase(stage)
