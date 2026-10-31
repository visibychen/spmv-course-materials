#!/usr/bin/env python3
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent
pairs=json.loads((H/'paired-analysis.json').read_text())
for filename,title,data in [('main-pairs','Main matrix: candidate / control (lower is faster)',[x for x in pairs if x['phase']=='large']),('target-pairs','New T12/R9 targets: candidate / parent',[x for x in pairs if x['phase']=='targets' and x['control']=='v22'])]:
 fig,ax=plt.subplots(figsize=(8,3.2));ys=list(range(len(data)))
 for y,x in zip(ys,data):
  low,high=x['ci95'];point=x['median_candidate_over_control'];ax.errorbar(point,y,xerr=[[point-low],[high-point]],fmt='o',capsize=4,color='#2166ac')
 ax.axvline(1,color='#777',linestyle='--',linewidth=1);ax.set_yticks(ys,[x['control'] if filename=='main-pairs' else x['matrix'] for x in data]);ax.invert_yaxis();ax.set_xlabel('Median paired time ratio and percentile 95% interval');ax.set_title(title);ax.grid(axis='x',alpha=.2);fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(H/f'figures/{filename}.{ext}',dpi=180)
 plt.close(fig)
print('PLOTS written')
