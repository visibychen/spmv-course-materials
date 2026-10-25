#!/usr/bin/env python3
"""Read-only v1 reanalysis: arithmetic and work-count models, NOT new timings."""
from pathlib import Path
import csv
import hashlib
import json
import math
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
MATERIALS=HERE.parents[1]
V1=MATERIALS/'experiments/2026-10-25-v1'
SUMMARY=json.loads((V1/'summary.json').read_text())

def get(matrix,variant,t=24,r=9):
    found=[x for x in SUMMARY if x['matrix']==matrix and x['variant']==variant
           and int(x['threads'])==t and int(x['repeat'])==r]
    assert len(found)==1,(matrix,variant,t,r)
    return found[0]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def counts(name):
    if name=='large':return 12000000,lambda i:8*i,8
    if name=='heavy-clustered':return 100000,lambda i:1024*min(i,1000)+4*max(i-1000,0),1024
    if name=='heavy-scattered':return 100000,lambda i:4*i+1020*((i+99)//100),1024
    if name=='giant-row':return 100000,lambda i:0 if not i else 1000000+i-1,1000000
    if name=='empty99':return 1000000,lambda i:8*((i+99)//100),8
    raise ValueError(name)

def balanced_targets(total,threads):
    q,r=divmod(total,threads)
    return [q*t+min(t,r) for t in range(threads+1)]

def lower_bound(m,prefix,target):
    lo,hi=0,m
    while lo<hi:
        mid=(lo+hi)//2
        if prefix(mid)+mid<target:lo=mid+1
        else:hi=mid
    return lo

def workload_models():
    result=[]
    for name in ['large','heavy-clustered','heavy-scattered','giant-row','empty99']:
        m,prefix,longest=counts(name);nnz=prefix(m)
        for threads in [12,24]:
            for method in ['static_rows','nnz_plus_rows_lambda1']:
                boundaries=(balanced_targets(m,threads) if method=='static_rows' else
                    [lower_bound(m,prefix,t) for t in balanced_targets(m+nnz,threads)])
                rs=[b-a for a,b in zip(boundaries,boundaries[1:])]
                nz=[prefix(b)-prefix(a) for a,b in zip(boundaries,boundaries[1:])]
                assert sum(rs)==m and sum(nz)==nnz and min(rs)>=0 and min(nz)>=0
                work=[r+n for r,n in zip(rs,nz)]
                result.append(dict(matrix=name,threads=threads,model=method,rows=m,nonzeros=nnz,
                    max_thread_rows=max(rs),max_thread_nnz=max(nz),nnz_max_over_mean=max(nz)/(nnz/threads),
                    weighted_work_max_over_mean=max(work)/((m+nnz)/threads),
                    longest_row_nnz=longest,whole_row_nnz_lower_bound=max(1,longest/(nnz/threads)),
                    merge_model_max_events=math.ceil((m+nnz)/threads)))
    return result

def object_text_comparison():
    records={}
    for variant in ['original','v1']:
        obj=V1/'build'/variant/'src/csr.o'
        if not obj.exists():return {'available':False,'reason':'local ignored build artifacts absent'}
        with tempfile.TemporaryDirectory(prefix='spmv-v2-object-') as td:
            out=Path(td)/'csr.text'
            subprocess.run(['objcopy','--dump-section',f'.text={out}',str(obj)],check=True,capture_output=True)
            records[variant]=dict(object_sha256=sha(obj),csr_source_sha256=sha(obj.with_suffix('.c')),
                                  text_sha256=sha(out),text_bytes=out.stat().st_size)
    return dict(available=True,objects=records,
                source_equal=records['original']['csr_source_sha256']==records['v1']['csr_source_sha256'],
                text_equal=records['original']['text_sha256']==records['v1']['text_sha256'],
                limitation='ELF object .text before final-link relocations; not proof of identical final addresses, caches or execution environment')

def main():
    old=get('large','original');sell=get('large','sell16')
    delta=(old['median_ms']-sell['median_ms'])/1000
    model=dict(original_median_ms=old['median_ms'],sell16_median_ms=sell['median_ms'],
        saved_per_call_ms=delta*1000,prepare_median_s=sell['prepare_median_s'],
        max_prepare_for_R9_ms=9*delta*1000,
        prepare_reduction_factor_needed=sell['prepare_median_s']/(9*delta),
        break_even_calls_under_R9_medians=math.floor(sell['prepare_median_s']/delta)+1,
        max_kernel_ms_if_prepare_unchanged=(9*old['median_ms']/1000-sell['prepare_median_s'])/9*1000,
        original_compute_total_s=old['compute_total_median_s'],sell16_compute_total_s=sell['compute_total_median_s'],
        R9_total_slowdown_percent=(sell['compute_total_median_s']/old['compute_total_median_s']-1)*100,
        note='derived from component medians, not a new benchmark or per-run guarantee')
    small=[get('cache-small','original',t,100) for t in [1,12,24]]
    controls=dict(original=get('large','original'),v1_original=get('large','v1-original'),
        v1_original_relative_difference_percent=(get('large','v1-original')['median_ms']/old['median_ms']-1)*100,
        interpretation='overlapping min/max and unchanged CSR source prevent causal attribution to wrapper overhead alone')
    cases=[]
    for name in ['random4','random15','random8','random256','heavy-clustered','giant-row','empty99']:
        variants=[get(name,v,12,100 if name=='cache-small' else 9) for v in ['original','csr-scalar','csr-pack','sell8','sell16']]
        cases.append(dict(matrix=name,rows=variants))
    output=dict(kind='reanalysis_of_v1_no_new_performance_measurements',date='2026-10-25',
        inputs_sha256={n:sha(V1/n) for n in ['measurements.csv','summary.json','source-provenance.json']},
        cost_model=model,small_matrix=small,
        small_24_over_1_time_ratio=small[2]['median_ms']/small[0]['median_ms'],
        controls=controls,object_text_comparison=object_text_comparison(),cases=cases,
        v1_code_commit='f089579a489723547a354459d591c551a313c4bb',
        original_code_commit='9352c865044f4c8b344d6fe5a277200a89f7a08b')
    (HERE/'diagnosis.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    workloads=workload_models()
    with (HERE/'workload-model.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(workloads[0]),lineterminator='\n');w.writeheader();w.writerows(workloads)
    print(json.dumps(dict(cost_model=model,object_text_comparison=output['object_text_comparison'],
                         small_24_over_1_time_ratio=output['small_24_over_1_time_ratio']),ensure_ascii=False,indent=2))
    for row in workloads:
        if row['threads']==24:
            print(row['matrix'],row['model'],round(row['nnz_max_over_mean'],3),round(row['weighted_work_max_over_mean'],3))

if __name__=='__main__':main()
