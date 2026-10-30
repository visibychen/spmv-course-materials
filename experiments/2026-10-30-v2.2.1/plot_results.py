#!/usr/bin/env python3
"""Static export after formal timings; keep actual-thread caveats visible."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from run_experiments import HERE as H
SERIES=[('original_ms','#b4bbc2','original'),('v2_ms','#69778b','v2'),('v22_ms','#d69551','v2.2'),('v221_ms','#087e8b','v2.2.1')]
def export(fig,name):
 fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(H/f'figures/{name}.{ext}',dpi=160)
 plt.close(fig)
def main():
 (H/'figures').mkdir(exist_ok=True);cs=json.loads((H/'comparison-cases.json').read_text())
 for tag,subset in [('old-T12',[c for c in cs if c['threads']==12 and c['phase']!='heldout']),('new-T12',[c for c in cs if c['threads']==12 and c['phase']=='heldout'])]:
  subset=sorted(subset,key=lambda c:c['matrix']);y=np.arange(len(subset));fig,ax=plt.subplots(figsize=(11,max(6,.3*len(subset))))
  for i,(key,color,label) in enumerate(SERIES[1:]):
   ax.barh(y+(i-1)*.23,[c['original_ms']/c[key] for c in subset],height=.22,color=color,label=label)
  ax.axvline(1,color='#b64040',lw=1);ax.set_xscale('log');ax.set_yticks(y,[c['matrix'] for c in subset]);ax.invert_yaxis()
  ax.set_title(tag+': requested cap12, actual teams may differ');ax.set_xlabel('Speedup vs original (median P + E + cleanup); higher is faster')
  ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True);ax.legend(loc='upper right');export(fig,tag)
 maincases=sorted([c for c in cs if c['matrix']=='large' and c['repeat']==9],key=lambda c:c['threads'])
 fig,axes=plt.subplots(1,2,figsize=(11,4.5),gridspec_kw={'width_ratios':[1,2]})
 for ax,subset in zip(axes,[[c for c in maincases if c['threads']==1],[c for c in maincases if c['threads']!=1]]):
  x=np.arange(len(subset));w=.2
  for i,(key,color,label) in enumerate(SERIES):ax.bar(x+(i-1.5)*w,[c[key] for c in subset],width=w,color=color,label=label)
  ax.set_xticks(x,[str(c['threads']) for c in subset]);ax.set_xlabel('Requested thread cap, R=9');ax.set_ylabel('Median P + E + cleanup (ms)');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
 axes[1].legend();fig.suptitle('12M rows /96M nonzeros; separate y scales');export(fig,'large-R9')
 d=json.loads((H/'decision.json').read_text());fig,ax=plt.subplots(figsize=(8,4))
 for i,(label,p) in enumerate(d['main_pairs'].items()):
  point=p['median_pair_speedup'];ax.errorbar(point,i,xerr=[[point-p['low95']],[p['high95']-point]],fmt='o',color=SERIES[i][1],capsize=5)
 ax.set_yticks(range(3),[f'{k}, n={p["pairs"]} pairs' for k,p in d['main_pairs'].items()]);ax.axvline(1,color='#666',lw=1);ax.axvline(.95,color='#c04b40',lw=1,ls='--')
 ax.set_xlabel('Control /v2.2.1 paired speedup, median and bootstrap95% interval');ax.set_title('Main T24/R9; 0.95 bound applies to v2 comparison');ax.grid(axis='x',alpha=.15);export(fig,'main-pairs')
if __name__=='__main__':main()
