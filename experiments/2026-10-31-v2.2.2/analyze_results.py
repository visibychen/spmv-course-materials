#!/usr/bin/env python3
"""Frozen paired analysis and predeclared acceptance. Never retunes production."""
import collections,csv,json,statistics as st
from pathlib import Path
import numpy as np
import run_experiments as r
H=Path(__file__).resolve().parent
SEED=2026103111
METRICS=['prepare_s','execute_s','cleanup_s','total_s','wall_s']
def interval(vals,key):
 vals=np.asarray(vals,dtype=float);seed=SEED+sum((i+1)*ord(c) for i,c in enumerate(str(key)))
 rng=np.random.default_rng(seed);means=np.median(rng.choice(vals,size=(20000,len(vals)),replace=True),axis=1)
 return [float(x) for x in np.quantile(means,[.025,.975])]
def analyze():
 rows=r.records();protocol=json.loads((H/'protocol.json').read_text());assert len(rows)==len(protocol['jobs'])
 r.summarize();sums=json.loads((H/'summary.json').read_text())
 groups=collections.defaultdict(list)
 for x in rows:
  if x['pair']:groups[x['pair']].append(x)
 paired=collections.defaultdict(list)
 for pid,g in groups.items():
  assert len(g)==2
  if g[0]['phase']=='aa':control='v2-aa-a';candidate='v2-aa-b'
  else:control=next(x['variant'] for x in g if x['variant']!='v222');candidate='v222'
  a=next(x for x in g if x['variant']==candidate);b=next(x for x in g if x['variant']==control)
  key=(a['phase'],a['matrix'],int(a['threads']),int(a['repeat']),control)
  paired[key].append((a,b))
 results=[]
 for key,pairs in sorted(paired.items()):
  phase,m,t,R,c=key;ratios=[float(a['total_s'])/float(b['total_s']) for a,b in pairs]
  item=dict(phase=phase,matrix=m,threads=t,repeat=R,control=c,pairs=len(pairs),median_candidate_over_control=st.median(ratios),ci95=interval(ratios,key),time_change_percent=(st.median(ratios)-1)*100,ratios=ratios)
  for metric in METRICS:
   item['candidate_'+metric+'_median']=st.median(float(a[metric]) for a,b in pairs)
   item['control_'+metric+'_median']=st.median(float(b[metric]) for a,b in pairs)
  item['candidate_active_values']=sorted({a.get('active','') for a,b in pairs});results.append(item)
 r.save('paired-analysis.json',results)
 index={(x['phase'],x['matrix'],int(x['threads']),int(x['repeat']),x['variant']):x for x in sums}
 comparisons=[]
 for key,base in index.items():
  phase,m,t,R,v=key
  if v!='original' or phase not in ['critical','targets','screen','heldout','large','large-sensitivity']:continue
  if not all((phase,m,t,R,x) in index for x in ['v2','v22','v222']):continue
  out=dict(phase=phase,matrix=m,threads=t,repeat=R)
  for v in ['original','v2','v22','v222']:
   x=index[(phase,m,t,R,v)];out[v+'_ms']=x['total_s_median']*1000
  out['v222_vs_original_percent']=(out['v222_ms']/out['original_ms']-1)*100
  out['v222_vs_v22_percent']=(out['v222_ms']/out['v22_ms']-1)*100
  x=index[(phase,m,t,R,'v222')];out['prepare_ms']=x['prepare_s_median']*1000;out['execute_ms']=x['execute_s_median']*1000;out['actual_threads']=x['actual_threads'];comparisons.append(out)
 r.save('comparisons.json',comparisons)
 with (H/'comparisons.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
 main=[x for x in results if x['phase']=='large'];aa=next(x for x in results if x['phase']=='aa')
 mainmap={x['control']:x for x in main}
 original_candidates=[x for x in sums if x['matrix']=='large' and x['variant']=='original' and int(x['repeat'])==9]
 best_original=min(original_candidates,key=lambda x:x['total_s_median'])
 baseline=mainmap['original'];best24=int(best_original['threads'])==24
 main_original=best24 and baseline['candidate_total_s_median']<=.95*baseline['control_total_s_median'] and baseline['ci95'][1]<1
 main_v2=mainmap['v2']['median_candidate_over_control']<=1.03 and mainmap['v2']['ci95'][1]<=1.05
 main_v22=mainmap['v22']['median_candidate_over_control']<=1.03 and mainmap['v22']['ci95'][1]<=1.05
 guards=[x for x in results if x['phase']=='critical' and x['matrix'] in r.GUARDS and x['control']=='v22']
 guards_ok=all(x['median_candidate_over_control']<=1.05 for x in guards)
 targets=[x for x in results if x['phase']=='targets' and x['control']=='v22']
 improved=[x['matrix'] for x in targets if x['median_candidate_over_control']<.95 and x['ci95'][1]<1]
 eligibility_names=['v222-block1','v222-block4','v222-block8','v222-block90','v222-block64']
 coverage={m:sorted({x.get('active','') for x in rows if x['matrix']==m and x['variant']=='v222'}) for m in eligibility_names}
 coverage_ok=all(v==['1'] for v in coverage.values())
 counts={}
 for label,new in [('old',False),('new',True)]:
  names={m['name'] for m in r.matrices() if (m['group']=='new-heldout')==new}
  cases=[x for x in comparisons if x['matrix'] in names and x['threads']==12]
  counts[label]=dict(n=len(cases),v22_slower_over5=sum(x['v22_ms']>x['original_ms']*1.05 for x in cases),v222_slower_over5=sum(x['v222_ms']>x['original_ms']*1.05 for x in cases))
 count_ok=all(v['v222_slower_over5']<=v['v22_slower_over5'] for v in counts.values())
 unit=json.loads((H/'verification-builds.json').read_text());correct=json.loads((H/'correctness.json').read_text())
 checks_ok=len(unit)==21 and all(x['returncode']==0 for x in unit) and len({x['matrix'] for x in correct if 'matrix' in x})==len(r.matrices())
 gates=dict(correctness=checks_ok,main_vs_original=main_original,main_vs_v2=main_v2,main_vs_v22=main_v22,preserve_parent_guards=guards_ok,target_coverage_and_two_improvements=coverage_ok and len(improved)>=2,negative_counts_not_increased=count_ok,aa_precision=aa['ci95'][0]>=1/1.05 and aa['ci95'][1]<=1.05)
 decision=dict(gates=gates,failed_gates=[k for k,v in gates.items() if not v],accepted_as_robust_upgrade=all(gates.values()),branch_action='keep optimization/v2.2.2' if all(gates.values()) else 'restore optimization/v2; preserve optimization/v2.2.2',best_tested_original=best_original,main_matched=main,aa=aa,descriptive_counts=counts,improved_new_targets=improved,coverage=coverage,guard_pairs=guards,limitations='Paired intervals are per-condition, not family-wise corrected. Counts are descriptive; no workload weighting. A/A uncertainty is not evidence of equivalence. Production six-decimal E is retained.')
 r.save('decision.json',decision);r.save('policy-coverage.json',coverage)
 print(json.dumps(dict(gates=gates,improved_new_targets=improved,counts=counts),ensure_ascii=False,indent=2))
if __name__=='__main__':analyze()
