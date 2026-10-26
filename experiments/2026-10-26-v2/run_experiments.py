#!/usr/bin/env python3
"""Sequential WSL experiments; raw records append-only and resumable.
python3 run_experiments.py build|inputs|verify|pilot|screen|heldout|large|summarize
No concurrent benchmarks. Builds original/v1 from fixed git archives, v2
from the isolated master-based working tree. Large input is reused by SHA.
"""
import csv,hashlib,io,json,os,random,re,shutil,statistics,subprocess,sys,tarfile,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
MATERIALS=HERE.parents[1];CORE=MATERIALS.parent/'csrspmv'
OLD=MATERIALS/'experiments/2026-10-25-v1'
BASE=MATERIALS/'experiments/2026-10-25-baseline'
ORIGINAL='9352c865044f4c8b344d6fe5a277200a89f7a08b'
V1='f089579a489723547a354459d591c551a313c4bb'
FLAGS='-O3 -march=native -g -Wall -iquote src -fopenmp'
for d in ['build','data','raw']:(HERE/d).mkdir(exist_ok=True)
def save(name,obj): (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def env(t):
    e={k:v for k,v in os.environ.items() if not k.startswith(('OMP_','GOMP_'))}
    e.update(OMP_NUM_THREADS=str(t),OMP_DYNAMIC='FALSE',OMP_PLACES='cores',
             OMP_PROC_BIND='spread',OMP_WAIT_POLICY='PASSIVE',LC_ALL='C')
    return e
VARIANTS={
 'original':('original',[]),'original-novec':('original-novec',[]),
 'v1-scalar':('v1',['--kernel=csr-scalar']),
 'v1-sell16':('v1',['--kernel=sell','--sell-chunk=16']),
 'v1-pack':('v1',['--kernel=csr-pack']),
 'v2-original':('v2',['--kernel=original']),
 'v2-auto':('v2',['--kernel=v2']),
 'v2-csr-rows':('v2',['--kernel=v2','--v2-kernel=csr','--partition=rows','--execution=parallel']),
 'v2-csr-work':('v2',['--kernel=v2','--v2-kernel=csr','--partition=work','--execution=parallel']),
 'v2-merge':('v2',['--kernel=v2','--v2-kernel=merge','--execution=parallel']),
 'v2-short0':('v2',['--kernel=v2','--v2-kernel=short8','--execution=parallel']),
 'v2-short32':('v2',['--kernel=v2','--v2-kernel=short8','--execution=parallel','--prefetch=32']),
 'v2-short128':('v2',['--kernel=v2','--v2-kernel=short8','--execution=parallel','--prefetch=128']),
 'v2-serial':('v2',['--kernel=v2','--execution=serial']),
}
def build():
    records={}
    for name in ['original','original-novec','v1','v2']:
        dest=HERE/'build'/name;dest.mkdir(exist_ok=True)
        if name!='v2':
            data=subprocess.check_output(['git','archive',V1 if name=='v1' else ORIGINAL],cwd=CORE)
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:tf.extractall(dest)
        else:
            for p in list((CORE/'src').glob('*.c'))+list((CORE/'src').glob('*.h'))+[CORE/'Makefile']:
                out=dest/p.relative_to(CORE);out.parent.mkdir(exist_ok=True);shutil.copyfile(p,out)
            shutil.copytree(CORE/'tests',dest/'tests',dirs_exist_ok=True)
        subprocess.run(['make','clean'],cwd=dest,check=True,capture_output=True)
        flags=FLAGS+(' -fno-tree-loop-vectorize -fno-tree-slp-vectorize' if name=='original-novec' else '')
        cmd=['make','-j12','CFLAGS='+flags+' -fopt-info-vec-all='+str(HERE/f'raw/vectorization-{name}.txt')]
        p=subprocess.run(cmd,cwd=dest,text=True,capture_output=True)
        (HERE/f'raw/build-{name}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
        records[name]=dict(command=cmd,flags=flags,binary_sha256=sha(dest/'csrspmv'))
        for fn in (['spmv_v2_execute','rows_f32','merge_f32'] if name=='v2' else []):
            p=subprocess.run(['objdump','-d','-M','intel','--disassemble='+fn,str(dest/'csrspmv')],capture_output=True,text=True,check=True)
            (HERE/f'raw/assembly-{fn}.txt').write_text(p.stdout)
    save('build.json',records)
    source={str(p.relative_to(CORE)):sha(p) for p in sorted(CORE.rglob('*'))
            if p.is_file() and '.git' not in p.parts and p.suffix in ['.c','.h']}
    source['Makefile']=sha(CORE/'Makefile')
    save('source-provenance.json',dict(original_commit=ORIGINAL,v1_commit=V1,
        v2_branch=subprocess.check_output(['git','branch','--show-current'],cwd=CORE,text=True).strip(),
        v2_base=subprocess.check_output(['git','merge-base','HEAD','master'],cwd=CORE,text=True).strip(),
        source_sha256=source,runner_sha256=sha(Path(__file__))))
    er={}
    for cmd in [['lscpu'],['uname','-a'],['gcc','--version'],['free','-b'],['git','status','--short']]:
        er[' '.join(cmd)]=subprocess.check_output(cmd,cwd=CORE,text=True)
    er['omp']={k:v for k,v in env(12).items() if k.startswith('OMP_')}
    er['date']='2026-10-26 Asia/Shanghai';er['unix_start']=time.time();save('environment.json',er)
    print('built',list(records),flush=True)
def matrices():return json.loads((HERE/'matrices.json').read_text())
def matrix(n):return next(x for x in matrices() if x['name']==n)
def command(v,n,r,out=None):
    folder,opts=VARIANTS[v];meta=matrix(n)
    cmd=[str(HERE/'build'/folder/'csrspmv'),meta['path'],*opts,
       '--matrix-format=f32','--source-vector-format=f32','--destination-vector-format=f32',
       '--repeat='+str(r),'-v']
    if meta.get('expand_symmetric'):cmd+=['--include-symmetric-part']
    if out:cmd+=['--destination-vector='+str(out),'--destination-vector-prec=9']
    return cmd
def vector(p):
    with Path(p).open() as f:
        for line in f:
            if not line.startswith('%'):dims=list(map(int,line.split()));break
        a=np.loadtxt(f,dtype=np.float32,ndmin=1)
    assert len(a)==dims[0];return a
FIELDS=['phase','matrix','variant','threads','repeat','sample','pair','order',
 'execute_s','prepare_s','cleanup_s','total_s','wall_s','max_rss_kib','major_faults',
 'actual_threads','selected','partition','reason','extra_bytes','row_scan_s','column_validation_s','policy_s','command_file']
def records():
    p=HERE/'measurements.csv';return list(csv.DictReader(p.open())) if p.exists() else []
def measure(phase,n,v,t,r,s,pair='',order=''):
    key=(phase,n,v,str(t),str(r),str(s))
    if any(tuple(x[k] for k in FIELDS[:6])==key for x in records()):return
    tag=f'{phase}-{n}-{v}-t{t}-r{r}-s{s}'
    resource=HERE/f'raw/{tag}.resource.json';cmd=command(v,n,r)
    full=['/usr/bin/time','-f','{"wall_s":%e,"max_rss_kib":%M,"major_faults":%F}','-o',str(resource),*cmd]
    save(f'raw/{tag}.command.json',dict(argv=full,environment={k:v for k,v in env(t).items() if k.startswith('OMP_')}))
    p=subprocess.run(full,env=env(t),capture_output=True,text=True,timeout=1200)
    (HERE/f'raw/{tag}.stdout.txt').write_text(p.stdout);(HERE/f'raw/{tag}.stderr.txt').write_text(p.stderr);p.check_returncode()
    e=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',p.stdout)
    assert e and int(e[2])==r,(tag,p.stdout)
    prep=re.search(r'spmv_prepare: ([\d.]+).*selected=(\S+) reason=(\S+).*extra_bytes=(\d+)',p.stdout)
    info=re.search(r'spmv_v2: (.*)',p.stdout);info=dict(re.findall(r'(\w+)=(\S+)',info[1])) if info else {}
    cleanup=re.search(r'spmv_cleanup: ([\d.]+)',p.stdout)
    team=re.search(r'spmv_team: actual_threads=(\d+)',p.stdout)
    ps=float(prep[1]) if prep else 0;cs=float(cleanup[1]) if cleanup else 0
    row=dict(phase=phase,matrix=n,variant=v,threads=t,repeat=r,sample=s,pair=pair,order=order,
       execute_s=float(e[1]),prepare_s=ps,cleanup_s=cs,total_s=float(e[1])+ps+cs,
       **json.loads(resource.read_text()),actual_threads=int(team[1]) if team else t,
       selected=info.get('kernel',prep[2] if prep else 'original'),partition=info.get('partition','original'),
       reason=prep[3] if prep else 'original-source',extra_bytes=int(prep[4]) if prep else 0,
       row_scan_s=info.get('row_scan_s',0),column_validation_s=info.get('column_validation_s',0),
       policy_s=info.get('policy_s',0),command_file=f'raw/{tag}.command.json')
    f=HERE/'measurements.csv';exists=f.exists()
    with f.open('a',newline='') as o:
        w=csv.DictWriter(o,fieldnames=FIELDS,lineterminator='\n')
        if not exists:w.writeheader()
        w.writerow(row)
    print(tag,f'E={float(e[1])*1000/r:.4f}ms P={ps*1000:.3f}ms total={row["total_s"]:.6f}s',row['selected'],row['actual_threads'],flush=True)
def phase(name):
    rng=random.Random(20261026+sum(map(ord,name)))
    if name=='pilot':
        jobs=[(n,v,t,100) for n in ['cache-small','wide','calibration-small','calibration-medium']
              for v in ['original','v2-auto','v2-serial','v2-short0'] for t in [1,12,24]]
        jobs += [('random8',v,t,9) for v in ['original','v2-auto','v2-short32','v2-short128'] for t in [1,12,24]]
        samples=3
    elif name=='screen':
        jobs=[(x['name'],v,12,100 if x['name'] in ['zero','cache-small','wide'] else 9)
              for x in matrices() if x['group']=='v1' and x['name']!='large'
              for v in ['original','v1-scalar','v1-sell16','v2-auto']]
        jobs += [(n,v,12,9) for n in ['random8','banded8','hot8']
                 for v in ['v2-short0','v2-short32','v2-short128']]
        jobs += [(n,v,t,9) for n in ['heavy-clustered','heavy-scattered','giant-row','empty99']
                 for v in ['v2-csr-rows','v2-csr-work','v2-merge'] for t in [12,24]]
        jobs += [(n,v,24,9) for n in ['heavy-clustered','giant-row','empty99']
                 for v in ['original','v2-auto']]
        jobs += [('giant-row','v1-pack',t,9) for t in [12,24]]
        jobs += [('random256','v1-pack',12,9)]
        samples=5
    elif name=='heldout':
        jobs=[(x['name'],v,t,100 if x['nonzeros']<20000 else 9)
               for x in matrices() if x['group'] in ['heldout','real']
               for v in ['original','v1-scalar','v1-sell16','v2-auto'] for t in [1,12,24]]
        jobs += [('heldout-two-giants','v1-pack',t,9) for t in [1,12,24]]
        samples=5
    elif name=='large':
        # Adjacent AB/BA process pairs. P and all samples retained.
        conditions=[(t,r) for t in [1,12,24] for r in [1,9,100]]
        for s in range(1,11):
            rng.shuffle(conditions)
            for t,r in conditions:
                order=['original','v2-auto'];rng.shuffle(order)
                for rank,v in enumerate(order):measure(name,'large',v,t,r,s,f'{t}-{r}-{s}',rank)
        # Additional matched controls, separate from the primary pairs.
        for s in range(1,6):
            jobs=[('large',v,t,9) for t in [1,12,24] for v in ['v1-scalar','v1-sell16','v2-original','original-novec','v2-csr-rows']]
            rng.shuffle(jobs)
            for n,v,t,r in jobs:measure('large-controls',n,v,t,r,s)
        summarize();return
    else:raise ValueError(name)
    for s in range(1,samples+1):
        rng.shuffle(jobs)
        for n,v,t,r in jobs:measure(name,n,v,t,r,s)
    summarize()
def summarize():
    groups={}
    for x in records():groups.setdefault(tuple(x[k] for k in FIELDS[:5]),[]).append(x)
    result=[]
    for key,rows in sorted(groups.items()):
        item=dict(zip(FIELDS[:5],key));item['samples']=len(rows)
        for n in ['execute_s','prepare_s','cleanup_s','total_s','wall_s']:
            a=[float(x[n]) for x in rows];item[n+'_median']=statistics.median(a)
            if n=='total_s':item['total_s_min']=min(a);item['total_s_max']=max(a)
        item['ms_per_call']=1000*item['execute_s_median']/int(item['repeat'])
        item['selected']=','.join(sorted({x['selected'] for x in rows}))
        item['partition']=','.join(sorted({x['partition'] for x in rows}))
        item['actual_threads']=','.join(sorted({x['actual_threads'] for x in rows}))
        item['extra_bytes']=max(int(x['extra_bytes']) for x in rows)
        item['peak_rss_kib']=max(int(x['max_rss_kib']) for x in rows)
        result.append(item)
    save('summary.json',result)
    if result:
        with (HERE/'summary.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(result[0]),lineterminator='\n');w.writeheader();w.writerows(result)
    print('SUMMARY',len(result),'conditions;',len(records()),'processes',flush=True)
if __name__=='__main__':
    stage=sys.argv[1]
    if stage in ['build','summarize']:globals()[stage]()
    elif stage in ['inputs','verify']:
        from verify_and_inputs import inputs,verify
        globals()[stage]()
    else:phase(stage)
