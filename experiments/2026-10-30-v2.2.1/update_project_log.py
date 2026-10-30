#!/usr/bin/env python3
"""Append once after final analysis; preserve the entire design commit prefix."""
import hashlib,json,subprocess
import run_experiments as r
H=r.HERE
def main():
 f=r.MATERIALS/'项目日志.md';before=f.read_bytes();base=subprocess.check_output(['git','show','f6e247a:项目日志.md'],cwd=r.MATERIALS)
 assert before==base,'Journal changed since design; preserve edits instead of overwriting.'
 d=json.loads((H/'decision.json').read_text());cs=json.loads((H/'comparison-cases.json').read_text())
 accepted=d['accepted_as_robust_upgrade'];expected='optimization/v2.2.1' if accepted else 'optimization/v2'
 assert subprocess.check_output(['git','branch','--show-current'],cwd=r.CORE,text=True).strip()==expected
 lines=['','### 优化方案v2.2.1实现与实验记录','',
  '- 资料main设计已推送f6e247a（优化方案v2.2.1设计）。核心明确从v2.2的10f6b89创建optimization/v2.2.1，实现提交并推送dfb4ae2（优化方案v2.2.1实现），之后才开始固定提交的正式四方实验。master、v2、v2.2均保留原提交。',
  '- 完整统计之后按真实非空行数重试索引，修复64点均匀抽样混叠漏选；索引缓存边界使用已有rows/work策略；普通任务直接复用v2执行器，保留resident串行与少数巨行两线程。原始CSR/v2/v2.2数值源不变，空行仍加零，没有缓存Ax。',
  '- 独立90个CLI校准观察没有支持默认并行列检查，因此在代码提交前把auto设为串行，保留显式parallel供正式消融。原始校准命令、时点默认、程序哈希、决策及最终CLI验证均留档。该调整早于正式输入和计时，正式结果之后没有调参。',
  '- v2/v2.2/v2.2.1每配置分别5368/1007/1032项检查；native1/12/24、portable12、ASan+UBSan1/12/24共21组配置全部通过。80份正式输入含旧68份回归及12份新保留结构，489组完整向量/四版本类型兼容核验通过；真实矩阵使用独立float64参考和误差界，不声称全部误差0。',
  '- 正式进程3369个：critical1560、screen1000、heldout480、large80、large-sensitivity89、ablations160；相邻随机AB/BA进程对820组。主T24/R9与v2预先增加至20对，与原始/v2.2各10对；旧8份退化输入也升级为配对证据。P包含补扫、分配及全部验证，wall另列。',
  '', '#### 超大矩阵四方总成本（P+E+清理）','',
  '| T | R | 原始/ms | v2/ms | v2.2/ms | v2.2.1/ms | 本版执行器/实际T |',
  '| --- | --- | ---: | ---: | ---: | ---: | --- |']
 for c in sorted([c for c in cs if c['matrix']=='large'],key=lambda c:(c['threads'],c['repeat'])):
  lines.append(f'| {c["threads"]} | {c["repeat"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v221_ms"]:.3f} | {c["executor"]}/{c["actual_threads"]} |')
 p=d['main_pairs']['v2']
 lines+=['',f'原始R9最佳已测线程为{d["original_best_tested_threads"]}。本版T24相对最佳原始总时间{d["v221_vs_original_best_percent"]:+.2f}%，相对v2 {d["v221_vs_v2_percent"]:+.2f}%，相对v2.2 {d["v221_vs_v22_percent"]:+.2f}%。v2/本版配对速度比中位数{p["median_pair_speedup"]:.3f}，95%区间[{p["low95"]:.3f}, {p["high95"]:.3f}]。配对点值和候选合并40样本中位数之比不同；区间包含1不能称确定变慢或等效。',
  '', '#### 原有收益与漏选修复的成本','',
  '| 输入T12 | 原始/ms | v2/ms | v2.2/ms | 本版/ms | 本版相对v2.2总时间 |',
  '| --- | ---: | ---: | ---: | ---: | ---: |']
 for name in ['bcsstk18','heldout-two-giants','empty99','v22-empty90','v22-empty99']:
  c=next(c for c in cs if c['matrix']==name and c['threads']==12 and c['phase']=='critical')
  lines.append(f'| {name} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v22_ms"]:.3f} | {c["v221_ms"]:.3f} | {c["v221_vs_v22_percent"]:+.2f}% |')
 lines+=['', '两份旧90%/99%漏选输入实际启用empty-runs且index_retry=1，覆盖缺口已修复；但补扫/分配仍会增加P，不能将“选到了路径”当作“总耗时一定改善”。完整分项、消融及同二进制轮转单列；内部轮转不是独立进程重复。',
  '', '#### 全量负结果与最终分支','']
 for key,label in [('old_T12','旧68输入'),('new_T12','新12输入')]:
  item=d[key];lines.append(f'{label}T12中相对原始慢超过5%的数量：v2 {item["v2"]["slower_over5"]}，v2.2 {item["v22"]["slower_over5"]}，本版 {item["v221"]["slower_over5"]}。计数只是描述，不代表真实工作负载权重或逐例显著性。')
 lines+=['', '共同门槛未通过项目：'+('；'.join(d['failed_gate_descriptions']) if d['failed_gates'] else '无')+'。旧8份回退条件的配对区间、所有负样本与最差值均保留。未测硬件缓存/DRAM、未锁宿主机频率，不将E差异直接归因于某个硬件原因。',
  '', ('共同门槛通过，核心工作区保留 **optimization/v2.2.1**。' if accepted else '共同门槛未通过，按要求将核心工作区恢复 **optimization/v2**并重建v2程序；远端optimization/v2.2.1和dfb4ae2保留供审核。')+' 没有合并master或重写历史。',
  '', '资料main提交名 **2026.10.30v2.2.1实验记录**，包括原始日志、固定源码/输入/程序哈希、图表、诊断、准入判断及审计。结果提交号查看本节所属Git提交，不作内部自引用。',
  '', '入口：[实验说明](experiments/2026-10-30-v2.2.1/README.md)、[四方结果](experiments/2026-10-30-v2.2.1/结果分析.md)、[逐进程数据](experiments/2026-10-30-v2.2.1/measurements.csv)、[配对区间](experiments/2026-10-30-v2.2.1/paired-analysis.json)、[决策](experiments/2026-10-30-v2.2.1/decision.json)、[审计](experiments/2026-10-30-v2.2.1/audit.json)。','']
 suffix='\n'.join(lines).encode();f.write_bytes(before+suffix)
 r.save('project-log-update.json',dict(prefix_bytes=len(before),prefix_sha256=hashlib.sha256(before).hexdigest(),appended_bytes=len(suffix),original_prefix_preserved=f.read_bytes()[:len(before)]==before,final_sha256=r.sha(f)))
 print('Appended v2.2.1 results; all previously committed journal bytes preserved')
if __name__=='__main__':main()
