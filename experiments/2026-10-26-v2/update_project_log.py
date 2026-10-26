#!/usr/bin/env python3
"""Append the dated final log after report/audit and core Git publication."""
import json
import run_experiments as run
H=run.HERE
def main():
    summary=json.loads((H/'summary.json').read_text())
    decision=json.loads((H/'decision.json').read_text())
    git=json.loads((H/'git-provenance.json').read_text())
    assert json.loads((H/'audit.json').read_text())['status']=='passed'
    def get(phase,n,v,t=12,r=9):
        a=[x for x in summary if x['phase']==phase and x['matrix']==n and x['variant']==v and int(x['threads'])==t and int(x['repeat'])==r]
        assert len(a)==1;return a[0]
    lines=['## 2026.10.26','', '### 优化方案 v2 实现与实验','',
      '- 核心 v2 直接从原始 master `9352c865044f4c8b344d6fe5a277200a89f7a08b` 创建 `optimization/v2`，与 v1 为并列分支；没有合入 v1 提交或内核，原始 csr.c 不变。v1 从固定提交单独构建作对照。',
      '- 实现免格式转换的 CSR8 短行、真正串行入口、按 nnz+rows 的连续行分区，以及作者 merge-spmv CPU 方法的 f32/int64/y+=Ax 适配。预取0/32/128为显式消融，默认0；保持原始默认入口，v2用 --kernel=v2 启用，其他类型沿原始回退。',
      '- 完整验证行指针与列号，融合统计并对大输入并行检查，所有新增成本进入prepare。merge只需64*T字节片段空间，处理巨行跨多个线程、实际团队变化及旧y只加一次；结构/类型变化要求显式重建计划。没有缓存Ax或把R次加法替换为R*Ax。',
      '- 新核心测试在native 1/12/24、portable 12及ASan+UBSan 1/12/24各通过5368项；另重跑v1的850项。165条CLI/兼容性/全量输出记录包含130组完整向量检查；超大矩阵4条v2路径在12线程R=3下逐项核对1200万个输出，精确分数输入误差0。补充检查见64bit-check.json和supplementary-cli-checks.json，不通过巨大实分配测试64位边界。',
      '- 34个输入：原23个、2个校准、7个新种子保留输入及NIST的BCSSTK18/SHERMAN5。后者对称展开/非对称分别验证；真实矩阵按f32误差界检查，没有误称全都逐位或误差0。大文件与构建物保持忽略，生成器、来源、头部和SHA留档。',
      '- 共1640个独立进程样本：先导180，正式1460。其中超大矩阵1/12/24线程×R=1/9/100各10个相邻随机AB/BA进程对，另75个强对照；其余样本覆盖全部极端与保留输入。固定OMP绑定、PASSIVE和无全局fast-math，不删慢样本。独立同二进制诊断为5后端轮转10轮，明确不是额外350个独立进程。',
      '', '#### 超大均匀矩阵 R=9','',
      '下表为进程中位数；单次和P为ms，总计为s。总计按每个样本prepare+execute+cleanup后取中位数，非直接相加分项中位数。',
      '', '| 线程 | 原始单次 | v2单次 | v2准备 | 原始总计 | v2总计 | 总成本加速比 |',
      '| --- | --- | --- | --- | --- | --- | --- |']
    for t in [1,12,24]:
        a=get('large','large','original',t);b=get('large','large','v2-auto',t)
        lines.append(f'| {t} | {a["ms_per_call"]:.3f} | {b["ms_per_call"]:.3f} | {b["prepare_s_median"]*1000:.3f} | {a["total_s_median"]:.6f} | {b["total_s_median"]:.6f} | {a["total_s_median"]/b["total_s_median"]:.3f}× |')
    lines+=['',f'主目标{"通过" if decision["passes_primary"] else "未通过"}预定工程门槛：对原始最佳已测{decision["original_best_threads"]}线程配置，v2请求24线程的总时间降低 **{decision["time_reduction_percent"]:.2f}%**。对应加速比区间约 **[{decision["low95"]:.3f}, {decision["high95"]:.3f}]**；它来自本批配对过程样本，非跨机器保证。5%门槛是本项目约定。',
      '', '#### 适用性、强对照与局限','']
    for n,r in [('heavy-clustered',9),('empty99',9),('cache-small',100)]:
        a=get('screen',n,'original',12,r);b=get('screen',n,'v2-auto',12,r)
        lines.append(f'- {n}，请求12线程、R={r}：原始总计{a["total_s_median"]*1000:.3f} ms，v2总计{b["total_s_median"]*1000:.3f} ms，原始/v2={a["total_s_median"]/b["total_s_median"]:.3f}×；v2实际线程为{b["actual_threads"]}。小矩阵收益包含串行选择，不能表述为新多线程加速。' if n=='cache-small' else f'- {n}，12线程R={r}：原始总计{a["total_s_median"]*1000:.3f} ms，v2总计{b["total_s_median"]*1000:.3f} ms，原始/v2={a["total_s_median"]/b["total_s_median"]:.3f}×。')
    a=get('screen','giant-row','v2-auto');b=get('screen','giant-row','v1-pack')
    lines+=[f'- 巨行12线程R=9：v2总计{a["total_s_median"]*1000:.3f} ms，v1-pack为{b["total_s_median"]*1000:.3f} ms。拆行解决了线程参与问题，但同步和分段内核成本仍在，不能称v2对全部后端都更快。',
      '- 保留原始novec、v1标量/SELL及同FP模式通用CSR强对照，源码/链接前csr.o .text相同。相同源码不保证最终链接布局或运行状态一致；同二进制统一预热诊断单独列出，普通CSR与固定8项路径相同FP模式，不把包装差异直接称算法收益。',
      '- 自动阈值不是通用最优，部分稍大缓存内输入仍适合强制串行。对均匀矩阵不能期待负载均衡本身获益；空行多不等于nnz失衡。保留集、真实输入和各项退化均列在完整结果中。未独立测DRAM流量/持续带宽上限，没有据此宣称带宽饱和。',
      '', '#### Git 交付','',
      f'核心提交 `{git["core_commit"]}`，名称 **“优化方案v2”**，已推送 `origin/optimization/v2` 并核对远端；父提交为原始master。'+('本轮主目标达标，核心工作区保留在optimization/v2；原始master保持不变。' if decision['passes_primary'] else '本轮未过主目标门槛，核心工作区切回master；远端v2分支保留供审核。'),
      '资料继续在main，提交名称 **“2026.10.26v2实验记录”**。包含本段日志、实验脚本、原始输出、汇总、图表、校验与复现说明；本文件所属提交号由git log查看，避免在提交内部自引用提交号。',
      '', '完整入口：[v2实验](experiments/2026-10-26-v2/README.md)；[结果分析](experiments/2026-10-26-v2/结果分析.md)；[配对区间](experiments/2026-10-26-v2/paired-analysis.json)；[审计](experiments/2026-10-26-v2/audit.json)；[Git证据](experiments/2026-10-26-v2/git-provenance.json)。']
    p=run.MATERIALS/'项目日志.md';s=p.read_text();assert '## 2026.10.26' not in s,'Dated log already exists; do not duplicate.'
    p.write_text(s.rstrip()+'\n\n'+'\n'.join(lines)+'\n')
    p=run.MATERIALS/'research/2026-10-25-spmv-v2/README.md';s=p.read_text()
    s+='\n## 2026-10-26 实现与验证\n\n本目录保留2026-10-25的设计记录。实际v2已按后续要求从原始master独立分支实现，与v1隔离；实现、正式结果及适用边界见 [v2实验](../../experiments/2026-10-26-v2/README.md)。上述历史设计中的状态/分支设想以此次实现记录为准。\n'
    p.write_text(s);print('Updated dated project log and research cross-reference.')
if __name__=='__main__':main()
