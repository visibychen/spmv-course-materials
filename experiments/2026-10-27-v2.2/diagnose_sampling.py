#!/usr/bin/env python3
"""Structural replay only: no timing, no code/threshold changes."""
import re
import run_experiments as r
def main():
 out=[]
 for name in ['v22-empty99','v22-empty90']:
  m=r.matrix(name);n=m['rows'];sample=[i*(n-1)//63 for i in range(64)]
  is_empty=(lambda row:row%100!=0) if name.endswith('99') else (lambda row:row>=n//10)
  count=sum(map(is_empty,sample));full=n-((n-1)//100+1) if name.endswith('99') else n-n//10
  log=r.HERE/f'raw/heldout-{name}-v22-t12-r9-s1.stdout.txt'
  text=log.read_text();info=dict(re.findall(r'(\w+)=(\S+)',re.search(r'spmv_v22: (.*)',text)[1]))
  assert int(info['empty_rows'])==full and info['route']=='v2-rules-fast-validation'
  out.append(dict(matrix=name,rows=n,actual_empty_rows=full,actual_empty_ratio=full/n,sample_rows=sample,
   sampled_empty_rows=count,sample_size=64,sample_empty_ratio=count/64,allocation_hint_pass=count*10>=64*9,
   source='committed spmv_v22.c uniform allocation-hint sampling; generator exact row formulas',log=str(log.relative_to(r.HERE)),
   interpretation='False negative allocation hint; full validation still counts empties, but no later index allocation retry. Correctness unaffected; no claim of run-kernel speedup on this input.'))
 r.save('sampling-diagnosis.json',out);print('Verified2 sampling misses against route/full-count logs')
if __name__=='__main__':main()
