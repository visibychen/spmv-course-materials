#!/usr/bin/env python3
"""Formats frozen analysis only; no sample selection, inference or retuning."""
import json,statistics as st
from pathlib import Path
import common as c
H=c.H
def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,x))+' |' for x in rows])+'\n'
def paired_table(xs):
 return table(['控制','请求T(本版/控制)','块数','控制总计/ms','本版总计/ms','配对时间比','95%区间','本版P/ms','本版E/ms'],[(x['control'],f"{x['threads']}/{x['control_threads']}",x['blocks'],f"{x['control_total_s_median']*1000:.3f}",f"{x['candidate_total_s_median']*1000:.3f}",f"{x['median_time_ratio']:.4f}",f"[{x['ci95'][0]:.4f}, {x['ci95'][1]:.4f}]",f"{x['candidate_prepare_s_median']*1000:.3f}",f"{x['candidate_execute_s_median']*1000:.3f}") for x in xs])
def main():
 d=json.loads((H/'decision.json').read_text());a=json.loads((H/'audit.json').read_text());p=json.loads((H/'protocol.json').read_text());pairs=json.loads((H/'paired-analysis.json').read_text());comp=json.loads((H/'comparisons.json').read_text());summ=json.loads((H/'summary.json').read_text())
 branch='optimization/v3' if d['accepted_as_robust_upgrade'] else 'optimization/v2'
 gate_names={'correctness':'正确性/类型/安全','main_vs_best_original':'主条件对最佳已测原始至少5%收益','main_vs_v2':'主条件对v2至少5%配对收益','matched_fp_mechanism':'同FP通用CSR对照确认至少5%机制收益','actual_tile_coverage':'实际转置路径覆盖','aa_precision':'A/A达到5%精度','production_cli_guard':'生产CLI收益护栏','critical_regression_guard':'关键输入退化护栏','negative_counts_not_increased':'旧/新集退化计数不增加'}
 lines=['# v3最终优化版本实验结果','', '设计b67c6374先推送，核心实现e83160bf从原始master 9352c86直接创建并推送，随后固定提交实验；没有继承v1/v2分支历史。v2 9b652e8作为最佳对照。用户指定这是最后一个优化版本。','', f'**共同验收{"通过" if d["accepted_as_robust_upgrade"] else "未通过"}，最终工作分支为{branch}；v3分支和全部结果保留。**','',table(['预设共同门槛','判断'],[(gate_names[k],'通过' if v else '未通过/证据不足') for k,v in d['gates'].items()]), '## 方法与成本边界','', 'v3在局部8行各8项时按四列一半即时转置寄存器，让每lane保持一个输出行的有序累加。没有整份SELL/其他格式副本、矩阵重排或Ax缓存；每次真实执行y+=Ax，空行实际加零。默认tile8，非适格块和尾部走通用CSR。数据结构验证完整计入P，只有一个大任务检查团队；无动态辅助数组。连续work分区和小任务串行选择不是本版新增贡献。','', '主对照使用同一个benchmark程序及标准CSR快照加载器，分别链接固定原始CSR、固定v2对象和v3对象。每个进程只执行一个后端；P+R次E+D为总成本，wall另列。夹具由原始MatrixMarket转换器产生，源MTX与夹具双SHA保留。**夹具生成/加载是共同实验基础，不是v3算法收益；其wall不能直接同历史MTX进程混比。** 生产CLI另测，原始CSR/OpenMP/自动向量化均未计作新增贡献。','', '原始CSR对象被所有后端共享；原始和v2的全局编译设置沿用正式O3/native。v3新单元ffp-contract=off，generic仍允许编译器向量化。v3-csr与默认使用相同FP/验证/分区，是独立机制对照。','', '## 主标准CSR大矩阵 T24/R9','', '三版本20个相邻块，同一块的候选同时对应原始和v2；时间比=本版/控制，低于1更快。单项中位数不直接相加替代逐进程总成本。','',paired_table(d['main']), f'原始最佳已测请求线程为{d["best_tested_original"]["threads"]}。其最佳选择来自预先固定的线程组，样本数见summary.json；不是全局最优线程证明。若选中12线程，使用预先冻结cross12对照，不外推T24区间。','', paired_table([d['main_vs_selected_original']]) if d['main_vs_selected_original'] and d['main_vs_selected_original']['phase']=='cross12' else '', '## 同FP机制对照与A/A','',paired_table([d['mechanism'],d['aa']]), 'A/A为同一个v2后端、相同二进制/参数/环境的12对，仅外部记录标签不同。精度带预设为[1/1.05,1.05]。通过只支持本批尺度判断，不证明普遍等效；不通过则按预设判为证据不足，不事后追加到显著。','', '独立gcov探针使用真实变化x和有序参考核对，tile8实际调用12次；计时程序不加覆盖计数。源码中的本地块判断与正式输出simd/backend字段保留，不能把结构命中本身当作收益。','', '## 生产CLI T24/R9（不与夹具混合）','',paired_table(d['cli']), '此组5个相邻三版本块，保留各程序已有P/E/D输出精度。wall包含MTX解析、CSR转换和日志；以夹具I/O代替MTX的变化不计为优化。小样本区间仅报告，主要统计证据来自预先指定的共同CSR实验。','', '## 关键输入与全部回退','',table(['输入','T','控制','配对本版/控制','时间变化','95%区间'],[(x['matrix'],x['threads'],x['control'],f"{x['median_time_ratio']:.4f}",f"{x['time_change_percent']:+.2f}%",f"[{x['ci95'][0]:.4f}, {x['ci95'][1]:.4f}]") for x in pairs if x['phase']=='critical']),table(['组','输入数','v2对原始慢>10%','v3对原始慢>10%'],[(k,x['n'],x['v2_slower_over10'],x['v3_slower_over10']) for k,x in d['descriptive_counts'].items()]),'计数是描述统计，无工作负载权重，也不表示逐例显著性。以下列出T12相对原始或v2变慢的全部输入，按各组中位数筛查；关键条件正式判断以配对数据为准。','',table(['输入','原始/ms','v2/ms','v3/ms','对原始','对v2','P/ms','E/ms','实际T'],[(x['matrix'],*[f"{x[v+'_ms']:.3f}" for v in ['original','v2','v3']],f"{x['v3_vs_original_percent']:+.2f}%",f"{x['v3_vs_v2_percent']:+.2f}%",f"{x['prepare_ms']:.3f}",f"{x['execute_ms']:.3f}",x['actual_threads']) for x in comp if x['threads']==12 and (x['v3_vs_original_percent']>0 or x['v3_vs_v2_percent']>0)]), '## 新12份保留集','',table(['输入','T','R','原始/ms','v2/ms','v3/ms','对v2'],[(x['matrix'],x['threads'],x['repeat'],*[f"{x[v+'_ms']:.3f}" for v in ['original','v2','v3']],f"{x['v3_vs_v2_percent']:+.2f}%") for x in comp if x['phase']=='heldout']), '## 独立校准、消融及敏感性','']
 cal=json.loads((H/'calibration-decision.json').read_text());lines += [f'8份独立形状、288次提交前校准。非8行组auto/tile8几何均值{cal["geomean_auto_over_tile_non8"]:.4f}，最差组{cal["worst_group_auto_over_tile"]:.4f}；未满足预设<=0.97及无组退化>10%，故默认保留tile8。没有用保留集调默认。校准后仅补NO_OPENMP兼容宏；变更及校准源重构见calibration-compatibility.json。','',table(['输入','变体','T','P/ms','E/ms','总计/ms','实际T'],[(x['matrix'],x['variant'],x['threads'],*[f"{x[k+'_median']*1000:.3f}" for k in ['prepare_s','execute_s','total_s']],x['actual_threads']) for x in summ if x['phase']=='ablations']), '显式pipeline4在高度不均匀的4行块中可能受最长行拖累；default未将该候选用于非tile块。rows/work消融只改边界，其他准备相同。消融小样本与正式块不同时段，不将微小差值直接归因某一指令。','',table(['组','输入','变体','T','R','P/ms','E/ms','总计/ms','实际T'],[(x['phase'],x['matrix'],x['variant'],x['threads'],x['repeat'],*[f"{x[k+'_median']*1000:.3f}" for k in ['prepare_s','execute_s','total_s']],x['actual_threads']) for x in summ if x['phase'] in ['sensitivity','waiting','original-best']]),'ACTIVE是双方一致的附加敏感性组，没有据此改变PASSIVE主条件。原始T1对小任务的结果用于区分线程选择与同线程内核收益，不把串行选择全部称为新SIMD加速。','', '## 正确性、审计与局限','',f'- 104输入，464组完整输出检查（含104组生产CLI）、10组类型/对称兼容；8组native/portable/ASan+UBSan/无OpenMP配置，每组4156项。另有15项CLI参数检查、无OpenMP生产构建及独立tile覆盖探针。', '- 精确二进制分数输入用精确参考；真实输入先转f32再用独立float64参考及逐行误差界，CLI输出50位避免舍零，不称真实误差均0。源值和x逐次变化、非零y、NaN/Inf/-0、64位偏移、非法CSR及团队变化均覆盖。', '- 固定提交归档构建的benchmark .text/.rodata/.data与提交前完整核验构建一致；源文件/输入/夹具/程序和冻结脚本哈希均审计。原始csr.c不改，旧v2对象独立链接，不合入v2提交。',f'- 正式{a["formal_processes"]}个进程（含15个生产CLI），{a["blocks"]}个双/三版本块。最大RSS {a["max_rss_kib"]/1024:.2f}MiB、最大major faults {a["max_major_faults"]}。全程RSS包含共同输入加载和CLI COO峰值，不代表新内核辅助内存。', '- 无动态格式副本；固定计划、寄存器和可能的编译器栈spill均不能等同于零总空间开销。夹具本体与构建不入Git，生成方法和双SHA留档。', '- 同可执行文件减少链接布局和计时框架差异，不能消除地址随机化、宿主负载、频率及CPU放置差异。未锁频，未测DRAM控制器/STREAM/缓存硬件事件；不将时间差或逻辑访存量当作已证明的硬件瓶颈。', '- 逐条件区间未作多重比较校正；三进程组和胜负计数仅描述。结果限记录环境、矩阵和R，不能宣称任何输入都更快。', '- 本版是最后一轮；未通过则保留v3并回到v2，不事后修改门槛、样本数或R。上游PR和课程最终报告另待后续任务。','', '![主条件与机制区间](figures/main-pairs.png)','', '[完整逐次CSV](measurements.csv) · [全部条件](comparisons.csv) · [配对数据](paired-analysis.json) · [决策](decision.json) · [审计](audit.json)']
 (H/'结果分析.md').write_text('\n'.join(lines)+'\n')
 (H/'README.md').write_text('''# v3独立最终路线实验

设计b67c6374先推送；代码e83160bf直接基于master9352c86，推送后才冻结正式实验。对照最佳v2 9b652e8，不从v2派生。

[结果分析](结果分析.md) · [设计](../../research/2026-10-31-spmv-v3/优化方案v3.md) · [预设准入](../../research/2026-10-31-spmv-v3/验证计划.md)

## 两种输入/观测方式

主实验使用同一benchmark及加载器，以标准CSR快照比较原始/v2/v3。快照由固定原始MatrixMarket转换器产生，所有后端共享同一CSR、x/y建立方式和9位计时。P包括各实现完整准备，E包含真实R次/团队/屏障，D计清理。原始自动向量化和既有并行保持。没有单方预热或缓存Ax。

快照是共同实验基础，不属于v3生产功能；生成/加载相对MTX的加速不计入v3收益，也不能把该wall直接与历史MTX进程混比。生产CLI额外5个三版本块保留原计时，并对104份输入逐一核对输出。原始CLI缺少团队日志时按请求值推定，统一benchmark直接记录实际团队。

## 主要文件

- common.py/build_fixed.py/bench.c：固定对象、标准CSR生成/加载和统一执行器；source-provenance.json/fixed-build-proof.json记录固定提交及提交前后计算代码段一致性。
- inputs.py/matrices.json：旧92及新12来源、生成器、MTX和CSR双SHA；本体在忽略的data中。
- run_checks.py/verification-builds.json：8组、每组4156项；correctness.json464组及compatibility.json10组，precommit-cli.json15项、no-openmp-cli.json和tile-execution-proof.json。
- calibrate.py/calibration*.json：8独立校准形状、288观察、固定选择规则、默认tile8及后续仅串行兼容宏的来源重构。
- protocol.json/frozen-harness.json：首个正式进程前完整顺序、条件/输入/源码/程序/分析哈希。新增cross12预先声明，以防原始最佳团队是12。
- measurements.csv/raw：所有正式命令、环境、输出、资源。summary/comparisons/paired-analysis/decision/audit记录全部正负结果。
- run_experiments.py/analyze_results.py/audit_results.py：冻结运行、统计与完整性检查；write_report.py/finalize_record.py/plot_results.py只格式化，不参与验收；finalize_record的report-only模式保留解释段。
- 设计和代码提交分开；结果提交包含项目日志。Git来源见git-provenance.json，不内部自引用结果提交SHA。

## 复现

请复制脚本到experiments下新目录，创建build/data/raw/figures，保留本归档。旧MTX按matrices.json的provenance/生成器或URL恢复，旧绝对路径需要对应本地目录。单元检查先在干净检出切至固定v3代码；性能构建从固定提交导出，不依赖工作区分支。

~~~
python3 common.py
python3 run_checks.py
python3 precommit.py
python3 inputs.py create
python3 inputs.py verify
python3 check_compatibility.py
python3 build_fixed.py
python3 freeze_protocol.py
python3 run_experiments.py
python3 analyze_results.py
# 按本次决策设置最终工作分支并记录自己的Git来源
python3 audit_results.py
python3 plot_results.py
python3 finalize_record.py --report-only
~~~

校准如需重跑必须使用新目录和自己的来源；不得把新观察冒充原288次。冻结器拒绝覆盖已有测量CSV，运行器按六字段键续跑；不覆盖本次构建和来源记录。调度种子2026103151，bootstrap基种子2026103153加条件的确定性偏移。双/三版本块内索引整体重采样，候选/控制时间比小于1更快。
''')
 print('REPORT WRITTEN')
if __name__=='__main__':main()
