#!/usr/bin/env python3
"""Four-way descriptive/paired analysis; never edits production rules."""
import csv,json,statistics
from collections import defaultdict
import numpy as np
import run_experiments as r
H=r.HERE
GATE_TITLES={
 'correctness':'正确性与安全检查',
 'main_vs_original':'主矩阵对最佳已测原始至少5%收益，且配对支持',
 'main_vs_v2':'主矩阵对v2中位退化≤3%，速度比区间下界≥0.95',
 'main_vs_v22':'主矩阵对v2.2中位退化≤3%',
 'guards_no_over5_regression_vs_v22':'原7个关键条件对v2.2不新增超过5%中位退化',
 'misses_selected_and_total_cost_improved':'两份漏选实际启用索引，T12至少一份改善>5%，另一份退化≤5%',
 'negative_counts_not_increased':'旧/新T12对原始的退化计数均不多于v2.2',
 'no_confirmed_prior_regressions_vs_v2':'此前8个退化条件无确认的>5%对v2退化'}
def med(rows,k='total_s'):return statistics.median(float(x[k]) for x in rows)
def counts(cs,k):return dict(faster_over5=sum(x[k]<-5 for x in cs),within5=sum(abs(x[k])<=5 for x in cs),slower_over5=sum(x[k]>5 for x in cs))
def describe(c):return f'快>5% {c["faster_over5"]}、±5%内 {c["within5"]}、慢>5% {c["slower_over5"]}'
def main():
 rows=r.records();assert len(rows)==3369
 g=defaultdict(list);blocks=defaultdict(list)
 for x in rows:
  g[(x['phase'],x['matrix'],int(x['threads']),int(x['repeat']),x['variant'])].append(x)
  if x['pair']:blocks[x['pair']].append(x)
 pairs=defaultdict(list)
 for pid,rs in blocks.items():
  assert len(rs)==2
  candidate=next(x for x in rs if x['variant']=='v221');control=next(x for x in rs if x['variant']!='v221')
  key=(candidate['phase'],candidate['matrix'],int(candidate['threads']),int(candidate['repeat']),control['variant'])
  pairs[key].append((float(control['total_s']),float(candidate['total_s'])))
 rng=np.random.default_rng(20261030);paired=[]
 for (phase,m,t,R,control),values in sorted(pairs.items()):
  a=np.array(values);ratio=a[:,0]/a[:,1]
  boot=np.median(ratio[rng.integers(0,len(ratio),size=(20000,len(ratio)))],axis=1)
  paired.append(dict(phase=phase,matrix=m,threads=t,repeat=R,control=control,pairs=len(values),median_pair_speedup=float(np.median(ratio)),
   low95=float(np.quantile(boot,.025)),high95=float(np.quantile(boot,.975)),control_total_s_median=float(np.median(a[:,0])),candidate_total_s_median=float(np.median(a[:,1])),pair_speedups=ratio.tolist()))
 r.save('paired-analysis.json',paired)
 cases=[]
 for (phase,m,t,R,v),rs in sorted(g.items()):
  if v!='v221' or phase=='ablations':continue
  controls={v:g.get((phase,m,t,R,v)) for v in ['original','v2','v22']}
  if not all(controls.values()):continue
  vals={v:med(a) for v,a in controls.items()};vals['v221']=med(rs)
  c=dict(phase=phase,matrix=m,threads=t,repeat=R,**{v+'_ms':1000*x for v,x in vals.items()})
  for v in ['v2','v22','v221']:c[v+'_vs_original_percent']=100*(vals[v]/vals['original']-1)
  for v in ['v2','v22']:c['v221_vs_'+v+'_percent']=100*(vals['v221']/vals[v]-1)
  c.update(prepare_ms=1000*med(rs,'prepare_s'),execute_ms=1000*med(rs,'execute_s'),cleanup_ms=1000*med(rs,'cleanup_s'),
   selected=','.join(sorted({x['selected'] for x in rs})),route=','.join(sorted({x['route'] for x in rs})),executor=','.join(sorted({x['executor'] for x in rs})),
   actual_threads=','.join(sorted({x['actual_threads'] for x in rs})),index_retry=','.join(sorted({x['index_retry'] for x in rs})),extra_bytes=max(int(x['extra_bytes']) for x in rs),
   **{'samples_'+v:len(a) for v,a in {**controls,'v221':rs}.items()})
  cases.append(c)
 r.save('comparison-cases.json',cases)
 with (H/'comparisons.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(cases[0]),lineterminator='\n');w.writeheader();w.writerows(cases)
 t12=[c for c in cases if c['threads']==12 and c['repeat'] in [9,100]]
 old=[c for c in t12 if c['phase']!='heldout'];new=[c for c in t12 if c['phase']=='heldout'];assert len(old)==68 and len(new)==12
 teams=[(k[2],med(a)) for k,a in g.items() if k[1]=='large' and k[3]==9 and k[4]=='original']
 best_t,best=min(teams,key=lambda x:x[1]);ca=g[('large','large',24,9,'v221')];ct=med(ca)
 primary={v:next(p for p in paired if p['phase']=='large' and p['control']==v) for v in ['original','v2','v22']}
 maincost={v:med(g[('large','large',24,9,v)]) for v in ['original','v2','v22','v221']}
 gates={}
 gates['correctness']=len(json.loads((H/'correctness.json').read_text()))==489
 gates['main_vs_original']=ct<=best*.95 and best_t==24 and primary['original']['low95']>1
 gates['main_vs_v2']=ct<=maincost['v2']*1.03 and primary['v2']['low95']>=.95
 gates['main_vs_v22']=ct<=maincost['v22']*1.03
 guards=[c for c in cases if c['phase']=='critical' and c['matrix'] in r.GUARDS]
 gates['guards_no_over5_regression_vs_v22']=all(c['v221_vs_v22_percent']<=5 for c in guards)
 misses=[c for c in cases if c['phase']=='critical' and c['matrix'] in r.MISSES and c['threads']==12]
 all_miss_rows=[x for x in rows if x['phase']=='critical' and x['matrix'] in r.MISSES and x['variant']=='v221']
 gates['misses_selected_and_total_cost_improved']=all(x['selected']=='empty-runs' and x['index_retry']=='1' for x in all_miss_rows) and min(c['v221_vs_v22_percent'] for c in misses)<-5 and max(c['v221_vs_v22_percent'] for c in misses)<=5
 groups={label:{v:counts(cs,v+'_vs_original_percent') for v in ['v2','v22','v221']} for label,cs in [('old_T12',old),('new_T12',new)]}
 gates['negative_counts_not_increased']=all(x['v221']['slower_over5']<=x['v22']['slower_over5'] for x in groups.values())
 confirmations=[];prior=[]
 for name in r.REGRESSIONS:
  c=next(c for c in old if c['matrix']==name);p=next(p for p in paired if p['phase']=='critical' and p['matrix']==name and p['threads']==12 and p['control']=='v2')
  confirmed=c['v221_vs_v2_percent']>5 and p['high95']<1
  item=dict(matrix=name,time_change_vs_v2_percent=c['v221_vs_v2_percent'],time_change_vs_v22_percent=c['v221_vs_v22_percent'],low95=p['low95'],high95=p['high95'],confirmed_over5_vs_v2=confirmed)
  prior.append(item)
  if confirmed:confirmations.append(name)
 gates['no_confirmed_prior_regressions_vs_v2']=not confirmations
 accept=all(gates.values());failed=[k for k,v in gates.items() if not v]
 decision=dict(gates=gates,failed_gates=failed,failed_gate_descriptions=[GATE_TITLES[k] for k in failed],accepted_as_robust_upgrade=accept,
  branch_action='keep optimization/v2.2.1' if accept else 'switch working checkout to optimization/v2; preserve origin/optimization/v2.2.1',
  original_best_tested_threads=best_t,original_best_total_s=best,main_T24_R9_s=maincost,
  v221_vs_original_best_percent=100*(ct/best-1),v221_vs_v2_percent=100*(ct/maincost['v2']-1),v221_vs_v22_percent=100*(ct/maincost['v22']-1),
  main_pairs=primary,old_T12=dict(n=68,**groups['old_T12']),new_T12=dict(n=12,**groups['new_T12']),
  worst_guard_vs_v22=max(guards,key=lambda c:c['v221_vs_v22_percent']),misses_T12=misses,prior_regression_review=prior,
  interval_limit='Intervals containing1 do not prove slowdown or equivalence. Intervals are per-condition, not family-wise corrected; counts are descriptive.',
  default_change='Serial column validation selected from independent precommit calibration, no tuning after formal measurements.')
 r.save('decision.json',decision)
 lines=['# v2.2.1四版本实验结果','',
  '先推送设计f6e247a，再从v2.2创建分支并推送实现dfb4ae2；随后固定四个提交计时。实现不来自v2或v2.1。正式结果出现后没有更改代码、阈值、输入、样本或准入门槛。',
  '',f'正式进程{len(rows)}，80份输入，820个相邻随机进程对；另有90个提交前独立CLI校准观察及489组完整向量/兼容核验。',
  '', '## 最终判断','',
  '**'+('共同门槛通过，核心工作区保留optimization/v2.2.1。' if accept else '共同门槛未通过，核心工作区恢复optimization/v2；远端v2.2.1保留。')+'** 未合并master，没有重写历史。',
  '', '| 预先约定的门槛 | 是否通过 |','| --- | --- |']
 for k,v in gates.items():lines.append(f'| {GATE_TITLES[k]} | '+('通过' if v else '未通过')+' |')
 lines+=['', '任一共同门槛失败或证据不足即回退；区间包含1时不能称为确定变慢，也不能声称证明了等效。不按某个亮点替换整体判定。',
  '', '## 主大矩阵：总成本与样本区间','',
  f'R9原始最佳已测线程{best_t}，total={best:.6f}s。本版T24中位total={ct:.6f}s，相对最佳原始变化{100*(ct/best-1):+.2f}%，相对v2 {decision["v221_vs_v2_percent"]:+.2f}%，相对v2.2 {decision["v221_vs_v22_percent"]:+.2f}%。',
  '', '| 请求T | R | 原始/ms | v2/ms | v2.2/ms | v2.2.1/ms | 本版P/ms | 本版执行器/实际T |','| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
 for c in sorted([c for c in cases if c['matrix']=='large'],key=lambda c:(c['threads'],c['repeat'])):
  lines.append(f'| {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v221_ms"]:.3f} | {c["prepare_ms"]:.3f} | {c["executor"]}/{c["actual_threads"]} |')
 lines+=['', '| 主T24控制 | 配对数 | 控制/本版配对速度比中位数 | 95%区间 |','| --- | --- | ---: | --- |']
 for v,p in primary.items():lines.append(f'| {v} | {p["pairs"]} | {p["median_pair_speedup"]:.3f} | [{p["low95"]:.3f}, {p["high95"]:.3f}] |')
 lines+=['', '表中本版使用40个候选样本，中位数之比与对应10/20对速度比中位数不同。各区间仅使用对应进程对。若最佳原始团队不是24，T24配对区间不能外推至该最佳团队。',
  '', '主条件全程序wall中位数：'+ '，'.join(f'{v} {med(g[("large","large",24,9,v)],"wall_s"):.2f}s' for v in r.VERSIONS)+'。它含MTX读取和转换，不能把SpMV阶段变化率当作全程序变化率。大任务复用旧v2，观察到的差值不能直接归为新算术内核收益。',
  '', '## 关键输入与此前八份退化输入','',
  '| 输入 | T | R | 原始/ms | v2/ms | v2.2/ms | 本版/ms | 相对v2 | 相对v2.2 | 路径/实际T |','| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
 for c in cases:
  if c['phase']!='critical':continue
  lines.append(f'| {c["matrix"]} | {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v221_ms"]:.3f} | {c["v221_vs_v2_percent"]:+.2f}% | {c["v221_vs_v22_percent"]:+.2f}% | {c["route"]}/{c["actual_threads"]} |')
 lines+=['', '对上轮八份相对v2退化输入，本轮逐例增加了与三个控制的配对证据；以下“确认”仅表示同时满足预设>5%中位退化和对应区间完全低于1，不是总体显著性结论。',
  '', '| 输入T12 | 本版相对v2时间 | 相对v2.2时间 | v2/本版区间 | 是否确认>5%退化 |','| --- | ---: | ---: | --- | --- |']
 for p in prior:lines.append(f'| {p["matrix"]} | {p["time_change_vs_v2_percent"]:+.2f}% | {p["time_change_vs_v22_percent"]:+.2f}% | [{p["low95"]:.3f}, {p["high95"]:.3f}] | {p["confirmed_over5_vs_v2"]} |')
 lines+=['', '## 抽样漏选是否修复、额外准备是否回本','',
  '两份旧漏选输入要求所有默认候选都启用empty-runs并记录index_retry=1。补扫/分配计入P，覆盖修复不能代替总成本收益；工作量划分是否有利还需看等行数消融。分项中位数相加不必等于逐进程总成本的中位数。',
  '', '| 输入T12 | v2.2 P/ms | v2.2 E/ms | 本版P/ms | 本版E/ms | 本版重试/ms | 相对v2.2总时间 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
 for c in misses:
  a=g[('critical',c['matrix'],12,9,'v22')];b=g[('critical',c['matrix'],12,9,'v221')]
  lines.append(f'| {c["matrix"]} | {1000*med(a,"prepare_s"):.3f} | {1000*med(a,"execute_s"):.3f} | {c["prepare_ms"]:.3f} | {c["execute_ms"]:.3f} | {1000*med(b,"retry_s"):.3f} | {c["v221_vs_v22_percent"]:+.2f}% |')
 lines+=['', '## 旧回归集、新保留集及全部负结果','']
 for label,cs in [('old_T12',old),('new_T12',new)]:
  lines.append(f'{label}共{len(cs)}份，以原始为控制：'+ '；'.join(v+'（'+describe(groups[label][v])+'）' for v in ['v2','v22','v221'])+'。')
 lines+=['', '±5%只是描述刻度，不是逐例显著性。旧输入zero/cache-small/wide为R100，其他R9；新输入存储项数<20000时R100，其余R9。每个同条件四方R/类型/对称处理一致。',
  '', '| 组 | 输入 | T | R | 原始/ms | v2/ms | v2.2/ms | 本版/ms | 相对原始 | 相对v2.2 | 路径/实际T |','| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
 for c in cases:
  if c['phase'] not in ['screen','heldout']:continue
  lines.append(f'| {c["phase"]} | {c["matrix"]} | {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v221_ms"]:.3f} | {c["v221_vs_original_percent"]:+.2f}% | {c["v221_vs_v22_percent"]:+.2f}% | {c["route"]}/{c["actual_threads"]} |')
 lines+=['', 'T12相对v2.2最差的10个条件（保留微小时间的百分比，并列P/E避免错归因）：','',
  '| 输入 | 相对v2.2总时间 | v2.2 P/ms | v2.2 E/ms | 本版P/ms | 本版E/ms |','| --- | ---: | ---: | ---: | ---: | ---: |']
 for c in sorted(t12,key=lambda c:c['v221_vs_v22_percent'],reverse=True)[:10]:
  a=g[(c['phase'],c['matrix'],12,c['repeat'],'v22')]
  lines.append(f'| {c["matrix"]} | {c["v221_vs_v22_percent"]:+.2f}% | {1000*med(a,"prepare_s"):.3f} | {1000*med(a,"execute_s"):.3f} | {c["prepare_ms"]:.3f} | {c["execute_ms"]:.3f} |')
 lines+=['', '## 消融与同二进制诊断','',
  '下表各为额外5进程组。最终默认串行列验证，parallel是显式实验候选；不是默认又偷偷并行。policy=v2委托旧准备与计算；empty-off保留零矩阵路径；rows只改变索引缓存边界，备用v2分区日志可能仍为work。小差值不直接作因果结论。',
  '', '| 输入 | 变体 | R | P/ms | E/ms | total/ms | 实际T |','| --- | --- | --- | ---: | ---: | ---: | --- |']
 for (phase,m,t,R,v),a in sorted(g.items()):
  if phase=='ablations':lines.append(f'| {m} | {v} | {R} | {1000*med(a,"prepare_s"):.3f} | {1000*med(a,"execute_s"):.3f} | {1000*med(a):.3f} | '+','.join(sorted({x['actual_threads'] for x in a}))+' |')
 if (H/'diagnostic.json').exists():
  lines+=['', '同二进制每配置只有一个独立进程：8后端各一次预热、16轮轮转、每个顺序位两次。执行器使用同一批生产对象；original仍保留原生产浮点编译方式。多个计划同时存活，不能代替单计划独立进程的主测量。',
   '', '| 输入 | 后端 | P/ms（一次） | E/ms（内部中位数） | 实际T |','| --- | --- | ---: | ---: | --- |']
  for d in json.loads((H/'diagnostic.json').read_text()):
   for prep in [x for x in d['records'] if x['type']=='prepare']:
    samples=[x for x in d['records'] if x['type']=='sample' and x['backend']==prep['backend']]
    lines.append(f'| {d["matrix"]} | {prep["backend"]} | {prep["prepare_s"]*1000:.3f} | {1000*med(samples,"execute_s"):.3f} | '+','.join(map(str,sorted({x['actual_threads'] for x in samples})))+' |')
 lines+=['', '## 正确性、资源和结论边界','',
  '- v2/v2.2/v2.2.1分别每配置5368/1007/1032项检查，在native T1/12/24、portable T12、ASan+UBSan T1/12/24共21组配置通过；旧测试及数值源文件保留。最终CLI默认调整另做目标次数、非法选项及实际团队限制检查。',
  '- 489组核验包括479组完整输出和10组四版本类型/对称兼容。合成四分之一值使用精确参考；10份真实矩阵先按运行类型转f32，再以独立float64参考和逐行误差界核验，输出精度50。不得称所有真实误差为0。',
  '- 精确索引重试和work边界不改变数值核；非零初始y、逐次x/values变化、特殊浮点、空行加零、预算/分配失败、非法结构、R0和actual-team回退有单元覆盖。没有缓存Ax或省略完整列检查。',
  f'- 正式进程最大RSS {max(int(x["max_rss_kib"]) for x in rows)/1024:.2f}MiB，最大major faults {max(int(x["major_faults"]) for x in rows)}，最大保留辅助payload {max(int(x["extra_bytes"]) for x in rows)}B。它们分别是全程序资源峰值与计划保留量，不能混同准备过程中实测动态分配峰值。',
  '- 原始自动向量化开启，csr.c/spmv_v2.c/spmv_v22.c未改。链接前代码/源码相同不保证最终地址、缓存、NUMA放置、频率或负载一致；执行差异未由硬件计数器归因，不直接断言都是噪声或某条指令收益。',
  '- 新增并行列检查候选在独立校准中未显示足够稳定收益，故提交前禁用默认并行；完整初始90个命令和校准决策保留，正式数据之后没有改规则。',
  '- 未测DRAM控制器、STREAM、硬件缓存失效，未锁宿主机频率/后台负载；结论只针对记录环境。逐例区间未校正多重比较，胜负计数没有真实工作负载权重。',
  '', '![主矩阵R9](figures/large-R9.png)', '', '![主条件配对区间](figures/main-pairs.png)', '', '[旧68份T12图](figures/old-T12.png) · [新12份T12图](figures/new-T12.png)。速度比>1表示快于原始，实际团队可不同。',
  '', '完整逐次记录见measurements.csv/raw；复现与校准调整见README；共同门槛与工作分支见decision.json/git-provenance.json。']
 (H/'结果分析.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(gates=gates,failed_gates=failed,accepted=accept,primary=maincost,old=decision['old_T12'],new=decision['new_T12']),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
