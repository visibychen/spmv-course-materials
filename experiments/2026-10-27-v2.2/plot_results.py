#!/usr/bin/env python3
"""Export static figures after formal timings have completed."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from run_experiments import HERE as H
def main():
 cs=json.loads((H/'comparison-cases.json').read_text());out=H/'figures';out.mkdir(exist_ok=True)
 for tag,subset in [('old-T12',[c for c in cs if c['threads']==12 and c['phase'] in ['critical','screen','large']]),
                    ('new-T12',[c for c in cs if c['threads']==12 and c['phase']=='heldout'])]:
  subset=sorted(subset,key=lambda c:c['matrix']);y=np.arange(len(subset))
  fig,ax=plt.subplots(figsize=(11,max(6,len(subset)*.29)))
  for k,color,dy,label in [('v2_ms','#6c7a89',-.15,'v2'),('v22_ms','#087f8c',.15,'v2.2')]:
   ax.barh(y+dy,[c['original_ms']/c[k] for c in subset],height=.28,color=color,label=label)
  ax.axvline(1,color='#c04b40',lw=1);ax.set_xscale('log');ax.set_yticks(y,[c['matrix'] for c in subset]);ax.invert_yaxis()
  ax.set_xlabel('Speedup vs original (median P + E + cleanup); higher is faster')
  ax.set_title(f'{tag}: requested cap 12; actual teams may differ')
  ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True);ax.legend(loc='upper right');fig.tight_layout()
  for ext in ['png','svg']:fig.savefig(out/f'{tag}.{ext}',dpi=160)
  plt.close(fig)
 maincases=sorted([c for c in cs if c['matrix']=='large' and c['repeat']==9],key=lambda c:c['threads'])
 fig,ax=plt.subplots(figsize=(8,4.5));x=np.arange(len(maincases));w=.25
 for idx,(key,color,label) in enumerate([('original_ms','#b6bec6','original'),('v2_ms','#65768a','v2'),('v22_ms','#087f8c','v2.2')]):
  ax.bar(x+(idx-1)*w,[c[key] for c in maincases],width=w,color=color,label=label)
 ax.set_xticks(x,[str(c['threads']) for c in maincases]);ax.set_xlabel('Requested thread cap, R=9');ax.set_ylabel('Median P + E + cleanup (ms)')
 ax.set_title('12M rows / 96M nonzeros, frozen archive builds');ax.legend();ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(out/f'large-R9.{ext}',dpi=160)
 plt.close(fig)
if __name__=='__main__':main()
