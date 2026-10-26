#!/usr/bin/env python3
"""Report every result, including regressions; never changes code or profile."""
import csv,json,statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
import run_experiments as run
H=run.HERE
def median(rows,key='total_s'):return statistics.median(float(x[key]) for x in rows)
def describe_counts(c):return f'快超过5%：{c["faster_over5"]}例，±5%内：{c["within5"]}例，慢超过5%：{c["slower_over5"]}例'
def main():
 rows=run.records();groups=defaultdict(list)
 for r in rows:groups[(r['phase'],r['matrix'],int(r['threads']),int(r['repeat']),r['variant'])].append(r)
 rng=np.random.default_rng(20261026);paired=[]
 blocks=defaultdict(list)
 for r in rows:
  if r['pair']:blocks[(r['phase'],r['matrix'],int(r['threads']),int(r['repeat']),r['pair'])].append(r)
 comparisons=defaultdict(list)
 for (phase,m,t,R,pid),rs in blocks.items():
  assert len(rs)==2
  candidate=next(x for x in rs if x['variant']=='v21');control=next(x for x in rs if x['variant']!='v21')
  comparisons[(phase,m,t,R,control['variant'])].append((float(control['total_s']),float(candidate['total_s'])))
 for (phase,m,t,R,control),pairs in sorted(comparisons.items()):
  a=np.array(pairs);ratios=a[:,0]/a[:,1];boot=np.median(ratios[rng.integers(0,len(pairs),size=(20000,len(pairs)))],axis=1)
  paired.append(dict(phase=phase,matrix=m,threads=t,repeat=R,control=control,pairs=len(pairs),
   median_pair_speedup=float(np.median(ratios)),low95=float(np.quantile(boot,.025)),high95=float(np.quantile(boot,.975)),
   control_total_s_median=float(np.median(a[:,0])),candidate_total_s_median=float(np.median(a[:,1])),
   pair_speedups=ratios.tolist()))
 run.save('paired-analysis.json',paired)
 cases=[]
 for (phase,m,t,R,v),rs in sorted(groups.items()):
  if v!='v21' or phase_not_supported(phase):continue
  orig=groups.get((phase,m,t,R,'original'));v2=groups.get((phase,m,t,R,'v2'))
  if not orig or not v2:continue
  a,b,c=median(orig),median(v2),median(rs)
  cases.append(dict(phase=phase,matrix=m,threads=t,repeat=R,original_ms=1000*a,v2_ms=1000*b,v21_ms=1000*c,
   v2_vs_original_percent=100*(b/a-1),v21_vs_original_percent=100*(c/a-1),v21_vs_v2_percent=100*(c/b-1),
   prepare_ms=1000*median(rs,'prepare_s'),execute_ms=1000*median(rs,'execute_s'),
   selected=','.join(sorted({r['selected'] for r in rs})),actual_threads=','.join(sorted({r['actual_threads'] for r in rs})),
   prepare_threads=','.join(sorted({r['prepare_threads'] for r in rs})),samples_original=len(orig),samples_v2=len(v2),samples_v21=len(rs)))
 with (H/'comparisons.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(cases[0]),lineterminator='\n');w.writeheader();w.writerows(cases)
 t12=[c for c in cases if c['threads']==12 and c['phase'] in ['critical','screen','heldout','large']]
 def counts(cs,key):return {'faster_over5':sum(x[key]<-5 for x in cs),'within5':sum(abs(x[key])<=5 for x in cs),'slower_over5':sum(x[key]>5 for x in cs)}
 old=[c for c in t12 if c['phase']!='heldout'];new=[c for c in t12 if c['phase']=='heldout']
 large_original=[(key[2],median(rs)) for key,rs in groups.items() if key[1]=='large' and key[3]==9 and key[4]=='original' and key[0] in ['large','large-sensitivity']]
 best_t,best_total=min(large_original,key=lambda x:x[1]);candidate=groups[('large','large',24,9,'v21')];v2=groups[('large','large',24,9,'v2')]
 ct,bt=median(candidate),median(v2);pi=next(x for x in paired if x['phase']=='large' and x['threads']==24 and x['control']=='original')
 primary_original=(ct<=.95*best_total and pi['low95']>1 and best_t==24)
 primary_v2=ct<=1.03*bt
 critical=[c for c in cases if c['phase']=='critical'];worst=max(c['v21_vs_original_percent'] for c in critical)
 robust=counts(old,'v21_vs_original_percent')['slower_over5']<counts(old,'v2_vs_original_percent')['slower_over5']
 accept=primary_original and primary_v2 and robust and worst<=5
 decision=dict(original_best_tested_threads=best_t,original_best_total_s=best_total,v21_cap24_total_s=ct,v2_t24_total_s=bt,
  v21_time_change_vs_original_best_percent=100*(ct/best_total-1),v21_time_change_vs_v2_percent=100*(ct/bt-1),
  same_cap24_paired_low95=pi['low95'],same_cap24_paired_high95=pi['high95'],
  primary_original_pass=primary_original,primary_v2_pass=primary_v2,old_development_negative_count_improved=robust,
  worst_critical_time_change_percent=worst,critical_all_within5=worst<=5,accepted_as_robust_upgrade=accept,
  branch_action='keep optimization/v2.1' if accept else 'switch working checkout back to optimization/v2; keep v2.1 commit and remote branch',
  limits='If best original team differs from24, same-cap24 CI does not validate that best-team comparison; report inconclusive rather than extrapolate.',
  old_T12={'n':len(old),'v2':counts(old,'v2_vs_original_percent'),'v21':counts(old,'v21_vs_original_percent')},
  new_T12={'n':len(new),'v2':counts(new,'v2_vs_original_percent'),'v21':counts(new,'v21_vs_original_percent')})
 run.save('decision.json',decision)
 lines=['# v2.1 实验结果与适用范围','',
  '源码先提交并推送，随后使用固定提交构建，正式计时期间没有修改代码/profile。v2.1为v2的直接子分支；master与v2均保留。',
  '',f'正式性能进程共 **{len(rows)}** 个；52个输入。结果指标为逐进程准备+执行+清理后取中位数；全程wall另列。',
  '', '## 1. 主大矩阵与分支判定','',
  f'原始R9最佳已测团队为{best_t}，total={best_total:.6f}s；v2.1请求上限24时total={ct:.6f}s，对该原始配置时间变化{100*(ct/best_total-1):+.2f}%；同批v2为{bt:.6f}s，v2.1相对它变化{100*(ct/bt-1):+.2f}%。',
  '',f'请求上限24时，相邻配对的原始/v2.1加速比区间为[{pi["low95"]:.3f},{pi["high95"]:.3f}]。若原始最佳已测团队不是24，这个区间不能外推为对最佳团队的区间。',
  '', '本条件v2.1实际选择'+','.join(sorted({r['selected'] for r in candidate}))+'，实际线程'+','.join(sorted({r['actual_threads'] for r in candidate}))+'；v2实际选择'+','.join(sorted({r['selected'] for r in v2}))+'。应先将差异理解为策略选择结果，不能仅凭进程中位数归因于某个内核指令。',
  '', '**判定：'+('通过本轮稳健升级门槛，保留v2.1工作分支。' if accept else '未通过本轮稳健升级门槛，工作区切回v2；v2.1代码和远端分支保留，不合并。')+'**',
  '', '采用预先约定的主目标、对v2不超过3%退化、旧输入退化数减少和关键组不超过5%退化等共同门槛。门槛是工程选择，不是普遍定理。',
  '', '| 请求上限 | R | 原始total/ms | v2 total/ms | v2.1 total/ms | v2.1 P/ms | v2.1实际策略/线程 |',
  '| --- | --- | ---: | ---: | ---: | ---: | --- |']
 for c in sorted([c for c in cases if c['matrix']=='large'],key=lambda c:(c['threads'],c['repeat'])):
  lines.append(f'| {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v21_ms"]:.3f} | {c["prepare_ms"]:.3f} | {c["selected"]}; T={c["actual_threads"]} |')
 lines+=['',f'主大矩阵R9、上限24的全进程wall中位数：原始{median(groups[("large","large",24,9,"original")],"wall_s"):.2f}s，v2 {median(v2,"wall_s"):.2f}s，v2.1 {median(candidate,"wall_s"):.2f}s。它包含MTX读取和转换，不能把SpMV阶段变化率当作全程序变化率。']
 lines+=['','主条件中每个控制10个进程，v2.1来自两组配对共20个；表中使用该条件全部样本中位数。区间分别只用对应控制的10个相邻进程对，配对点值另见paired-analysis.json。R敏感性及T1补充每方5个进程，不混为同一配对设计。',
  '', '## 2. 关键退化组：不删负结果','',
  '| 输入 | 上限T | 原始/ms | v2/ms | v2.1/ms | v2.1相对原始时间 | v2.1策略/实际T |','| --- | --- | ---: | ---: | ---: | ---: | --- |']
 for c in critical:lines.append(f'| {c["matrix"]} | {c["threads"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v21_ms"]:.3f} | {c["v21_vs_original_percent"]:+.2f}% | {c["selected"]}/{c["actual_threads"]} |')
 lines+=['','## 3. 逐例回归与新保留集','',
  f'旧输入T12共{len(old)}例，以原始项目为控制：v2（{describe_counts(decision["old_T12"]["v2"])}）；v2.1（{describe_counts(decision["old_T12"]["v21"])}）。新输入T12共{len(new)}例：v2（{describe_counts(decision["new_T12"]["v2"])}）；v2.1（{describe_counts(decision["new_T12"]["v21"])}）。这些计数不是逐例显著性结论，也不是实际工作负载权重。',
  '',f'直接以v2为控制，旧输入T12的v2.1为（{describe_counts(counts(old,"v21_vs_v2_percent"))}），新输入T12为（{describe_counts(counts(new,"v21_vs_v2_percent"))}）。小输入在原始多线程前取得大加速，也可能仍明显弱于v2已有串行策略，两种对照必须同时看。',
  '', '本轮旧输入的zero/cache-small/wide使用R100，其余使用R9；旧heldout-small本轮使用R9，上一轮为R100。因此这里的胜负计数只用于本轮三方同批对照，不与上一轮计数作严格配对。新保留输入按存储项数小于20000时R100、其余R9。',
  '', '| 组别 | 输入 | 上限T | R | 原始/ms | v2/ms | v2.1/ms | 相对原始时间 | 策略/实际T |','| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |']
 for c in cases:
  if c['phase'] not in ['screen','heldout']:continue
  lines.append(f'| {c["phase"]} | {c["matrix"]} | {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v21_ms"]:.3f} | {c["v21_vs_original_percent"]:+.2f}% | {c["selected"]}/{c["actual_threads"]} |')
 lines+=['','## 4. 单项消融','',
  '以下均为额外5进程组。与主组处于不同时间段，不能把其小差值直接当作单项因果贡献；明显差异也需结合一致FP和同线程对照。',
  '', '| 输入 | 后端 | 上限T | P/ms | E/ms（R次合计） | total/ms | 实际T |','| --- | --- | --- | ---: | ---: | ---: | --- |']
 for key,rs in sorted(groups.items()):
  phase,m,t,R,v=key
  if phase=='ablations':lines.append(f'| {m} | {v} | {t} | {1000*median(rs,"prepare_s"):.3f} | {1000*median(rs,"execute_s"):.3f} | {1000*median(rs):.3f} | '+','.join(sorted({x['actual_threads'] for x in rs}))+' |')
 lines+=['','## 5. 正确性、资源与局限','',
  '- 新v2.1在native1/12/24、portable12、ASan+UBSan1/12/24各2465项检查通过；v2对应各5368项回归通过。正式程序使用生产FP选项，测试/诊断与正式计时分离。',
  '- 52输入的全部向量检查覆盖auto、长行和merge；主大矩阵还含匹配通用CSR。合成精确分数输入逐项相等；六个真实输入使用独立float64参考和逐行误差界，不宣称所有真实误差为0。',
  '- 初轮共168组完整向量检查及10组类型/对称兼容检查；最终profile另外在上限24线程对52个输入全部复核（含1200万行主矩阵），全部通过。另有6组最终profile定点复核，原记录分文件保留。',
  '- SHERMAN3初次检查被固定9位小数的文本输出舍零影响，原始/v2/v2.1都相同失败；真实输入统一提高输出精度50后重新核对。初次记录与诊断保留。这是校验序列化修正，不是计算代码修复。',
  '- 校准进程内918观察不是独立性能样本；拟合有残差，8MiB分组不是物理缓存容量。正式计时前剔除只有一个尺寸点的6个模型，原profile、SHA及修正原因完整保留，未按正式成绩重拟合。',
  '- 模型对首次/稳态缓存用近似，不能准确预测所有规模与局部性。原始CSR自动向量化保留；全局fast-math、Ax缓存、减少R、删去准备时间均未使用。',
  '- 校准的最大x长度4000003，主大矩阵为12000000；规则把工作集仅分为两组，存在超出训练规模/局部性的外推。它是可定位的覆盖缺口，但没有独立测缓存/DRAM，不能仅由此宣称已经证明硬件瓶颈。短8的stream模型因尺寸点不足而没有进入最终auto，排除本身不能代替补足校准证据。',
  f'- 本批最大RSS={max(int(r["max_rss_kib"]) for r in rows)/1024:.2f}MiB，最大major faults={max(int(r["major_faults"]) for r in rows)}；新增元数据最大{max(int(r["extra_bytes"]) for r in rows)}字节。RSS可能由COO+CSR更早阶段决定，不当作额外数组大小。',
  '- 没有锁定宿主机频率/负载、没有DRAM控制器或STREAM测量。PASSIVE下等待会影响最优团队；结果不代表其他等待策略或机器。',
  '', '完整逐次数据见[measurements.csv](measurements.csv)、[配对区间](paired-analysis.json)、[决策](decision.json)和[README](README.md)。']
 (H/'结果分析.md').write_text('\n'.join(lines)+'\n')
 run.save('comparison-cases.json',cases)
 print(json.dumps(decision,ensure_ascii=False,indent=2))
def phase_not_supported(phase):return phase not in ['critical','screen','heldout','large','large-sensitivity']
if __name__=='__main__':main()
