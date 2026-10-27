#!/usr/bin/env python3
"""Append experiment results once; preserve all previously committed bytes."""
import hashlib,json,subprocess
import run_experiments as r
H=r.HERE
def main():
 decision=json.loads((H/'decision.json').read_text());cs=json.loads((H/'comparison-cases.json').read_text())
 journal=r.MATERIALS/'项目日志.md';before=journal.read_bytes()
 committed=subprocess.check_output(['git','show','645b292:项目日志.md'],cwd=r.MATERIALS)
 assert before==committed,'Journal changed after design commit; do not overwrite edits.'
 kept=decision['accepted_as_robust_upgrade'];branch='optimization/v2.2' if kept else 'optimization/v2'
 assert subprocess.check_output(['git','branch','--show-current'],cwd=r.CORE,text=True).strip()==branch
 p=decision['same_cap24_original_pair'];v=decision['same_cap24_v2_pair']
 lines=['','### 优化方案v2.2实现与实验记录','',
  '- 设计先在资料main提交并推送 `645b292`（**优化方案v2.2设计**）；核心从v2 `9b652e8`另建 `optimization/v2.2`，代码提交并推送 `10f6b89`（**优化方案v2.2**）。之后才开始正式实验。没有从v2.1创建，也没有合并到master。',
  '- 大任务保留原v2路径；小任务使用普通循环完成安全检查并融合行统计，受限resident任务串行；高空行率采用非空行索引和连续输出run，空行仍执行y+=+0；对符合原v2 merge条件的少数巨行小任务限制为两线程。没有外部profile、Ax缓存或全局fast-math，原始CSR和v2内核源码未改。',
  '- 180个独立CLI校准观察先于代码提交；随后规则冻结。68个正式输入：此前52份均作开发回归，新增12份合成保留输入及4份NIST真实矩阵（BCSSTK14、BCSSTK15、SHERMAN1、WEST0655），新保留集不用于调参。',
  '- 正式性能1960个顺序执行进程：critical560、screen660、heldout480、large80、large-sensitivity60、ablations120；相邻随机AB/BA共320对，分别对照原始和v2。主要指标为逐进程准备+R次执行+清理后取中位数，wall另列。',
  '- 新v2.2每配置1007项检查，原v2每配置5368项回归，native1/12/24、portable12、ASan+UBSan1/12/24全部通过。另有233组完整向量/类型兼容检查；真实矩阵使用独立float64参考和误差界，输出精度50，避免文本舍零。',
  '', '#### 超大矩阵同批三方比较','',
  '| 请求T | R | 原始/ms | v2/ms | v2.2/ms | v2.2路径/实际T |',
  '| --- | --- | ---: | ---: | ---: | --- |']
 for c in sorted([c for c in cs if c['matrix']=='large'],key=lambda x:(x['threads'],x['repeat'])):
  lines.append(f'| {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["route"]}/{c["actual_threads"]} |')
 lines+=['',f'R9原始最佳已测团队为{decision["original_best_tested_threads"]}。v2.2请求24线程时相对原始最佳已测时间变化{decision["v22_time_change_vs_original_best_percent"]:+.2f}%，相对同批v2变化{decision["v22_time_change_vs_v2_percent"]:+.2f}%。同上限24的原始/v2.2配对速度比区间[{p["low95"]:.3f}, {p["high95"]:.3f}]，v2/v2.2为[{v["low95"]:.3f}, {v["high95"]:.3f}]。若最佳原始线程不同，该区间不能外推。',
  '', '#### 关键缺陷修复及保留的负结果','',
  '| 输入（请求T12） | R | 原始/ms | v2/ms | v2.2/ms | 相对v2时间变化 |',
  '| --- | --- | ---: | ---: | ---: | ---: |']
 for name in ['bcsstk18','heldout-two-giants','empty99','heldout-empty-cluster','giant-row','heavy-clustered','wide']:
  c=next(c for c in cs if c['phase']=='critical' and c['matrix']==name and c['threads']==12)
  lines.append(f'| {name} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v22_vs_v2_percent"]:+.2f}% |')
 for key,label in [('old_T12','旧52输入'),('new_T12','新16输入')]:
  d=decision[key]
  lines+=['',f'{label}T12，相对原始超过5%退化数：v2 {d["v2"]["slower_over5"]}例、v2.2 {d["v22"]["slower_over5"]}例。全部逐例正负结果保留；这些计数是描述统计，不代表工作负载权重或逐例显著性。']
 worst=decision['critical_worst_vs_v2']
 lines+=['',f'关键条件相对v2最差为{worst["matrix"]}/T{worst["threads"]}：{worst["v22_vs_v2_percent"]:+.2f}%。主矩阵复用旧v2内核，不能把其同批时间浮动称为新内核优化。消融和同二进制轮转另列；后者每条件仅一个进程，不冒充独立重复。',
  '', '新空行输入还暴露了确定的策略漏选：64点均匀抽样在v22-empty99中与每100行一个非空行的周期混叠，只采到56/64空行（87.5%）；v22-empty90采到57/64（89.0625%）。两者均未分配非空行索引，完整检查后也没有重试，因此实际走普通CSR/work。正确性不受影响，但不能把这两例当作empty-runs性能。结构复算见sampling-diagnosis.json；正式成绩后没有修改代码。',
  '', '#### 共同门槛及Git交付','',
  ('本轮共同门槛通过，核心工作区保留 **optimization/v2.2**，不合并master。' if kept else '本轮共同门槛未通过，按要求将核心工作区切回 **optimization/v2**并重建v2程序；远端optimization/v2.2及提交保留，不合并master。'),
  '', '准入包含主矩阵对最佳原始至少5%收益、有配对支持、对v2中位退化不超过3%且配对下界≥0.95、关键条件无新增超过5%退化、改善至少两类缺陷，以及旧/新T12对原始退化数均不增加。详细逐项判断及限制见decision.json，不事后修改门槛。',
  '', '资料main提交名 **2026.10.27v2.2实验记录**；本提交包含全部原始日志、来源、图表、诊断、审计及日志更新。资料结果提交号从所属Git提交查看，避免自引用。没有改动Git日志显示配置、重写历史或重复提交旧结果。',
  '', '入口：[实验说明](experiments/2026-10-27-v2.2/README.md)、[结果分析](experiments/2026-10-27-v2.2/结果分析.md)、[逐次数据](experiments/2026-10-27-v2.2/measurements.csv)、[配对区间](experiments/2026-10-27-v2.2/paired-analysis.json)、[准入判定](experiments/2026-10-27-v2.2/decision.json)、[审计](experiments/2026-10-27-v2.2/audit.json)。','']
 suffix='\n'.join(lines).encode();journal.write_bytes(before+suffix)
 r.save('project-log-update.json',dict(prefix_bytes=len(before),prefix_sha256=hashlib.sha256(before).hexdigest(),appended_bytes=len(suffix),original_prefix_preserved=journal.read_bytes()[:len(before)]==before,final_sha256=hashlib.sha256(journal.read_bytes()).hexdigest()))
 print('Appended project log; prior bytes preserved')
if __name__=='__main__':main()
