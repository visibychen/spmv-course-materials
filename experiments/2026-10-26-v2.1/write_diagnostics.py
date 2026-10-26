#!/usr/bin/env python3
"""Append separately labelled within-process/probe evidence to the final report."""
import json,re,statistics
from collections import defaultdict
from pathlib import Path
H=Path(__file__).resolve().parent
def main():
 data=json.loads((H/'diagnostic.json').read_text());names=['original','v2-auto','v21-auto','v2-csr','v21-csr','v21-long']
 lines=['','## 6. 同二进制与同步诊断','',
  '这是正式工程计时之后的补充。每配置只有一个独立进程；六后端各一次预热、12轮轮转，每个后端在每个位置出现两次。进程内观察相关，不能当成12个独立进程，不能用稳态替代prepare+execute+cleanup。auto允许减少实际线程，显式CSR均为请求团队。',
  '', '| 输入 | 上限T | original/ms | v2-auto/ms | v21-auto/ms | v2-CSR/ms | v21-CSR/ms | v21-long/ms |','| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
 for entry in data:
  result=[]
  for name in names:
   arr=[r['execute_s']*1000/r['repeat'] for r in entry['records'] if r['type']=='sample' and r['backend']==name]
   assert len(arr)==12;result.append(f'{statistics.median(arr):.3f}')
  lines.append('| '+entry['matrix']+' | '+str(entry['requested_threads'])+' | '+' | '.join(result)+' |')
 lines+=['','匹配FP模式、相同团队下的v2-CSR/v21-CSR能帮助判断新增行路径是否有独立收益；自动后端/团队不同则反映策略差异。小幅差值只有单进程证据，不外推成普遍贡献。',
  '', '| 输入 | 后端 | 实际T | 平均线程计算/ms（R9） | 平均线程等待/ms（R9） | 探针E/无探针E |','| --- | --- | --- | ---: | ---: | ---: |']
 probes=json.loads((H/'thread-diagnostic.json').read_text());groups=defaultdict(list)
 for p in probes:groups[(p['matrix'],p['backend'])].append(p)
 aggregates=[]
 for (matrix,backend),entries in sorted(groups.items()):
  es={False:[],True:[]};wait=[];compute=[];teams=[]
  for e in entries:
   text=e['stdout'];m=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds',text);es[e['instrumented']].append(float(m[1]))
   if not e['instrumented']:continue
   slots={}
   for line in text.splitlines():
    if line.startswith('spmv_v21_thread:'):
     row=dict(re.findall(r'(\w+)=(\S+)',line));slots[int(row['thread'])]=row
   if slots:
    teams.append(len(slots));compute.append(statistics.mean(float(s['compute_s'])*1000 for s in slots.values()))
    wait.append(statistics.mean((float(s['publish_s'])+float(s['complete_s']))*1000 for s in slots.values()))
  overhead=statistics.median(es[True])/statistics.median(es[False])
  if compute:
   c=statistics.median(compute);w=statistics.median(wait);nt=','.join(map(str,sorted(set(teams))))
   lines.append(f'| {matrix} | {backend} | {nt} | {c:.3f} | {w:.3f} | {overhead:.3f} |')
   aggregates.append(dict(matrix=matrix,backend=backend,threads=nt,mean_thread_compute_ms=c,mean_thread_wait_ms=w,probe_execute_ratio=overhead))
  else:lines.append(f'| {matrix} | {backend} | 原始路径 | 未分项计时 | 未分项计时 | {overhead:.3f} |')
 lines+=['','每侧3个额外进程，顺序按诊断脚本固定，只有探针扰动的粗略对照，不是主性能结论。表中等待为各线程等待时间的均值，不是总wall中的可相加占比；fixup另见原始记录。原始内核没有拆分内部屏障计时。没有据此声称删除屏障即可得到同等收益。',
  '', '![旧输入总成本加速比](figures/development-speedup.png)','', '![新保留输入总成本加速比](figures/new-holdout-speedup.png)']
 report=H/'结果分析.md';text=report.read_text().split('\n## 6. 同二进制与同步诊断')[0];report.write_text(text+'\n'.join(lines)+'\n')
 (H/'thread-diagnostic-summary.json').write_text(json.dumps(aggregates,indent=2)+'\n')
 print('Appended separately labelled diagnostics')
if __name__=='__main__':main()
