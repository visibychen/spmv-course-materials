#!/usr/bin/env python3
"""Render frozen analysis; this script does not select samples or change gates."""
import json,statistics as st,collections
from pathlib import Path
import run_experiments as r
H=r.HERE

def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])+'\n'
def main():
 d=json.loads((H/'decision.json').read_text());p=json.loads((H/'protocol.json').read_text());a=json.loads((H/'audit.json').read_text());pairs=json.loads((H/'paired-analysis.json').read_text());comp=json.loads((H/'comparisons.json').read_text());summ=json.loads((H/'summary.json').read_text())
 gates={'correctness':'正确性与安全','main_vs_original':'主条件对最佳已测原始收益','main_vs_v2':'主条件相对v2不退化','main_vs_v22':'主条件相对父版不退化','preserve_parent_guards':'父版7个关键输入收益保留','target_coverage_and_two_improvements':'新目标覆盖且至少两份改善','negative_counts_not_increased':'旧/新集退化计数不增加','aa_precision':'A/A达到5%判断精度'}
 branch='optimization/v2.2.2' if d['accepted_as_robust_upgrade'] else 'optimization/v2'
 lines=['# v2.2.2四版本实验结果','',f'设计77bbb9c2先推送，代码92f45f7随后推送；实现直接基于父版10f6b89。固定提交、输入和统计脚本后完成{a["formal_processes"]}个正式进程、{a["paired_blocks"]}组相邻进程对，另有24个同二进制诊断进程。正式成绩后没有改生产代码、默认、阈值、R或样本数。','',f'**共同门槛{"通过" if d["accepted_as_robust_upgrade"] else "未通过"}；最终工作分支为{branch}。研究分支及全部结果保留。**','',table(['预先冻结门槛','判断'],[(gates[k],'通过' if v else '未通过/证据不足') for k,v in d['gates'].items()]),'## 主大矩阵：对应配对样本','', '候选/控制时间比小于1表示本版更快。每个控制只使用自己的20对；不同对照的候选中位数不混用。分项中位数相加不必等于总时间中位数。','',table(['控制','配对数','控制总计/ms','本版总计/ms','配对时间比中位数','95%区间','本版P/ms','本版E/ms'],[(x['control'],x['pairs'],f"{x['control_total_s_median']*1000:.3f}",f"{x['candidate_total_s_median']*1000:.3f}",f"{x['median_candidate_over_control']:.4f}",f"[{x['ci95'][0]:.4f}, {x['ci95'][1]:.4f}]",f"{x['candidate_prepare_s_median']*1000:.3f}",f"{x['candidate_execute_s_median']*1000:.3f}") for x in d['main_matched']]),f'原始R9最佳已测线程为{d["best_tested_original"]["threads"]}。主条件依旧委托旧v2数值路径，观察差异不能直接称新算术内核的收益。wall包含MTX读取与CSR转换，见summary.csv；SpMV阶段收益不能直接当作全程序收益。','', '## A/A测量分辨率','']
 aa=d['aa'];lines += [f'同一v2程序、相同参数及环境的12对A/A，时间比中位数{aa["median_candidate_over_control"]:.4f}，95%区间[{aa["ci95"][0]:.4f}, {aa["ci95"][1]:.4f}]。AB/BA各6对。预设精度区间为[1/1.05,1.05]，判断为{"通过" if d["gates"]["aa_precision"] else "证据不足"}。A/A只诊断本批测量，不证明任何不同实现等效，也不覆盖跨机器变化。','', '主条件对v2的配对点估计有表观收益，但uniform输入仍使用原v2数值路径；A/A点估计同样明显偏离1且精度门槛未过。因此不能将主条件差值归因于新区间算法，也不能以该亮点覆盖其他失败门槛。','', '## 新目标与路径覆盖','',table(['输入T12/R9','本版/父版配对中位时间比','时间变化','95%区间','本版P/ms','父版P/ms','本版E/ms','父版E/ms'],[(x['matrix'],f"{x['median_candidate_over_control']:.4f}",f"{x['time_change_percent']:+.2f}%",f"[{x['ci95'][0]:.4f}, {x['ci95'][1]:.4f}]",f"{x['candidate_prepare_s_median']*1000:.3f}",f"{x['control_prepare_s_median']*1000:.3f}",f"{x['candidate_execute_s_median']*1000:.3f}",f"{x['control_execute_s_median']*1000:.3f}") for x in pairs if x['phase']=='targets' and x['control']=='v22']), '实际启用新路径的适格新输入记录：'+json.dumps(d['coverage'],ensure_ascii=False)+'。超过8个空区间、最长行65及比例/驻留不匹配的输入继续旧路径，详见原始route日志。','', '新路径保留固定区间payload，不保留动态行号表；准备时父版可能已申请/填表再释放，成本仍计入P。retained_run_bytes只含有效区间payload，不代表整个plan或准备峰值。','', '单空区间block1在本轮获得配对总成本收益证据；block4/8的准备中位数分别从约0.341/0.359ms增至0.409/0.439ms，而执行中位数仅从约1.958/1.935ms降至1.941/1.912ms，未证明总收益。固定容量和长空区间资格不能替代回本条件。分项中位数仅用于定位阶段，不按直接相加重算总成本。','', '## 父版关键条件及全部负结果','',table(['输入','T','配对本版/父版','时间变化','95%区间'],[(x['matrix'],x['threads'],f"{x['median_candidate_over_control']:.4f}",f"{x['time_change_percent']:+.2f}%",f"[{x['ci95'][0]:.4f}, {x['ci95'][1]:.4f}]") for x in d['guard_pairs']])]
 lines += [table(['组','输入数','父版相对原始慢>5%','本版相对原始慢>5%'],[(k,x['n'],x['v22_slower_over5'],x['v222_slower_over5']) for k,x in d['descriptive_counts'].items()]), '上述计数为描述性统计，没有实际工作负载权重；相对原始的父版和本版样本组不同时，不能用计数代替配对效应或显著性。以下保留全部T12负例（相对原始或父版任一慢>5%），此表使用各组中位数仅供筛查，关键条件正式结论以配对表为准。','',table(['输入','原始/ms','v2/ms','父版/ms','本版/ms','对原始','对父版','本版P/ms','本版E/ms','实际T'],[(x['matrix'],*[f"{x[v+'_ms']:.3f}" for v in ['original','v2','v22','v222']],f"{x['v222_vs_original_percent']:+.2f}%",f"{x['v222_vs_v22_percent']:+.2f}%",f"{x['prepare_ms']:.3f}",f"{x['execute_ms']:.3f}",x['actual_threads']) for x in comp if x['threads']==12 and (x['v222_vs_original_percent']>5 or x['v222_vs_v22_percent']>5)]),'empty99/T12仍走父版索引执行，P中位数却从0.939增至1.298ms，E从2.480增至2.582ms；可观察增量主要落在准备阶段。本版给非目标输入增加了区间跟踪工作，具体编译组织和系统因素未被单独分离，不能把全部增量直接称为某条指令的成本。未来可检验超过容量后停止额外跟踪等收敛假设，本轮不据此修改实现或重跑成绩。','', '## 消融、线程和等待策略','']
 ab=[x for x in summ if x['phase']=='ablations'];lines += [table(['输入','变体','P/ms','E/ms','总计/ms','实际T'],[(x['matrix'],x['variant'],*[f"{x[k+'_median']*1000:.3f}" for k in ['prepare_s','execute_s','total_s']],x['actual_threads']) for x in ab]),'消融与主组处于不同时间，不能以它们的微小差值直接作因果贡献。policy=v22保留父版完整准备，runs=off只关闭新区间路径，不关闭旧索引/零矩阵。','']
 diagnostics=json.loads((H/'diagnostic.json').read_text());dg=collections.defaultdict(list)
 for process in diagnostics:
  names={x['backend'] for x in process['records']}
  for name in sorted(names):
   samples=[x for x in process['records'] if x['type']=='sample' and x['backend']==name]
   prep=next(x for x in process['records'] if x['type']=='prepare' and x['backend']==name)
   assert len(samples)==12
   dg[(process['matrix'],name)].append((st.median(x['execute_s'] for x in samples),prep['prepare_s'],samples[0]['actual_threads']))
 lines+=['## 同二进制的独立进程诊断','', '每个条件3个独立进程，各后端在每进程12轮中取E中位数，下表再列这3个数的中位数和范围。进程内轮转不当作36个独立样本；各计划同时存活，P只作参考，不能代替正式总成本。','',table(['输入','后端','独立进程数','P中位/ms','E中位/ms','3进程E范围/ms','实际T'],[(m,n,len(v),f"{st.median(x[1] for x in v)*1000:.3f}",f"{st.median(x[0] for x in v)*1000:.3f}",f"[{min(x[0] for x in v)*1000:.3f}, {max(x[0] for x in v)*1000:.3f}]",','.join(map(str,sorted({x[2] for x in v})))) for (m,n),v in sorted(dg.items())])]
 best=[x for x in summ if x['phase']=='original-best'];lines += [table(['输入','原始T1总计/ms','原始T12总计/ms','本版T12上限总计/ms','本版实际T'],[(x['matrix'],f"{x['total_s_median']*1000:.3f}",f"{next(z for z in comp if z['matrix']==x['matrix'] and z['threads']==12)['original_ms']:.3f}",f"{next(z for z in comp if z['matrix']==x['matrix'] and z['threads']==12)['v222_ms']:.3f}",next(z for z in comp if z['matrix']==x['matrix'] and z['threads']==12)['actual_threads']) for x in best]), '原始T1每条件3进程，仅是额外已测配置；不会把候选实际T1对原始T12的收益全部称为新内核加速。','',table(['输入','变体','ACTIVE总计/ms','实际T'],[(x['matrix'],x['variant'],f"{x['total_s_median']*1000:.3f}",x['actual_threads']) for x in summ if x['phase']=='waiting']), 'ACTIVE仅为单独敏感性组，未用于修改默认或替换PASSIVE主测量。novec强对照见summary.csv的controls组；全局禁向量化影响多个翻译单元，不能将全部变化归因于一处循环。','', '## 正确性、诊断和局限','', '- 新区间执行同时使用已有rows/work选择，本轮runs消融不能单独分离区间组织与分区边界改变的贡献。新阈值直接按设计固定，未做保留集拟合。',f'- native T1/12/24、portable T12及ASan+UBSan T1/12/24，三套测试共21配置全部通过；每配置v2/v2.2/v2.2.2各5368/1007/1197项。另有12项提交前CLI检查、{a["full_vector_and_compatibility_checks"]}组完整输出/类型兼容核验，覆盖92份正式输入；另有4组original-novec强编译对照完整输出检查。', '- 合成二进制分数使用精确参考；10份真实矩阵先转f32再用独立float64参考及逐行误差界，不称全部误差0。非零初始y、逐次x/values变化、特殊浮点、分配失败及团队改变有单元覆盖。', '- 同二进制每条件3个独立进程，每进程6个后端各预热一次、12轮轮转；同进程轮转有关联，不计为独立重复。多个计划同时存活，诊断不能替代独立进程总成本。',f'- 正式最大RSS {a["max_rss_kib"]/1024:.2f}MiB、最大major faults {a["max_major_faults"]}。RSS含COO/CSR转换早期峰值，不能替代新增内存测量。', '- csr.c、spmv_v2.c、spmv_v22.c及旧测试源码保留。plan增大可能影响准备机器码和布局，相同源码不保证所有对象代码相同。未以差值直接归因于包装、缓存或某条指令。', '- 原始自动向量化保留；优化翻译单元沿原FP约束，不启用全局fast-math。原生产E文本精度为1us、资源wall为0.01s，极小输入百分比需结合绝对时间看。', '- 未锁宿主机频率/后台负载，未测硬件DRAM/STREAM或缓存失效；结论限本环境。配对区间未做多重比较校正，胜负计数无实际工作负载权重。', '- 补充诊断初版遗漏父版选项参数，首个诊断计时前编译失败。原冻结文件和失败日志保留；bench_compare_fixed.c/diagnostic_fixed.py仅修复接口调用，哈希及补丁见diagnostic-correction.json。正式生产源码、执行命令、样本与统计脚本未改。', '- 所有正式记录、固定哈希、负例与失败门槛均保留；未挑样本、事后追加到显著、改变验收或改写历史。','', '![主条件配对区间](figures/main-pairs.png)','', '![新目标配对区间](figures/target-pairs.png)','', '[完整CSV](comparisons.csv) · [全部逐次记录](measurements.csv) · [冻结协议](protocol.json) · [审计](audit.json) · [同二进制诊断](diagnostic.json)']
 (H/'结果分析.md').write_text('\n'.join(lines)+'\n')
 (H/'README.md').write_text('''# v2.2.2实验归档

先推送设计77bbb9c2，再从v2.2的10f6b89创建并推送代码92f45f7，随后固定提交实验。原始9352c86、最佳v2 9b652e8、父版v2.2 10f6b89四方比较。

[结果分析](结果分析.md) · [设计](../../research/2026-10-31-spmv-v2.2.2/优化方案v2.2.2.md) · [准入](../../research/2026-10-31-spmv-v2.2.2/验证计划.md)

本轮92输入含旧80份开发回归、新12份保留形状。调度种子2026103107；bootstrap基种子2026103111加条件的确定性偏移，见冻结的analyze_results.py。正式3952个进程、972个配对块（含12个A/A块），24个独立诊断进程另列。性能严格顺序，原始自动向量化开启，统一生产O3/native/精度/绑定；优化单元保留局部FP约束。主指标P+R次E+D，完整进程wall单列。每个控制只使用自己的候选配对样本，随机化块顺序且每个条件AB/BA平衡。

新路径仅针对少量长空行区间；不保证所有高空行输入选路或加速。默认仍original，不缓存Ax、不改变R、空行实际加零、完整列检查和团队完成同步保留。输入、输出解释与资源限制详见结果分析。

## 文件

- protocol.json/frozen-harness.json：首个正式进程前冻结的完整顺序、样本数、输入/脚本/程序哈希。
- run_experiments.py：固定提交构建、条件生成、顺序运行与续跑；analyze_results.py：冻结的配对统计和准入。
- matrices.json/verify_and_inputs.py：输入来源、生成器、哈希；MTX和构建产物忽略。
- verification-builds.json/precommit-cli.json/correctness.json/supplementary-control-checks.json：单元、安全、CLI和完整输出核验。
- measurements.csv/raw：全部正式命令、环境、标准输出、错误输出与资源日志。
- summary.csv/json/comparisons.csv/paired-analysis.json/decision.json：全部分项、描述比较、对应配对与决策。
- bench_compare_fixed.c/diagnostic_fixed.py/diagnostic.json：多个独立进程的公平预热轮转诊断；原冻结版本和编译失败日志保留，修正见diagnostic-correction.json。
- source-provenance.json/executor-source-proof.json/git-provenance.json/audit.json：源码、Git谱系及完整性核对。

## 新目录复现

不要覆盖本归档。将脚本复制到资料仓库experiments下的新目录，先创建build/data/raw/figures。按matrices.json及其provenance指向的历史生成器/来源复现旧输入目录，或保留已有data。单元检查脚本读取核心仓库当前检出源码，需先在干净工作区切至optimization/v2.2.2（92f45f7），或使用其固定提交的隔离检出；检查后恢复自己的工作分支。性能build从Git提交独立导出，不依赖当前检出。再执行：

```sh
python3 run_checks.py
python3 run_experiments.py build
python3 run_experiments.py inputs
python3 run_experiments.py verify
python3 freeze_protocol.py
python3 run_experiments.py formal
python3 diagnostic_fixed.py
python3 analyze_results.py
python3 verify_controls.py
# 依据新一次decision切换工作分支，记录自己的Git来源
python3 audit_results.py
python3 plot_results.py
python3 write_report.py
```

原运行器按六字段键续跑，已有CSV会跳过完成样本；冻结器拒绝覆盖已有正式CSV。新运行使用自己的冻结来源，不能将重跑冒充本次记录。若版本分支未来移动，须先按本归档protocol.json的commits固定构建来源，不能用移动后的分支替代。原始actual_threads缺少日志时按请求值推定；优化版本读取实际团队日志。旧v2缺少route日志时CSV沿用original占位值，不表示实际回退original，应结合selected与executor。委托路径的新区间统计0表示未收集，不推断真实空行数为0。新报告未转录validation_s时CSV为0，完整验证仍计入P；profile相关空列仅沿用历史格式，本版不读取外部profile。固定plan中的区间数组不受动态数组预算限制，retained_run_bytes只报告有效区间payload。extra_bytes是动态payload，retained_run_bytes是有效区间payload，均非整个准备阶段峰值。所有统计门槛以实现前设计和冻结分析脚本为准。
''')
 print('REPORT written')
if __name__=='__main__':main()
