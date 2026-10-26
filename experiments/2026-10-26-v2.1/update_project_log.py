#!/usr/bin/env python3
"""Append final measured results to the course log; no Git mutations."""
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent
ROOT=H.parents[1]
def describe(c):return f'快超过5% {c["faster_over5"]}例、±5%内{c["within5"]}例、慢超过5% {c["slower_over5"]}例'
def main():
 decision=json.loads((H/'decision.json').read_text());cases=json.loads((H/'comparison-cases.json').read_text())
 marker='### 优化方案 v2.1 实现与实验结果'
 log=ROOT/'项目日志.md';before=log.read_bytes();assert marker not in before.decode()
 lines=['',marker,'',
  '- 已从v2的 `9b652e8da85b7a1ad255e0b4f8ddadc5e0558f1a` 创建 `optimization/v2.1`，代码提交 `aa1ef3d9bfb93002f19d0bfffdb3074225bb7f15`，名称 **“优化方案v2.1”**。代码先推送GitHub，随后才开始正式性能比较；v1未合并，master与v2保持原提交。',
  '- 实现有效R预检、独立prepare/compute团队选择、单团队完整检查、离线成本profile、O(T)行/merge坐标缓存、按被拆行分配归并所有者及局部长行AVX2候选。默认仍original；未缓存Ax、改变R、全局fast-math或省略非法列检查，空行仍加零。空行压缩没有在本版实现。',
  '- 52个输入：32个旧输入作为开发回归，另有16个新种子/形状合成输入与4个新NIST真实输入（BCSSTK17、WEST0479、SHERMAN3、SAYLR4）。新真实矩阵对称展开、显式零、f32转换等两边相同，来源/头部/哈希留档，MTX不入Git。',
  '- 正式性能共1835个独立进程：critical480、screen375、heldout600、large80、large-sensitivity60、ablations240；280个相邻随机AB/BA进程对分别比较v2.1/原始和v2.1/v2。重复次数敏感性集中超大矩阵上限24线程，未跑满所有线程×R组合。',
  '- v2.1在native1/12/24、portable12、ASan+UBSan1/12/24各2465项检查通过，原v2对应5368项回归通过。全量输出覆盖所有输入及长行/merge/CSR路径；真实矩阵用独立高精度参考和误差界，不称所有误差为0。SHERMAN3首次检查发现原始及优化版本都被固定9位小数输出舍零影响，改用50位校验文本后通过，未修改计算代码。',
  '- 离线校准使用独立形状/种子、一个进程918条内部观察，拟合残差保留；正式计时前排除仅一个尺寸点、无法区分规模斜率与调用固定开销的6个模型，原profile/SHA和原因留档。正式成绩出现后未改代码或模型。',
  '', '#### 超大均匀矩阵 R=9（准备+执行+清理）','',
  '| 请求线程上限 | 原始/ms | v2/ms | v2.1/ms | v2.1实际策略/线程 |','| --- | ---: | ---: | ---: | --- |']
 for c in sorted(cases,key=lambda c:c['threads']):
  if c['matrix']=='large' and c['repeat']==9:
   lines.append(f'| {c["threads"]} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v21_ms"]:.3f} | {c["selected"]}/{c["actual_threads"]} |')
 lines+=['',f'原始最佳已测线程为{decision["original_best_tested_threads"]}。上限24线程的v2.1相对原始最佳已测配置时间变化{decision["v21_time_change_vs_original_best_percent"]:+.2f}%，相对同批v2变化{decision["v21_time_change_vs_v2_percent"]:+.2f}%；原始/v2.1同上限配对加速比95%区间为[{decision["same_cap24_paired_low95"]:.3f},{decision["same_cap24_paired_high95"]:.3f}]。SpMV阶段与包含MTX读取/转换的全进程wall分开报告。',
  '', '#### 缺陷修复结果与保留的负结果','',
  '| 输入（上限12线程、R9） | 原始/ms | v2/ms | v2.1/ms |','| --- | ---: | ---: | ---: |']
 for n in ['heldout-two-giants','heldout-empty-cluster','bcsstk18','empty99','giant-row']:
  c=next(x for x in cases if x['matrix']==n and x['threads']==12 and x['phase']=='critical')
  lines.append(f'| {n} | {c["original_ms"]:.3f} | {c["v2_ms"]:.3f} | {c["v21_ms"]:.3f} |')
 lines+=['', '部分旧退化得到了改善，但主大矩阵上限24时auto回到original，没有保住v2的收益；empty99等仍有退化。不能将本版概括为全面优于v2。模型校准的规模/局部性覆盖有限，原始CSR链接前机器码相同也不保证最终地址和缓存状态相同；同二进制与同步诊断另列，不以进程差值直接推断某个指令的贡献。',
  '',f'本轮旧输入T12描述计数：v2（{describe(decision["old_T12"]["v2"])}），v2.1（{describe(decision["old_T12"]["v21"])}）；新输入T12：v2（{describe(decision["new_T12"]["v2"])}），v2.1（{describe(decision["new_T12"]["v21"])}）。±5%仅为描述刻度，不是逐例显著性判断；个别旧小输入本轮R与上一轮不同，仅作本轮同批比较。',
  '', '#### Git交付与最终工作分支','',
  ('通过本轮稳健升级门槛，工作区保留optimization/v2.1。' if decision['accepted_as_robust_upgrade'] else '未通过本轮稳健升级门槛，按本人要求将核心工作区切回 **optimization/v2** 并重建v2程序；v2.1远端分支及提交保留供复盘，没有合并或删除。'),
  '资料在main提交，名称 **“2026.10.26v2.1实验结果”**，包含完整正负结果、原始记录、校准来源、图表、诊断与审计。资料提交号通过本文件所属提交查看，避免内部自引用。',
  '', '入口：[实验说明](experiments/2026-10-26-v2.1/README.md)、[结果分析](experiments/2026-10-26-v2.1/结果分析.md)、[逐进程数据](experiments/2026-10-26-v2.1/measurements.csv)、[配对区间](experiments/2026-10-26-v2.1/paired-analysis.json)、[分支决策](experiments/2026-10-26-v2.1/decision.json)、[审计](experiments/2026-10-26-v2.1/audit.json)。','']
 appended=('\n'.join(lines)).encode();log.write_bytes(before+appended)
 proof={'before_bytes':len(before),'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'append_only':log.read_bytes().startswith(before)}
 (H/'project-log-update.json').write_text(json.dumps(proof,indent=2)+'\n')
 print('Appended project log results, preserving all prior bytes')
if __name__=='__main__':main()
