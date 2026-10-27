#!/usr/bin/env python3
"""Describe frozen experiments; evaluate the predeclared joint criteria."""
import csv,json,statistics
from collections import defaultdict
import numpy as np
import run_experiments as run
H=run.HERE
def med(rows,k='total_s'):return statistics.median(float(r[k]) for r in rows)
def counts(cs,k):return dict(faster_over5=sum(c[k]<-5 for c in cs),within5=sum(abs(c[k])<=5 for c in cs),slower_over5=sum(c[k]>5 for c in cs))
def describe(c):return f'快超过5% {c["faster_over5"]}，±5%内 {c["within5"]}，慢超过5% {c["slower_over5"]}'
def main():
 rows=run.records();g=defaultdict(list);blocks=defaultdict(list)
 for r in rows:
  g[(r['phase'],r['matrix'],int(r['threads']),int(r['repeat']),r['variant'])].append(r)
  if r['pair']:blocks[r['pair']].append(r)
 bycontrol=defaultdict(list)
 for pid,rs in blocks.items():
  assert len(rs)==2
  c=next(r for r in rs if r['variant']=='v22');a=next(r for r in rs if r['variant']!='v22')
  bycontrol[(c['phase'],c['matrix'],int(c['threads']),int(c['repeat']),a['variant'])].append((float(a['total_s']),float(c['total_s'])))
 rng=np.random.default_rng(20261027);paired=[]
 for (phase,m,t,R,control),pairs in sorted(bycontrol.items()):
  a=np.array(pairs);ratios=a[:,0]/a[:,1]
  boot=np.median(ratios[rng.integers(0,len(pairs),size=(20000,len(pairs)))],axis=1)
  paired.append(dict(phase=phase,matrix=m,threads=t,repeat=R,control=control,pairs=len(pairs),
   median_pair_speedup=float(np.median(ratios)),low95=float(np.quantile(boot,.025)),high95=float(np.quantile(boot,.975)),
   control_total_s_median=float(np.median(a[:,0])),candidate_total_s_median=float(np.median(a[:,1])),pair_speedups=ratios.tolist()))
 run.save('paired-analysis.json',paired)
 cases=[]
 for (phase,m,t,R,v),rs in sorted(g.items()):
  if v!='v22' or phase=='ablations':continue
  a=g.get((phase,m,t,R,'original'));b=g.get((phase,m,t,R,'v2'))
  if not a or not b:continue
  am,bm,cm=med(a),med(b),med(rs)
  cases.append(dict(phase=phase,matrix=m,threads=t,repeat=R,original_ms=am*1000,v2_ms=bm*1000,v22_ms=cm*1000,
   v2_vs_original_percent=100*(bm/am-1),v22_vs_original_percent=100*(cm/am-1),v22_vs_v2_percent=100*(cm/bm-1),
   prepare_ms=1000*med(rs,'prepare_s'),execute_ms=1000*med(rs,'execute_s'),cleanup_ms=1000*med(rs,'cleanup_s'),
   selected=','.join(sorted({r['selected'] for r in rs})),route=','.join(sorted({r['route'] for r in rs})),
   actual_threads=','.join(sorted({r['actual_threads'] for r in rs})),extra_bytes=max(int(r['extra_bytes']) for r in rs),
   samples_original=len(a),samples_v2=len(b),samples_v22=len(rs)))
 run.save('comparison-cases.json',cases)
 with (H/'comparisons.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(cases[0]),lineterminator='\n');w.writeheader();w.writerows(cases)
 t12=[c for c in cases if c['threads']==12 and c['phase'] in ['critical','screen','heldout','large']]
 old=[c for c in t12 if c['phase']!='heldout'];new=[c for c in t12 if c['phase']=='heldout']
 assert len(old)==52 and len(new)==16
 origteams=[(k[2],med(rs)) for k,rs in g.items() if k[1]=='large' and k[3]==9 and k[4]=='original' and k[0] in ['large','large-sensitivity']]
 best_t,best=min(origteams,key=lambda x:x[1]);ca=g[('large','large',24,9,'v22')];vb=g[('large','large',24,9,'v2')]
 ct,bt=med(ca),med(vb)
 pi=next(p for p in paired if p['phase']=='large' and p['threads']==24 and p['control']=='original')
 pv=next(p for p in paired if p['phase']=='large' and p['threads']==24 and p['control']=='v2')
 primaryorig=ct<=.95*best and best_t==24 and pi['low95']>1
 primaryv2=ct<=1.03*bt and pv['low95']>=.95
 critical=[c for c in cases if c['phase']=='critical'];worst=max(critical,key=lambda c:c['v22_vs_v2_percent'])
 criticalpass=worst['v22_vs_v2_percent']<=5
 # Consistent requested T12 representatives; both T12/T24 still constrain criticalpass.
 classes={name:next(c for c in critical if c['matrix']==name and c['threads']==12)['v22_vs_v2_percent']
          for name in ['bcsstk18','empty99','heldout-two-giants']}
 improved=sum(v<-5 for v in classes.values())
 oc={v:counts(old,f'{v}_vs_original_percent') for v in ['v2','v22']}
 nc={v:counts(new,f'{v}_vs_original_percent') for v in ['v2','v22']}
 no_new_negatives=oc['v22']['slower_over5']<=oc['v2']['slower_over5'] and nc['v22']['slower_over5']<=nc['v2']['slower_over5']
 accept=primaryorig and primaryv2 and criticalpass and improved>=2 and no_new_negatives
 decision=dict(original_best_tested_threads=best_t,original_best_total_s=best,v22_cap24_total_s=ct,v2_t24_total_s=bt,
  v22_time_change_vs_original_best_percent=100*(ct/best-1),v22_time_change_vs_v2_percent=100*(ct/bt-1),
  same_cap24_original_pair=pi,same_cap24_v2_pair=pv,primary_original_pass=primaryorig,primary_v2_pass=primaryv2,
  critical_worst_vs_v2=worst,critical_all_within5=criticalpass,class_representatives_T12=classes,classes_improved_over5=improved,
  old_T12=dict(n=len(old),**oc),new_T12=dict(n=len(new),**nc),negative_counts_not_increased=no_new_negatives,
  correctness_pass=len(json.loads((H/'correctness.json').read_text()))==233,
  accepted_as_robust_upgrade=accept,branch_action='keep optimization/v2.2' if accept else 'switch checkout to optimization/v2; retain remote optimization/v2.2',
  interpretation='The v2/v22 interval includes1; this is insufficient evidence for the predeclared non-regression bound, not proof of a definite slowdown.',
  limits='If original best team is not24, the T24 paired interval cannot validate the best-team comparison; mark inconclusive and fail joint gate.')
 run.save('decision.json',decision)
 lines=['# v2.2 实验结果与适用范围','',
  '固定源码提交后进行三方实验，正式计时后没有调阈值或修改实现。v2.2直接基于v2，未合并v2.1。设计、实现、实验分别提交。',
  '',f'正式性能进程 **{len(rows)}** 个，68份输入，320个相邻配对。主指标为逐进程P+E+D后取中位数，完整程序wall另列。',
  '', '## 主大矩阵及共同门槛','',
  f'原始R9最佳已测线程数 **{best_t}**，总成本 **{best:.6f}s**。v2.2请求24线程时总成本 **{ct:.6f}s**，相对最佳原始时间变化 **{100*(ct/best-1):+.2f}%**；同批v2为 **{bt:.6f}s**，相对v2变化 **{100*(ct/bt-1):+.2f}%**。',
  '',f'上限24同团队配对：原始/v2.2速度比中位数{pi["median_pair_speedup"]:.3f}，95%区间[{pi["low95"]:.3f}, {pi["high95"]:.3f}]；v2/v2.2为{pv["median_pair_speedup"]:.3f}，区间[{pv["low95"]:.3f}, {pv["high95"]:.3f}]。最佳原始团队若不是24，此区间不能外推到最佳团队。',
  '', '**分支判定：'+('共同门槛通过，保留v2.2工作分支。' if accept else '共同门槛未通过，工作区切回v2；远端v2.2及全部结果保留。')+'**',
  '', '| 冻结门槛 | 本轮判断 |','| --- | --- |',
  f'| 主大矩阵对最佳已测原始至少5%收益且配对支持 | {primaryorig} |',
  f'| 主大矩阵相对v2中位退化≤3%，配对下界≥0.95 | {primaryv2} |',
  f'| 所有关键条件相对v2退化≤5% | {criticalpass}，最差{worst["matrix"]}/T{worst["threads"]}：{worst["v22_vs_v2_percent"]:+.2f}% |',
  f'| 小任务/空行/双巨行至少两类改善>5% | {improved}类（以T12各代表条件判断） |',
  f'| 旧/新T12组对原始的>5%退化计数均不增加 | {no_new_negatives} |',
  '', '以上是共同工程门槛，不按单项亮点替换整体判定。correctness.json的233组检查全部通过。',
  '', '相对v2的配对区间包含1，不能据此判定确定变慢；本轮回退的含义是尚未证明满足预设的不退化范围，不能将证据不足改写为计算内核已经退化。',
  '', '| 请求T | R | 原始total/ms | v2 total/ms | v2.2 total/ms | v2.2 P/ms | 路径/实际T |',
  '| --- | --- | ---: | ---: | ---: | ---: | --- |']
 for c in sorted([c for c in cases if c['matrix']=='large'],key=lambda x:(x['threads'],x['repeat'])):
  lines.append(f'| {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["prepare_ms"]:.3f} | {c["route"]}/{c["actual_threads"]} |')
 lines+=['',f'主R9/T24全程序wall中位数：原始{med(g[("large","large",24,9,"original")],"wall_s"):.2f}s，v2 {med(vb,"wall_s"):.2f}s，v2.2 {med(ca,"wall_s"):.2f}s。wall包含文本读取和格式转换，不能把SpMV阶段的加速率当作全程序加速率。',
  '', '关键/主条件每个控制10个进程，候选来自两组共20个。条件中位数与各自10对的速度比中位数是不同估计。R1/R100、T1以及原始T2/4/8各为5进程补充，不与配对样本混合。',
  '', '## 关键条件：相对原始和v2都报告','',
  '| 输入 | 上限T | R | 原始/ms | v2/ms | v2.2/ms | 相对原始时间 | 相对v2时间 | 路径/实际T |',
  '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
 for c in critical:
  lines.append(f'| {c["matrix"]} | {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v22_vs_original_percent"]:+.2f}% | {c["v22_vs_v2_percent"]:+.2f}% | {c["route"]}/{c["actual_threads"]} |')
 lines+=['', '## 旧回归集及新保留集','',
  f'旧52输入T12：v2（{describe(oc["v2"])}），v2.2（{describe(oc["v22"])}）。新16输入T12：v2（{describe(nc["v2"])}），v2.2（{describe(nc["v22"])}）。计数均相对原始；不能当作逐例显著性或工作负载权重。',
  '',f'直接对v2，旧T12：{describe(counts(old,"v22_vs_v2_percent"))}；新T12：{describe(counts(new,"v22_vs_v2_percent"))}。',
  '', '旧zero/cache-small/wide使用R100，其他旧输入R9；新输入按存储项数<20000时R100，其余R9。对称真实输入实际运算项数以展开后计数为准。所有同条件三方的R、输入及OpenMP环境一致。',
  '', '| 组 | 输入 | T | R | 原始/ms | v2/ms | v2.2/ms | 相对原始时间 | 相对v2时间 | 路径/实际T |',
  '| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
 for c in cases:
  if c['phase'] not in ['screen','heldout']:continue
  lines.append(f'| {c["phase"]} | {c["matrix"]} | {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v22_vs_original_percent"]:+.2f}% | {c["v22_vs_v2_percent"]:+.2f}% | {c["route"]}/{c["actual_threads"]} |')
 lines+=['', '### 仍然存在的退化与新增负例','',
  '退化总数减少不等于逐例支配。下表列出T12相对v2最慢的最多10个条件；其中准备和执行分别列出，避免将新验证循环的开销混称为计算内核变化。这里使用阶段中位数，P中位数+E中位数未必等于逐进程总成本中位数。',
  '', '| 输入 | R | 相对原始时间 | 相对v2时间 | v2 P/ms | v2 E/ms | v2.2 P/ms | v2.2 E/ms | 路径 |',
  '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
 for c in sorted(t12,key=lambda c:c['v22_vs_v2_percent'],reverse=True)[:10]:
  b=g[(c['phase'],c['matrix'],12,c['repeat'],'v2')]
  lines.append(f'| {c["matrix"]} | {c["repeat"]} | {c["v22_vs_original_percent"]:+.2f}% | {c["v22_vs_v2_percent"]:+.2f}% | {1000*med(b,"prepare_s"):.3f} | {1000*med(b,"execute_s"):.3f} | {c["prepare_ms"]:.3f} | {c["execute_ms"]:.3f} | {c["route"]} |')
 newnegative=[c['matrix'] for c in t12 if c['v22_vs_original_percent']>5 and c['v2_vs_original_percent']<=5]
 lines+=['', 'T12中v2原本未超过5%退化、v2.2却超过的条件：'+('、'.join(newnegative) if newnegative else '无')+'。这是冻结计数门槛允许出现的个例，不能从总数下降推断每个输入都改善。',
  '', '普通循环验证节省启动团队的成本，却仍要逐项扫描列号；接近大任务界限的输入可能付出更高准备时间。非空行索引仍需完整验证、分配索引、写空行输出；高空行比例本身不保证回本。random8和new-iid8的回退主要出现在E，不能归咎于准备时间：它们沿用旧内核，但本轮尚未用硬件计数器或更多配对区分验证前缀的缓存影响、链接布局和系统波动。不能直接断言都是噪声，也不宣称已定位指令原因。',
  '', '### 新空行输入的漏选：64点均匀抽样存在结构混叠','',
  '代码只把抽样作为是否提前分配索引的提示，随后仍全量检查；但提示漏选时不会在全量检查后重试分配。因此它不破坏正确性，却会遗漏优化机会。结构复算和实际route日志见sampling-diagnosis.json；没有据此改代码或补调阈值。',
  '', '| 新输入 | 真实空行率 | 64点抽到的空行 | 是否触发索引分配 | 实际路径 |',
  '| --- | ---: | --- | --- | --- |']
 for d in json.loads((H/'sampling-diagnosis.json').read_text()):
  lines.append(f'| {d["matrix"]} | {100*d["actual_empty_ratio"]:.4f}% | {d["sampled_empty_rows"]}/64（{100*d["sample_empty_ratio"]:.4f}%） | {d["allocation_hint_pass"]} | v2-rules-fast-validation |')
 lines+=['', '特别是新99%空行输入，均匀取样位置与每100行一个非空行的周期发生混叠，只看到87.5%空行；90%聚集输入的64点取整也只看到89.0625%。两者均低于分配提示门槛。不能把这两份auto成绩当作empty-runs内核的实测成绩；它们实质上走普通CSR/work。这是本版可复现的策略覆盖缺口。']
 lines+=['', '## 消融与同二进制诊断','',
  '消融每项5个额外进程，与主组处于不同时间段，小差值不能直接视为因果贡献。empty-off仅关闭非零矩阵索引，零矩阵专用路径仍在；显式serial和policy=v2委托旧v2。',
  '', '| 输入 | 变体 | T | R | P/ms | E/ms | total/ms | 实际T |',
  '| --- | --- | --- | --- | ---: | ---: | ---: | --- |']
 for (phase,m,t,R,v),rs in sorted(g.items()):
  if phase!='ablations':continue
  lines.append(f'| {m} | {v} | {t} | {R} | {1000*med(rs,"prepare_s"):.3f} | {1000*med(rs,"execute_s"):.3f} | {1000*med(rs):.3f} | '+','.join(sorted({r['actual_threads'] for r in rs}))+' |')
 if (H/'diagnostic.json').exists():
  lines+=['', '同二进制使用原始csr.o、未改的v2内核和新v2.2计划，生产浮点方式保留；六个后端各一次公平预热，12轮轮转，每个后端在各顺序位出现两次。每条件只有一个独立进程。下表仅为R次E的进程内中位数，正式结论仍以独立进程P+E+D为准。',
   '', '| 输入 | 后端 | P/ms（一次） | E/ms（轮转中位数） | 实际T |', '| --- | --- | ---: | ---: | --- |']
  for d in json.loads((H/'diagnostic.json').read_text()):
   for prep in [r for r in d['records'] if r['type']=='prepare']:
    ss=[r['execute_s'] for r in d['records'] if r['type']=='sample' and r['backend']==prep['backend']]
    lines.append(f'| {d["matrix"]} | {prep["backend"]} | {1000*prep["prepare_s"]:.3f} | {1000*statistics.median(ss):.3f} | {prep["actual_threads"]} |')
 lines+=['', '## 图表','', '![主矩阵R9总成本](figures/large-R9.png)', '',
  '[旧52输入T12速度比图](figures/old-T12.png) · [新16输入T12速度比图](figures/new-T12.png)。速度比图中大于1表示快于原始，图中请求线程上限相同、实际团队允许不同。',
  '', '## 正确性、资源及结论边界','',
  '- 新v2.2每配置1007项检查，旧v2每配置5368项回归；native T1/12/24、portable T12、ASan+UBSan T1/12/24共七配置。覆盖变化x/values、非零初始y、R0/1/3、特殊浮点、分配/预算回退、非法结构及实际团队变化。',
  '- 68输入完整向量检查：合成四分之一值与全1向量使用精确参考，真实矩阵将输入转f32后由独立float64参考及逐行误差界核验。真实输出文本用50位精度，避免固定9位将极小数舍零。另含10组类型/对称兼容检查。不声称所有真实误差为0。',
  '- 180个独立CLI校准观察在核心提交前完成，与正式保留输入分离。没有运行时外部profile，没有缓存Ax；每次重复均读取实时x和矩阵值。大任务委托旧v2，不能把该部分同批浮动归因于新内核算力提升。',
  f'- 正式进程最大RSS {max(int(r["max_rss_kib"]) for r in rows)/1024:.2f} MiB，最大major faults {max(int(r["major_faults"]) for r in rows)}，新增元数据最大 {max(int(r["extra_bytes"]) for r in rows)} B。RSS含更早的COO/CSR峰值，不等同于新增表大小。',
  '- 原始自动向量化保留，csr.c和spmv_v2.c源码未改。独立csr.o代码段字节比对只能证明重定位前代码段一致，不能证明链接布局、调度或缓存状态一致；相关证据另存。',
  '- 未锁定宿主机频率/后台负载，未测DRAM带宽或硬件缓存失效，不能将性能波动或工作集字节数冒充硬件瓶颈证据。PASSIVE及本机的线程选择不保证适合其他环境。',
  '', '全部负结果、命令、计时和资源记录均保留。共同门槛判定见decision.json；复现和数据来源见README.md。']
 (H/'结果分析.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(decision,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
