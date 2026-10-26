#!/usr/bin/env python3
"""Export static, shareable plots from total-cost medians."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
H=Path(__file__).resolve().parent
def main():
 (H/'figures').mkdir(exist_ok=True)
 cases=json.loads((H/'comparison-cases.json').read_text())
 for group in ['development','new-holdout']:
  rows=[c for c in cases if c['threads']==12 and
      (c['phase'] in ['critical','screen','large'] if group=='development' else c['phase']=='heldout')]
  rows=sorted(rows,key=lambda c:c['matrix']);n=len(rows);y=np.arange(n)
  fig,ax=plt.subplots(figsize=(11,max(5,n*.28+1.5)),layout='constrained')
  a=np.array([c['original_ms']/c['v2_ms'] for c in rows]);b=np.array([c['original_ms']/c['v21_ms'] for c in rows])
  ax.scatter(a,y+.12,label='v2',marker='s',s=25,color='#526b9e')
  ax.scatter(b,y-.12,label='v2.1',s=30,color='#cf651c')
  for i in range(n):ax.plot([a[i],b[i]],[y[i]+.12,y[i]-.12],color='#b0b6be',linewidth=.8,zorder=0)
  ax.set_yticks(y,[c['matrix'] for c in rows]);ax.invert_yaxis();ax.set_xscale('log');ax.axvline(1,color='#343c46',linestyle='--',linewidth=1)
  ax.set_xlabel('Total-cost speedup vs original (higher is better; log scale)')
  ax.set_title(f'{group}: requested cap 12; actual teams may differ')
  ax.grid(axis='x',alpha=.2);ax.legend(loc='upper right')
  for ext in ['png','svg']:fig.savefig(H/f'figures/{group}-speedup.{ext}',dpi=170)
  plt.close(fig)
 print('Exported four plot files')
if __name__=='__main__':main()
