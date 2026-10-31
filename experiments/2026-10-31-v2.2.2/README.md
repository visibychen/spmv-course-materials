# v2.2.2实验归档

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
