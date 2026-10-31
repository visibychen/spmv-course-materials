#!/usr/bin/env python3
"""Format existing frozen results and append their final project-log record."""
import json,subprocess,sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import common as c
import write_report as w
H=c.H

def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root,text=True).strip()

def main():
    w.main()
    d=json.loads((H/'decision.json').read_text())
    assert not d['accepted_as_robust_upgrade']
    a=json.loads((H/'audit.json').read_text())
    s=json.loads((H/'summary.json').read_text())
    mainrows={x['variant']:x for x in s if x['phase']=='main'}
    orig,base=d['main']
    assert orig['control']=='original' and base['control']=='v2'
    fail=[x for x in d['guards'] if x['median_time_ratio']>1.10]
    lead=f"""
## 本轮结论与成本解释

主输入为1200万行、9600万非零元，T24/R9。P+E+D总成本中位数：原始{mainrows['original']['total_s_median']*1000:.3f}ms、v2 {mainrows['v2']['total_s_median']*1000:.3f}ms、v3 {mainrows['v3']['total_s_median']*1000:.3f}ms。配对v3/原始中位数{orig['median_time_ratio']:.4f}（下降{-orig['time_change_percent']:.2f}%）；配对v3/v2为{base['median_time_ratio']:.4f}，95%区间[{base['ci95'][0]:.4f}, {base['ci95'][1]:.4f}]。后者包含1，不能宣称已证明变慢或等效；它没有满足预先要求的至少5%配对改善，因此不替代v2。配对比中位数与两个总时间中位数之比不同，不能互换。

局部转置路线有可测机制收益：相对同FP、相同验证与分区的v3-csr，配对总成本下降{-d['mechanism']['time_change_percent']:.2f}%，区间完全低于1；这说明本输入上跨行SIMD优于本版通用后端，却没有证明优于v2的固定8项展开。v2已有固定8项展开；原始对照仍保留原有OpenMP和编译器自动向量化条件。

A/A时间比{d['aa']['median_time_ratio']:.4f}，区间[{d['aa']['ci95'][0]:.4f}, {d['aa']['ci95'][1]:.4f}]，通过5%精度带。本轮没有复现前轮A/A精度不足的问题；v3仍然未通过整体门槛。按用户最后版本约定，恢复并重建v2，结束优化迭代；v3不删除、不合并进master。

"""
    report=(H/'结果分析.md').read_text()
    report=report.replace('## 方法与成本边界',lead+'## 方法与成本边界',1)
    costs=w.table(['观测','版本','P/ms','R次E/ms','D/ms','P+E+D/ms','进程wall/ms'],[
        (phase,x['variant'],*[f"{x[k+'_median']*1000:.3f}" for k in ['prepare_s','execute_s','cleanup_s','total_s','wall_s']])
        for phase in ['main','cli'] for x in s if x['phase']==phase])
    wallnote=f"""
## 计算总成本与进程耗时分别报告

{costs}

P/E/D及wall各取自己的样本中位数，表中中位数不能直接相加。标准CSR共同加载在P计时前，生产CLI的MTX解析/转换也在各自计算计时前；它们仍包含在进程wall中。生产CLI的wall中位数为原始9.22s、v2 9.54s、v3 9.92s，v3在这组端到端观测中没有呈现收益。只有5组、没有对该wall另设显著性判断，不能将此表述为普遍变慢，但更不能把计算阶段约10%的配对收益写成程序整体约10%的加速。

"""
    report=report.replace('## 关键输入与全部回退',wallnote+'## 关键输入与全部回退',1)
    guardtext=w.table(['失败护栏','T','控制','配对变化','P:控制→本版/ms','E:控制→本版/ms'],[
        (x['matrix'],x['threads'],x['control'],f"{x['time_change_percent']:+.2f}%",
         f"{x['control_prepare_s_median']*1000:.3f}→{x['candidate_prepare_s_median']*1000:.3f}",
         f"{x['control_execute_s_median']*1000:.3f}→{x['candidate_execute_s_median']*1000:.3f}") for x in fail])
    interpretation=f"""
## 退化来源能解释到哪一步

{guardtext}

empty99的8行均长8资格不成立，转置不能帮助该形状。与原始相比，本版完整验证带来可见P；执行阶段也没有足够下降将其抵消。T12/T24配对总成本分别增加24.33%/22.35%，均超过10%护栏。这是以总成本检验优化的必要性，不能只引用E或“不申请动态数组”来忽略准备工作。

heavy-clustered/T24对v2配对增加11.67%，本版P反而更低，退化主要出现在本批E观测。v3的通用后端、局部块检查、FP设置与v2的策略/代码生成存在多项差异；没有硬件计数或逐因素配对证据，不能锁定为gather、缓存、FMA或某一条指令造成。T12的配对点值则下降3.31%且区间跨1，表明线程条件影响结论，不能用一个T代表全部。

巨行没有拆分是本路线的明确边界。giant-row/T12对原始配对约+0.72%而对v2的合并中位数高约57.26%；v2已有merge拆行机制，v3没有继承。该例虽未触发对原始10%的指定护栏，仍作为负面证据保留。局部tile资格严格要求8行各8项，ragged7/8、长度2/4/7/16等形状不能据全8主输入外推；全部回退表和保留集展示这些限制。

旧92份T12相对原始慢超过10%的计数由v2的37降至v3的13，新12份为5→5，覆盖面有改善，但输入没有实际工作负载权重，不能用胜负计数覆盖主条件与关键护栏的失败。新路线证明了部分结构上的价值，本轮证据支持保留为研究结果，尚不足以替代v2作为最终交付版本。

"""
    report=report.replace('## 新12份保留集',interpretation+'## 新12份保留集',1)
    (H/'结果分析.md').write_text(report)
    if '--report-only' in sys.argv:
        print('REPORT-ONLY FORMATTING COMPLETE')
        return
    now=datetime.now(ZoneInfo('Asia/Shanghai'))
    stamp=now.strftime('%Y.%m.%d')
    prov=dict(
        recorded_local=now.isoformat(),
        design=dict(repo='visibychen/spmv-course-materials',branch='main',commit='b67c63744afcabe09412e6364e5b4c18837829f7',message='优化方案v3',pushed_before_implementation=True),
        implementation=dict(repo='visibychen/csrspmv',branch='optimization/v3',commit=git(c.C,'rev-parse','optimization/v3'),parent=git(c.C,'rev-parse','optimization/v3^'),message='优化方案v3代码实现',pushed_before_formal=True),
        result=dict(repo='visibychen/spmv-course-materials',branch='main',message=stamp+'v3实验记录',commit='Use the enclosing Git commit; no self-referential SHA.'),
        final_core_branch=git(c.C,'branch','--show-current'),final_core_commit=git(c.C,'rev-parse','HEAD'),final_core_clean=not git(c.C,'status','--porcelain'),
        restored_native_binary_sha256=c.sha(c.C/'csrspmv'),restore_log='raw/restore-v2-build.txt',
        unchanged_master=git(c.C,'rev-parse','master'),retained_candidate_branch=True,
        materials_design_head_before_results=git(c.M,'rev-parse','HEAD'),forced_push=False,history_rewritten=False)
    assert prov['implementation']['parent']==c.COMMITS['original']
    assert prov['unchanged_master']==c.COMMITS['original']
    assert prov['final_core_commit']==c.COMMITS['v2']
    assert prov['final_core_clean']
    c.save('git-provenance.json',prov)
    marker='### 最后一个优化版本v3实现与实验记录'
    logpath=c.M/'项目日志.md'
    log=logpath.read_text()
    assert marker not in log, 'Do not duplicate or silently replace a prior record.'
    entry=f"""

{marker}

- 设计main提交b67c6374（优化方案v3）先推送；核心从原始master 9352c86直接创建optimization/v3，实现e83160bf（优化方案v3代码实现）随后推送。没有从v1/v2派生，原始master未改。本版为用户指定的最后一轮优化。
- 路线为CSR局部8行×8项寄存器转置、跨行AVX2 gather，有序逐项累加；不创建SELL副本、不缓存Ax、无动态辅助数组。通用路径和portable运行时回退保留，默认work分区、小任务串行；局部资格付在E、完整验证付在P。独立8形状288观察不支持pipeline默认，按预设规则选tile8；提交后未按正式结果改代码或默认。
- 每组4156项的native1/12/24、portable12、ASan+UBSan1/12/24及无OpenMP共8配置通过；15项CLI参数检查、104输入464组完整输出（含104组生产CLI）、10组类型/对称兼容、串行生产构建及独立tile真实调用12次核验通过。真实矩阵以f32源的float64参考及逐行误差界判断，不称全部误差0。
- 固定提交正式{a['formal_processes']}进程、{a['blocks']}个双/三版本相邻块；三版本主场景20块、同FP机制10对、同一v2后端A/A12对。统一可执行文件/标准CSR夹具提高计算比较一致性；夹具不是v3生产功能，不将加载/MTX差异计作优化。另15进程用原生产CLI验证性能护栏。全部成本按P+R次E+D，wall另列。

| 主T24/R9版本 | P/ms | E/ms | P+E+D/ms |
| --- | ---: | ---: | ---: |
""" + ''.join(f"| {v} | {mainrows[v]['prepare_s_median']*1000:.3f} | {mainrows[v]['execute_s_median']*1000:.3f} | {mainrows[v]['total_s_median']*1000:.3f} |\n" for v in ['original','v2','v3']) + f"""
主条件配对v3/原始{orig['median_time_ratio']:.4f}，区间[{orig['ci95'][0]:.4f}, {orig['ci95'][1]:.4f}]（总成本下降11.63%）；v3/v2为{base['median_time_ratio']:.4f}，区间[{base['ci95'][0]:.4f}, {base['ci95'][1]:.4f}]，未满足至少5%改善，且区间跨1，不能宣称已证明变慢/等效。同FP机制对照下降13.11%，说明跨行转置对本版通用后端有收益，但不证明优于v2固定8项展开。

A/A区间[{d['aa']['ci95'][0]:.4f}, {d['aa']['ci95'][1]:.4f}]通过5%精度门槛。关键护栏失败：empty99对原始T12/T24配对+24.33%/+22.35%，验证P未被执行收益抵消；heavy-clustered/T24对v2+11.67%，E较高而P较低，未锁定硬件原因。巨行对v2、短行与非8形状的负例完整保留。旧92/新12份T12对原始慢>10%计数v2→v3为37→13、5→5；计数没有工作负载权重，不覆盖共同门槛。

生产CLI计算总成本v3/原始配对约-9.96%，但进程wall中位数原始9.22s、v2 9.54s、v3 9.92s，不能宣称程序端到端提速。P/E/D与wall以及本批和历史结果分别记录，不混比共同CSR夹具与MTX加载。

共同门槛未通过，失败项为main_vs_v2及critical_regression_guard。按约定已切回**optimization/v2（9b652e8）**、清理候选构建并重建v2，两仓库交付时核验干净并推送；optimization/v3及e83160bf保留。不再开始新优化版本，接下来的目标是最佳版本上游PR与课程实验报告，尚未标记完成。

完整入口：[实验说明](experiments/2026-10-31-v3/README.md)、[结果分析](experiments/2026-10-31-v3/结果分析.md)、[配对分析](experiments/2026-10-31-v3/paired-analysis.json)、[决策](experiments/2026-10-31-v3/decision.json)、[完整性审计](experiments/2026-10-31-v3/audit.json)、[Git来源](experiments/2026-10-31-v3/git-provenance.json)。本次材料提交名**{stamp}v3实验记录**，结果SHA查看所属Git提交。冻结脚本/程序/源/输入双SHA、原始资源及命令全通过审计；未调整正式后验收、样本数或R，未合并master、重写历史或强推。
"""
    logpath.write_text(log+entry)
    print('FORMATTED ANALYSIS, PROJECT LOG AND GIT PROVENANCE',stamp)
if __name__=='__main__':main()
