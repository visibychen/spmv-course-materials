#!/usr/bin/env python3
"""Input provenance and independent correctness; separate from timing."""
from pathlib import Path
import gzip,json,subprocess,urllib.request
import numpy as np
import run_experiments as run
H=run.HERE
def synthetic(name,m,n,length,profile='iid',group='heldout'):
    path=H/f'data/{name}.mtx';expected=H/f'data/{name}.expected.f32'
    rng=np.random.default_rng(20261026+sum(map(ord,name)));counts=[];sums=[]
    with path.open('w') as f:
        for i in range(m):
            l=length
            if profile=='two-giants':l=200003 if i==0 else 100003 if i==m//2 else 1
            if profile=='empty-cluster':l=16 if i<3000 else 0
            if profile=='longtail':l=512 if i<1000 else 3
            counts.append(l)
        f.write(f'%%MatrixMarket matrix coordinate real general\n% v2 generated seed; independent per-row uniform column samples\n{m} {n} {sum(counts)}\n')
        for i,l in enumerate(counts):
            cols=np.sort(rng.choice(n,size=l,replace=False))
            vals=rng.integers(1,5,size=l).astype(np.float32)*np.float32(.25)
            sums.append(np.sum(vals,dtype=np.float32))
            f.writelines(f'{i+1} {int(j)+1} {float(v):.2f}\n' for j,v in zip(cols,vals))
    np.array(sums,dtype=np.float32).tofile(expected)
    return dict(name=name,path=str(path),group=group,rows=m,columns=n,nonzeros=sum(counts),
        sha256=run.sha(path),expected_path=str(expected),expected_sha256=run.sha(expected),
        seed=20261026+sum(map(ord,name)),profile=profile,license='project-generated; same GPL-3.0-or-later as generator')
def inputs():
    old=json.loads((run.OLD/'matrices.json').read_text());records=[]
    for x in old:
        path=run.BASE/'data/large_random.mtx' if x['name']=='large' else run.OLD/f'data/{x["name"]}.mtx'
        expected=run.BASE/'data/large_expected.f32' if x['name']=='large' else run.OLD/f'data/{x["name"]}.expected.f32'
        assert run.sha(path)==x['sha256'],path
        assert run.sha(expected)==x['expected_sha256'],expected
        records.append(dict(name=x['name'],path=str(path),expected_path=str(expected),group='v1',
            rows=x['rows'],columns=x['columns'],nonzeros=x['nonzeros'],sha256=x['sha256'],
            expected_sha256=x['expected_sha256'],provenance='../2026-10-25-v1/matrices.json'))
    for args in [
      ('calibration-small',1024,2053,8,'iid','calibration'),
      ('calibration-medium',4096,8191,8,'iid','calibration'),
      ('heldout-iid8',100003,15000007,8),('heldout-iid9',8193,1000003,9),
      ('heldout-two-giants',10003,300007,1,'two-giants'),
      ('heldout-empty-cluster',120003,300007,0,'empty-cluster'),
      ('heldout-longtail',50003,2000003,3,'longtail'),
      ('heldout-small',1027,2053,8),('heldout-medium',8195,16381,8)]:
        records.append(synthetic(*args))
    for collection,name in [('bcsstruc2','bcsstk18'),('sherman','sherman5')]:
        archive=H/f'data/nist-{name}.mtx.gz'
        url=f'https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/{collection}/{name}.mtx.gz'
        if not archive.exists():
            req=urllib.request.Request(url,headers={'User-Agent':'SpMV-course-research/2'})
            with urllib.request.urlopen(req,timeout=60) as response,archive.open('wb') as out:
                while block:=response.read(1024*1024):out.write(block)
        path=H/f'data/{name}.mtx'
        with gzip.open(archive,'rb') as f:path.write_bytes(f.read())
        header=[]
        with path.open() as f:
            first=next(f).strip();header.append(first)
            for l in f:
                header.append(l.rstrip())
                if not l.startswith('%'):dims=list(map(int,l.split()));break
        records.append(dict(name=name,path=str(path),group='real',rows=dims[0],columns=dims[1],
            nonzeros=dims[2],stored_nonzeros=dims[2],sha256=run.sha(path),archive_sha256=run.sha(archive),
            field=first.split()[3],symmetry=first.split()[4],expand_symmetric=first.split()[4]!='general',
            url=url,metadata_url=f'https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/{collection}/{name}.html',
            accessed_on='2026-10-26',license='No standalone license stated on NIST matrix page; used locally, not redistributed.',
            matrix_header=header,download_method='Windows curl.exe --fail --location --retry 2 --max-time 60 URL --output LOCAL_GZIP',
            citation='NIST Matrix Market, Harwell-Boeing collection; original contributors Prof Mac Will (bcsstk18) and Andy Sherman (sherman5).',
            modifications='Decompressed MTX bytes unchanged; runtime f32 conversion and symmetric expansion reported.'))
        print('real input',name,path.stat().st_size,flush=True)
    run.save('matrices.json',records);print('inputs',len(records),flush=True)
def reference(meta):
    path=Path(meta['path'])
    if 'expected_path' in meta:return np.fromfile(meta['expected_path'],dtype=np.float32)*np.float32(3),None
    coords=np.loadtxt(path,comments='%',skiprows=len(meta['matrix_header']),ndmin=2)
    ri=coords[:,0].astype(np.int64)-1;ci=coords[:,1].astype(np.int64)-1
    vv=coords[:,2].astype(np.float32).astype(np.float64)
    sums=np.bincount(ri,weights=vv,minlength=meta['rows']);ab=np.bincount(ri,weights=np.abs(vv),minlength=meta['rows'])
    count=np.bincount(ri,minlength=meta['rows'])
    if meta['expand_symmetric']:
        off=ri!=ci
        sums+=np.bincount(ci[off],weights=vv[off],minlength=meta['rows'])
        ab+=np.bincount(ci[off],weights=np.abs(vv[off]),minlength=meta['rows'])
        count+=np.bincount(ci[off],minlength=meta['rows'])
    meta['expanded_nonzeros_verified']=int(count.sum())
    return sums*3,(count+8)*np.finfo(np.float32).eps*ab*12+1e-30
def verify():
    results=[];commands=[]
    sources=[str(run.CORE/'src'/n) for n in ['csr.c','matrix_market.c','vector.c','parse.c','spmv_plan.c','spmv_v2.c']]
    for label,flags,threads in [('native',['-O3','-march=native'],[1,12,24]),
          ('portable',['-O3'],[12]),('sanitize',['-O1','-march=native','-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie'],[1,12,24])]:
        binary=H/f'build/test-{label}'
        cmd=['gcc','-g','-Wall','-fopenmp','-ffp-contract=off','-iquote',str(run.CORE/'src'),
          str(run.CORE/'tests/test_spmv_v2.c'),*sources,*flags,'-Wl,--wrap=malloc','-lm','-o',str(binary)]
        p=subprocess.run(cmd,text=True,capture_output=True);(H/f'raw/test-build-{label}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
        commands.append(dict(label=label,command=cmd,binary_sha256=run.sha(binary)))
        for t in threads:
            e=run.env(t);e['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
            p=subprocess.run([str(binary)],env=e,capture_output=True,text=True,timeout=180)
            (H/f'raw/test-{label}-{t}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
            assert '5368 checks' in p.stdout and not p.stderr
            results.append(dict(kind=label,threads=t,stdout=p.stdout,exit=p.returncode));print(label,t,p.stdout.strip(),flush=True)
    run.save('verification-builds.json',commands)
    metas=run.matrices()
    for meta in metas:
        if meta['group']=='calibration':continue
        n=meta['name'];ref,bound=reference(meta)
        variants=['v2-auto','v2-csr-work','v2-merge','v2-short128']
        if meta['group']=='real':variants+=['original']
        for variant in variants:
            out=H/'data/check-output.mtx';cmd=run.command(variant,n,3,out)
            p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,timeout=300)
            (H/f'raw/correct-{n}-{variant}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
            got=run.vector(out);assert got.shape==ref.shape
            error=np.abs(got.astype(np.float64)-ref)
            assert np.all(error<=(bound if bound is not None else 0)),(n,variant,float(error.max()))
            results.append(dict(kind='full-output',matrix=n,variant=variant,threads=12,repeat=3,
                values=int(got.size),max_absolute_error=float(error.max(initial=0)),exact=bound is None))
            out.unlink();run.save('correctness.json',results);print('correct',n,variant,flush=True)
    # Existing original behavior for supported types and symmetric expansion.
    path=H/'data/typed.mtx';outputs=[H/f'data/typed-{i}.mtx' for i in [0,1]]
    for field,values in [('real',['1.25','-2.5','3']),('integer',['1','-2','3']),('complex',['1 2','-2 1','3 -1']),('pattern',['','',''])]:
        for dtype in (['f32','f64'] if field=='real' else [None]):
            for sym in ['general','symmetric']:
                path.write_text(f'%%MatrixMarket matrix coordinate {field} {sym}\n3 3 3\n'+''.join(f'{r} {c} {v}'.rstrip()+'\n' for r,c,v in zip([1,2,3],[1,1,2],values)))
                for i,v in enumerate(['original','v2-auto']):
                    folder,opts=run.VARIANTS[v];cmd=[str(H/'build'/folder/'csrspmv'),str(path),*opts,'--repeat=3','--destination-vector='+str(outputs[i])]
                    if sym=='symmetric':cmd+=['--include-symmetric-part']
                    if dtype:cmd += ['--matrix-format='+dtype,'--source-vector-format='+dtype,'--destination-vector-format='+dtype]
                    p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,timeout=15);p.check_returncode()
                def data(p):return [l for l in p.read_text().splitlines() if not l.startswith('%')]
                assert data(outputs[0])==data(outputs[1]);results.append(dict(kind='compatibility',field=field,dtype=dtype,symmetry=sym))
    for flag in ['--v2-kernel=bad','--partition=bad','--execution=bad','--prefetch=1','--prefetch=32garbage','--serial-threshold=-1','--repeat=-1','--flops=-1','--plan-memory-mib=-1','--v2-kernel','--partition','--execution']:
        cmd=run.command('v2-auto','cache-small',1)+[flag]
        p=subprocess.run(cmd,env=run.env(1),capture_output=True,text=True,timeout=10);assert p.returncode!=0,flag
        results.append(dict(kind='invalid-option',option=flag,exit=p.returncode))
    for opts in [['--v2-kernel=merge','--strict-order'],['--v2-kernel=merge','--partition=work']]:
        p=subprocess.run(run.command('v2-auto','cache-small',1)+opts,env=run.env(1),capture_output=True,text=True,timeout=10);assert p.returncode!=0
        results.append(dict(kind='invalid-combination',options=opts,exit=p.returncode))
    p=subprocess.run(run.command('v2-auto','zero',1)+['--flops=1'],env=run.env(1),capture_output=True,text=True,timeout=5);assert p.returncode!=0
    results.append(dict(kind='zero-positive-flops',exit=p.returncode))
    for r in [0,1,3]:
        out=H/'data/cli-count.mtx';p=subprocess.run(run.command('v2-auto','cache-small',r,out),env=run.env(24),capture_output=True,text=True,timeout=10);p.check_returncode()
        ref=np.fromfile(run.matrix('cache-small')['expected_path'],dtype=np.float32)*np.float32(r)
        assert np.array_equal(run.vector(out),ref);results.append(dict(kind='repeat-count',repeat=r));out.unlink()
    for p in [path,*outputs]:p.unlink()
    run.save('correctness.json',results);run.save('matrices.json',metas)
    print('verified',len(results),'records',flush=True)
