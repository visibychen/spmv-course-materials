#!/usr/bin/env python3
"""Predeclared paired block analysis, frozen before formal measurements."""
import collections,csv,json,statistics as st
import numpy as np
import common as c
import run_experiments as r
H=c.H
def interval(values,key):
 a=np.array(values,dtype=float);seed=2026103153+sum((i+1)*ord(x) for i,x in enumerate(str(key)))
 samples=np.random.default_rng(seed).choice(a,size=(20000,len(a)),replace=True)
 return np.quantile(np.median(samples,axis=1),[.025,.975]).tolist()
def analyze():
 rows=r.rows();p=json.loads((H/'protocol.json').read_text());assert len(rows)==len(p['jobs'])
 grouped=collections.defaultdict(list)
 for x in rows:grouped[tuple(x[k] for k in ['phase','matrix','variant','threads','repeat','mode'])].append(x)
 summaries=[]
 for key,g in sorted(grouped.items()):
  x=dict(zip(['phase','matrix','variant','threads','repeat','mode'],key));x['samples']=len(g)
  for metric in ['prepare_s','execute_s','cleanup_s','total_s','wall_s']:x[metric+'_median']=st.median(float(a[metric]) for a in g)
  x['total_s_min']=min(float(a['total_s']) for a in g);x['total_s_max']=max(float(a['total_s']) for a in g)
  x['actual_threads']=','.join(sorted({a['actual_threads'] for a in g}));summaries.append(x)
 c.save('summary.json',summaries)
 with (H/'summary.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(summaries[0]),lineterminator='\n');w.writeheader();w.writerows(summaries)
 blocks=collections.defaultdict(list);paired=collections.defaultdict(list)
 for x in rows:
  if x['block']:blocks[x['block']].append(x)
 for block,g in blocks.items():
  phase=g[0]['phase'];candidate='aa-b' if phase=='aa' else 'v3';a=next(x for x in g if x['variant']==candidate)
  for b in g:
   if b is a:continue
   key=(phase,a['matrix'],int(a['threads']),int(a['repeat']),b['variant'],int(b['threads']))
   paired[key].append((a,b))
 results=[]
 for key,g in sorted(paired.items()):
  phase,n,t,R,control,ct=key;ratios=[float(a['total_s'])/float(b['total_s']) for a,b in g]
  x=dict(phase=phase,matrix=n,threads=t,repeat=R,control=control,control_threads=ct,blocks=len(g),median_time_ratio=st.median(ratios),ci95=interval(ratios,(phase,n,t,R)),time_change_percent=(st.median(ratios)-1)*100,ratios=ratios)
  for metric in ['prepare_s','execute_s','cleanup_s','total_s','wall_s']:
   x['candidate_'+metric+'_median']=st.median(float(a[metric]) for a,b in g)
   x['control_'+metric+'_median']=st.median(float(b[metric]) for a,b in g)
  results.append(x)
 c.save('paired-analysis.json',results)
 index={(x['phase'],x['matrix'],int(x['threads']),int(x['repeat']),x['variant']):x for x in summaries}
 comparisons=[]
 for key,x in index.items():
  phase,n,t,R,v=key
  if v!='original' or phase not in ['main','critical','screen','heldout','sensitivity']:continue
  if not all((phase,n,t,R,k) in index for k in r.VERSIONS):continue
  item=dict(phase=phase,matrix=n,threads=t,repeat=R)
  for v in r.VERSIONS:item[v+'_ms']=index[(phase,n,t,R,v)]['total_s_median']*1000
  for v in ['v2','v3']:item[v+'_vs_original_percent']=(item[v+'_ms']/item['original_ms']-1)*100
  item['v3_vs_v2_percent']=(item['v3_ms']/item['v2_ms']-1)*100
  z=index[(phase,n,t,R,'v3')];item['prepare_ms']=z['prepare_s_median']*1000;item['execute_ms']=z['execute_s_median']*1000;item['actual_threads']=z['actual_threads'];comparisons.append(item)
 c.save('comparisons.json',comparisons)
 with (H/'comparisons.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(comparisons[0]),lineterminator='\n');w.writeheader();w.writerows(comparisons)
 main={x['control']:x for x in results if x['phase']=='main'}
 original_screen=[x for x in summaries if x['matrix']=='large' and x['variant']=='original' and x['repeat']=='9' and x['phase'] in ['main','sensitivity']]
 best=min(original_screen,key=lambda x:x['total_s_median'])
 if int(best['threads'])==24:orig=main['original']
 elif int(best['threads'])==12:orig=next(x for x in results if x['phase']=='cross12')
 else:orig=None
 original_ok=orig is not None and orig['candidate_total_s_median']/orig['control_total_s_median']<=.95 and orig['ci95'][1]<1
 v2_ok=main['v2']['median_time_ratio']<=.95 and main['v2']['ci95'][1]<1
 mech=next(x for x in results if x['phase']=='mechanism');mech_ok=mech['median_time_ratio']<=.95 and mech['ci95'][1]<1
 aa=next(x for x in results if x['phase']=='aa');aa_ok=aa['ci95'][0]>=1/1.05 and aa['ci95'][1]<=1.05
 cli={x['control']:x for x in results if x['phase']=='cli'}
 cli_ok=cli['v2']['median_time_ratio']<=1.05 and cli['original']['candidate_total_s_median']/cli['original']['control_total_s_median']<=.95
 guards=[x for x in results if x['phase']=='critical' and ((x['matrix']=='heavy-clustered' and x['control']=='v2') or (x['matrix'] in ['giant-row','empty99','heldout-two-giants'] and x['control']=='original'))]
 guard_ok=all(x['median_time_ratio']<=1.10 for x in guards)
 counts={}
 for label,isnew in [('old',False),('new',True)]:
  names={x['name'] for x in r.matrices() if (x['group']=='new-heldout')==isnew}
  cases=[x for x in comparisons if x['matrix'] in names and x['threads']==12]
  counts[label]=dict(n=len(cases),v2_slower_over10=sum(x['v2_ms']>x['original_ms']*1.1 for x in cases),v3_slower_over10=sum(x['v3_ms']>x['original_ms']*1.1 for x in cases))
 counts_ok=all(x['v3_slower_over10']<=x['v2_slower_over10'] for x in counts.values())
 proof=json.loads((H/'tile-execution-proof.json').read_text())
 correctness=len(json.loads((H/'verification-builds.json').read_text()))==8 and len(json.loads((H/'compatibility.json').read_text()))==10 and len({x['matrix'] for x in json.loads((H/'correctness.json').read_text())})==104
 gates=dict(correctness=correctness,main_vs_best_original=original_ok,main_vs_v2=v2_ok,matched_fp_mechanism=mech_ok,actual_tile_coverage=proof['tile8_calls']>0,aa_precision=aa_ok,production_cli_guard=cli_ok,critical_regression_guard=guard_ok,negative_counts_not_increased=counts_ok)
 decision=dict(gates=gates,failed_gates=[k for k,v in gates.items() if not v],accepted_as_robust_upgrade=all(gates.values()),branch_action='keep optimization/v3' if all(gates.values()) else 'restore optimization/v2; retain optimization/v3',best_tested_original=best,main=list(main.values()),main_vs_selected_original=orig,mechanism=mech,aa=aa,cli=list(cli.values()),guards=guards,descriptive_counts=counts,statistics='Median candidate/control total time ratios;20000 block bootstrap draws; per-condition CI, no family-wise correction; descriptive counts have no workload weights.')
 c.save('decision.json',decision)
 print(json.dumps(dict(gates=gates,counts=counts,main=[{k:x[k] for k in ['control','median_time_ratio','ci95']} for x in main.values()],mechanism=mech['median_time_ratio']),ensure_ascii=False,indent=2))
if __name__=='__main__':analyze()
