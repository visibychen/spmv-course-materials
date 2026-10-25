#!/usr/bin/env python3
"""Run after performance sampling: compatibility checks and evidence audit."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np
import run_experiments as run

HERE=run.HERE

def compatibility():
    rows=[]
    matrix=HERE/'data/compatibility.mtx'
    out0=HERE/'data/compatibility-original.mtx'
    out1=HERE/'data/compatibility-v1.mtx'
    for mtype in ['f32','f64','int32','int64','binary','complex32']:
        field='complex' if mtype=='complex32' else 'real'
        vals=['1 2','-2 1','3 -1'] if field=='complex' else ['1','-2','3']
        matrix.write_text(f'%%MatrixMarket matrix coordinate {field} general\n3 3 3\n'+
                          ''.join(f'{i+1} {i+1} {v}\n' for i,v in enumerate(vals)))
        for xtype,ytype in [('f32','f32'),('f32','f64'),('f64','f32'),('f64','f64'),('complex32','complex32')]:
            pair=[]
            for variant,out in [('original',out0),('sell16',out1)]:
                folder,opts=run.VARIANTS[variant]
                cmd=[str(HERE/'build'/folder/'csrspmv'),str(matrix),*opts,
                     '--matrix-format='+mtype,'--source-vector-format='+xtype,
                     '--destination-vector-format='+ytype,'--repeat=3','--destination-vector='+str(out)]
                p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,timeout=10)
                pair.append(p)
            assert pair[0].returncode==pair[1].returncode,(mtype,xtype,ytype)
            if not pair[0].returncode:
                def body(p):return [s for s in p.read_text().splitlines() if not s.startswith('%')]
                assert body(out0)==body(out1),(mtype,xtype,ytype)
            rows.append(dict(matrix_type=mtype,x_type=xtype,y_type=ytype,original_exit=pair[0].returncode,
                             v1_exit=pair[1].returncode,output_same=not pair[0].returncode))
    # A real symmetric input large enough that BOTH SELL paths actually run.
    m=64; entries=[(i,i,2.0) for i in range(m)]+[(i,i-1,-0.5) for i in range(1,m)]
    matrix.write_text(f'%%MatrixMarket matrix coordinate real symmetric\n{m} {m} {len(entries)}\n'+
                      ''.join(f'{i+1} {j+1} {v}\n' for i,j,v in entries))
    a=np.zeros((m,m),dtype=np.float32)
    for i,j,v in entries:
        a[i,j]+=v
        if i!=j:a[j,i]+=v
    ref=(a@np.ones(m,dtype=np.float32))*3
    for variant in run.PRIMARY:
        folder,opts=run.VARIANTS[variant]
        cmd=[str(HERE/'build'/folder/'csrspmv'),str(matrix),*opts,'--include-symmetric-part',
             '--repeat=3','-v','--destination-vector='+str(out1)]
        p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,check=True)
        if variant.startswith('sell'):assert 'selected=sell reason=selected' in p.stdout
        assert np.array_equal(run.read_vector(out1),ref)
        rows.append(dict(symmetric_full=True,variant=variant,max_absolute_error=0,stdout=p.stdout))
    for p in [matrix,out0,out1]:
        if p.exists():p.unlink()
    run.save('correctness-compatibility.json',rows)
    return len(rows)

def audit():
    rows=run.records()
    assert len(rows)==1210,len(rows)
    groups={}
    failures=[]
    for row in rows:
        key=tuple(row[k] for k in run.FIELDS[:5]);groups.setdefault(key,[]).append(row)
        tag=Path(row['command_file']).name.removesuffix('.command.json')
        text=(HERE/f'raw/{tag}.stdout.txt').read_text()
        assert not (HERE/f'raw/{tag}.stderr.txt').read_text()
        match=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',text)
        assert match and float(match[1])==float(row['execute_s'])
        assert int(match[2])==int(row['repeat'])
        meta=json.loads((HERE/row['command_file']).read_text())
        assert meta['environment']['OMP_NUM_THREADS']==row['threads']
        assert meta['environment']['OMP_PROC_BIND']=='spread'
        assert meta['environment']['OMP_WAIT_POLICY']=='PASSIVE'
    for key,rs in groups.items():
        assert len(rs)==(1 if key[0]=='pilot' else 5),(key,len(rs))
        assert len({(r['selected'],r['reason']) for r in rs})==1,(key,'mixed backend selection')
    provenance=json.loads((HERE/'source-provenance.json').read_text())
    git_path=HERE/'git-provenance.json'
    code_commit=json.loads(git_path.read_text())['core']['commit'] if git_path.exists() else None
    for name,digest in provenance['source_sha256'].items():
        if code_commit:
            blob=subprocess.check_output(['git','-C',str(run.CORE),'show',f'{code_commit}:{name}'])
            actual=hashlib.sha256(blob).hexdigest()
        else: actual=run.sha(run.CORE/name)
        assert actual==digest,name
    for name,meta in json.loads((HERE/'build.json').read_text()).items():
        assert run.sha(HERE/'build'/name/'csrspmv')==meta['binary_sha256']
    matrices=json.loads((HERE/'matrices.json').read_text())
    large=next(x for x in matrices if x['name']=='large')
    assert large['sha256']=='973866b437cfbd85a863432924093229aa89bed4c12047a0c09c7120504fb373'
    assert large['expected_sha256']=='f2112ee61fb3fd1b10bda644433785eebe3d29df7f2a873b7a42df90d71f32d9'
    for item in matrices:
        assert run.sha(run.matrix(item['name']))==item['sha256']
        assert run.sha(run.expected(item['name']))==item['expected_sha256']
    # Preserve upstream original branch, and verify large data/build exclusions.
    master=subprocess.check_output(['git','-C',str(run.CORE),'rev-parse','master'],text=True).strip()
    assert master==run.ORIGINAL
    for name in ['build/v1/csrspmv','data/random8.mtx']:
        assert subprocess.run(['git','-C',str(run.MATERIALS),'check-ignore','-q',str(HERE/name)]).returncode==0
    sanitize=json.loads((HERE/'correctness-sanitize.json').read_text())
    assert len(sanitize)==3 and all(x['exit']==0 and not x['stderr'] and '850 checks' in x['stdout'] for x in sanitize)
    additional=compatibility()
    result=dict(passed=True,process_samples=len(rows),conditions=len(groups),
                formal_conditions=sum(key[0]!='pilot' for key in groups),
                matrices=len(matrices),source_hashes_checked=len(provenance['source_sha256']),
                original_master=master,correctness_checks=len(json.loads((HERE/'correctness.json').read_text())),
                source_snapshot_commit=code_commit,
                additional_compatibility=additional,sanitizer_checks=3*850,
                max_major_faults=max(int(r['major_faults']) for r in rows),
                notes=['5 independent processes per formal condition; 1 per pilot',
                       'interval separation is descriptive, not a statistical hypothesis test',
                       'no benchmark results discarded; no synthetic warm-up inserted'])
    run.save('audit.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':audit()
