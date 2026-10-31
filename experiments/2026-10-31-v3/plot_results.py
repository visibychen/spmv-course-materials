#!/usr/bin/env python3
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
H=Path(__file__).resolve().parent
d=json.loads((H/'decision.json').read_text())
data=d['main']+[d['mechanism'],d['aa']]
labels=['original T24','v2 T24','matched-FP v3-csr','identical v2 A/A']
fig,ax=plt.subplots(figsize=(8,3.5))
for y,(x,label) in enumerate(zip(data,labels)):
 p=x['median_time_ratio'];lo,hi=x['ci95'];ax.errorbar(p,y,xerr=[[p-lo],[hi-p]],fmt='o',capsize=4,color='#2166ac')
ax.set_yticks(range(len(labels)),labels);ax.invert_yaxis();ax.axvline(1,color='#777',linestyle='--',linewidth=1);ax.grid(axis='x',alpha=.2);ax.set_xlabel('Candidate / control total cost; median and percentile 95% interval');ax.set_title('v3: unified CSR input, T24 / R9');fig.tight_layout()
for ext in ['png','svg']:fig.savefig(H/f'figures/main-pairs.{ext}',dpi=180)
print('PLOT WRITTEN')
