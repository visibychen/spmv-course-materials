#!/usr/bin/env python3
"""Fit nonnegative coefficients only from disjoint calibration observations."""
import csv,hashlib,itertools,json
from pathlib import Path
from statistics import median
import numpy as np
H=Path(__file__).resolve().parent

def nnls3(x,y):
    x=np.array(x,dtype=float);y=np.array(y,dtype=float)
    scale=np.maximum(np.max(np.abs(x),axis=0),1);a=x/scale
    best=(float(np.dot(y,y)),np.zeros(x.shape[1]))
    for mask in itertools.product([False,True],repeat=x.shape[1]):
        if not any(mask):continue
        idx=np.flatnonzero(mask);z=np.linalg.lstsq(a[:,idx],y,rcond=None)[0]
        if np.min(z)<-1e-15:continue
        full=np.zeros(x.shape[1]);full[idx]=np.maximum(z,0)
        err=np.sum((a@full-y)**2)
        if err<best[0]:best=(float(err),full)
    coef=best[1]/scale
    return coef,{'rmse_s':float(np.sqrt(best[0]/len(y))),'relative_rmse':float(np.sqrt(best[0]/len(y))/np.mean(y)),'n_shapes':len(y)}

def main():
    raw=list(csv.DictReader((H/'calibration.csv').open()));fps={r['fingerprint'] for r in raw}
    assert len(fps)==1
    groups={}
    for r in raw:groups.setdefault((int(r['regime']),int(r['kernel']),int(r['threads']),int(r['case'])),[]).append(r)
    bymodel={}
    for (reg,k,t,c),rows in groups.items():
        r=rows[0];launch=median(float(x['launch_s']) for x in rows)
        e=median(max(0,float(x['execute_s'])-launch)/int(x['repeat']) for x in rows)
        bymodel.setdefault((reg,k,t),[]).append(([float(r['max_nnz']),float(r['max_rows']),1],e,launch))
    lines=[f'SPMV21 1 {next(iter(fps))} 8388608 64 0.1']
    fits=[];excluded=[]
    for (reg,k,t),points in sorted(bymodel.items()):
        if len({tuple(p[0][:2]) for p in points})<2:
            excluded.append(dict(regime=reg,kernel=k,threads=t,reason='one workload size cannot identify a scaling slope separately from call overhead'))
            continue
        coef,diag=nnls3([p[0] for p in points],[p[1] for p in points]);launch=median(p[2] for p in points)
        lines.append(f'M {reg} {k} {t} {coef[0]:.16g} {coef[1]:.16g} {coef[2]:.16g} {launch:.16g}')
        fits.append(dict(regime=reg,kernel=k,threads=t,coefficients=coef.tolist(),launch_s=launch,**diag))
    for t in sorted({int(r['threads']) for r in raw}):
        points=[]
        for c in sorted({int(r['case']) for r in raw}):
            rows=[r for r in raw if int(r['threads'])==t and int(r['case'])==c]
            r=rows[0];points.append(([float(r['nonzeros']),float(r['rows']),1],median(float(x['prepare_s']) for x in rows)))
        coef,diag=nnls3([p[0] for p in points],[p[1] for p in points])
        lines.append(f'P {t} {coef[0]:.16g} {coef[1]:.16g} {coef[2]:.16g}')
        fits.append(dict(kind='prepare',threads=t,coefficients=coef.tolist(),**diag))
    text='\n'.join(lines)+'\n';(H/'profile.txt').write_text(text)
    (H/'calibration-fit.json').write_text(json.dumps({'fingerprint':next(iter(fps)),'observations':len(raw),
        'independent_processes':1,'calibration_source':'calibrate.c: disjoint dimensions and seed 19871207',
        'method':'nonnegative least squares by exhaustive active sets; median within-process observations per shape',
        'tier_note':'8MiB is a profile grouping boundary, not a measured LLC capacity or DRAM traffic boundary',
        'margin_note':'10% conservative engineering margin; not a confidence bound or tuned on evaluation inputs',
        'profile_sha256':hashlib.sha256(text.encode()).hexdigest(),'models':fits,'excluded_models':excluded},indent=2)+'\n')
    print('profile frozen from',len(raw),'calibration observations;',len(fits),'models')
if __name__=='__main__':main()
