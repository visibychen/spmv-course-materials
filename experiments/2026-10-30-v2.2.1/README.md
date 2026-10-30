# v2.2.1四版本实验

设计提交 `f6e247a`，核心实现 `dfb4ae2`，核心分支optimization/v2.2.1直接基于v2.2的 `10f6b89`。原始固定 `9352c86`，v2固定 `9b652e8`。先推送设计，再推送代码，随后从四个Git提交分别构建并正式测量。设计与本轮结果分别保存，不能把设计假设当成已验证收益。

[设计与准入](../../research/2026-10-30-spmv-v2.2.1/README.md) · [结果分析](结果分析.md) · [分支决策](decision.json) · [完整性审计](audit.json)

## 校准后、代码提交前的调整

先做21组单元/消毒测试配置，再用6份独立形状产生90个CLI校准观察。校准未支持将中型列检查默认并行化，因此最终auto使用普通串行列循环，只有显式`--v221-validation=parallel`才启用并行候选；work索引边界、精确容量重试和直接执行器保留。这一调整在任何正式输入生成与计时前完成，不是根据保留成绩调参。

原始90个命令/输出/程序哈希保存在calibration.json，决策见calibration-decision.json。其时CLI默认auto仍为并行候选；最终实现已改为串行。calibrate.py复现相同候选时显式写parallel，避免最终默认改变校准含义，不能将新一次运行冒充原始那90次。verification-source.json是单元配置时的源码快照；随后只改变了未链接到这些单元测试的CLI默认/解析，最终CLI另有precommit-cli.json检查，最终固定源码见source-provenance.json。

若需重建当时CLI源码，可对实现提交的archive应用raw/calibration-cli-default.patch；calibration-source-reconstruction.json验证重建的program_options.c哈希与调整前快照完全一致。其他生产源不变，但构建路径/编译器仍会影响整个程序哈希。

重建旧CLI后应重放calibration.json中的原始命令；calibrate.py给最终CLI显式传parallel是另一条策略复现路线，不要将新开关传给尚未支持它的旧CLI。

## 输入与环境

旧68份矩阵全部视为回归集，包含10份此前使用的真实矩阵；新增12份不同种子、尺寸和结构的合成保留输入。矩阵文件和构建产物不入Git。matrices.json保留来源、尺寸、对称展开、f32转换、SHA及期望向量哈希。新保留集涵盖不同周期/相位空行、聚集和随机空行、maxlen64/65、列检查阈值、resident范围及零输出大小两侧。

统一GCC生产参数`-O3 -march=native -g -Wall -iquote src -fopenmp`；原始自动向量化开启，优化文件保留各自fp-contract约束，不使用全局fast-math。完整机器/软件信息见environment.json。固定OMP_DYNAMIC=FALSE、OMP_PLACES=cores、OMP_PROC_BIND=spread、OMP_WAIT_POLICY=PASSIVE。性能进程顺序运行，不与编译、测试或绘图并行。

优化版本的实际线程数来自程序输出。上游原始没有team日志，其CSV actual_threads在上述约束下按请求值记入，是推定值。v2.2.1的executor=v2表示直接复用v2，并不表示请求策略被忽略；少数巨行仍使用准备好的两线程。日志partition记录旧v2备用路径策略；显式balance=rows时，索引实际使用等行数边界，即使备用partition仍显示work。

v2.2委托路线的validation_s=0表示包装层没有转录分项，不表示跳过验证；v2.2.1的statistics_known=0、计数=-1表示委托未统计。empty=off只关闭非零矩阵的行号表，零矩阵仍走加零路径。extra_bytes是已保留动态数组的payload，不是整个准备过程的实测内存峰值；预算按可能同时存活的索引/边界或merge数组核算，RSS另含更早的COO/CSR峰值。

CSV保留了旧运行器的profile相关空列以便格式连续，本版没有读取外部profile或执行模型评分。policy-coverage.json汇总新保留集的实际选路、重试和线程数，用于区分覆盖修复与性能收益。

## 计时和统计

主指标为逐进程P（准备）+E（R次执行）+D（清理），再取中位数；P包括全部检查、分配与补扫，wall另列。原始版本无计划阶段，P=D=0。没有只给候选预热、缩小R、缓存Ax或将准备移出计时。

所有正式命令用-v读取各版本既有的程序内计时。没有统一改写上游的观测代码；日志位于执行前，不能严格排除观测代码、布局等对微小输入的影响。完整wall包含日志及读取/转换开销。

正式计划3369个进程：critical1560、screen1000、heldout480、large80、large-sensitivity89、ablations160；820个相邻随机AB/BA配对。关键条件每控制10对，候选30样本；主T24/R9分别对原始10对、v2 20对、v2.2 10对，候选40样本。整组配对块也随机排列，避免把某个控制集中在较早或较晚时段。其他条件每版本5进程；原始T2/4/8补充各3进程。

配对区间仅用对应控制的进程对，候选合并组中位数不冒充配对点值。固定种子20261030、20000次配对速度比中位数bootstrap；多个条件的区间未做家族误差校正，不当作整体显著性检验。五进程组和±5%计数仅作描述统计，不代表真实工作负载权重。

## 复现与文件

重新采样请将脚本复制到资料仓库experiments下的新目录，保留原归档。运行器按六字段键续跑，原目录已有CSV会跳过已完成样本；不要用重建/重生成覆盖本次来源记录。新运行需创建自己的冻结哈希和来源信息。

```bash
mkdir -p data build raw
python3 run_experiments.py build
# 先复现旧2026-10-27-v2.2的输入，保留旧data目录
python3 run_experiments.py inputs
python3 run_experiments.py verify
python3 freeze_protocol.py
for phase in critical screen heldout large large-sensitivity ablations; do
    python3 run_experiments.py "$phase"
done
python3 diagnostic.py
python3 finish_support.py proof
python3 write_report.py
python3 plot_results.py
# checkout/log/audit是本次交付步骤；新复现应使用自己的日志及Git来源
```

- protocol.json、frozen-harness.json：首次正式进程前冻结的条件及脚本/输入/构建哈希。
- build.json、source-provenance.json、git-provenance.json：固定源码、程序及分支证据。
- verification-builds.json、correctness.json：21组测试配置、489组完整向量/类型兼容核验。
- measurements.csv、raw/：所有正式命令、输出、错误输出、资源及校准/验证日志。
- summary.csv/json、comparisons.csv、comparison-cases.json：全部条件和四方比较。
- paired-analysis.json、decision.json、结果分析.md：区间、共同门槛和全部负结果。
- diagnostic.json、csr-object-proof.json、assembly-index.json：同二进制轮转及源码/机器码证据。进程内重复不当作独立重复；original保留生产csr.o浮点方式。
- figures/：PNG和SVG图表；audit.json：条数、配对、哈希和原始输出一致性。

未锁定宿主机频率或后台负载，也未测DRAM控制器/STREAM或硬件缓存失效。不能将时间差、逻辑工作集或链接前代码段一致性当成已经证明的硬件因果。验收不佳切回v2，远端v2.2.1保留，不合并master。
