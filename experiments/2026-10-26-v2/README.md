# v2 实现与原始项目对照（2026-10-26）

v2 从原始核心 **master** 创建 `optimization/v2`，不以 v1 为父提交。原始 CSR 源文件不变；v1 从固定提交单独归档构建，原始、v1、v2 是独立对照。代码提交名称为“优化方案v2”，本目录与项目日志的资料提交名称为“2026.10.26v2实验记录”；确切提交号及最终检出分支见交付时的 `git-provenance.json`。

## 阅读入口

- [结果与适用边界](结果分析.md)：主目标、所有极端输入、保留集、强对照与负结果。
- [逐次进程数据](measurements.csv)、[汇总](summary.csv)、[主条件配对区间](paired-analysis.json)、[判定](decision.json)。
- [实验协议](protocol.json)、[构建](build.json)、[源码哈希](source-provenance.json)、[环境](environment.json)。
- [输入来源与SHA](matrices.json)、[正确性](correctness.json)、[验证构建](verification-builds.json)、[v1回归](v1-regression.json)。
- [同二进制诊断](diagnostic.json)、[原始CSR对象代码证明](csr-object-proof.json)、`raw/` 中所有逐次命令/输出/资源及汇编。
- `figures/` 为总成本加速比图；低于1表示中位数退化，先导数据不混入正式结果。

## 实现范围与公平比较

v2 显式启用 `--kernel=v2`，默认仍为 original。直接使用 CSR：小工作量串行、完整确认的8项短行展开、连续 nnz+rows 分区、作者 CPU merge-path 的 f32/int64/累加适配。参数和来源见核心 `docs/v2.md`，研究依据见 [v2设计资料](../../research/2026-10-25-spmv-v2/README.md)。

所有主条件明确 f32/f32/f32、y+=Ax、同一 GCC/ISA 与 OpenMP 设置，无全局 fast-math。v2 翻译单元采用 ffp-contract=off，行函数局部不向量化；原始自动向量化、原始全构建novec、v1标量及SELL和同FP模式的v2通用CSR均有对照。不能把原有CSR、线程扩展或自动SIMD记作新增成果。

主时间为每个进程 prepare+execute+cleanup；全进程 wall 另列，包含读MTX、COO转CSR等。完整检查始终付费；行验证和统计融合，策略和小额分配融合，阶段名称按实际边界报告。v2只借用CSR，不生成SELL副本；merge的O(T) scratch另外记录。默认规则不在线免费试算后端，不缓存Ax。

正式实验同一时间只运行一个条件。中等输入每条件5个独立进程；超大矩阵1/12/24线程、R=1/9/100各10个相邻随机AB/BA进程对。配对区间以进程对为单位，20,000次固定种子重采样；同一进程内R次循环不能当独立样本。没有锁定宿主频率/活动，也没有本轮实际DRAM流量或STREAM上限测量。

## 输入与许可

共34个输入：复用原23个（含1200万阶/9600万nnz大矩阵）、2个校准输入、7个新种子保留输入、2个真实矩阵。复用输入均重新核对SHA，旧实验记录不改写。新输入的列在整行范围无放回均匀抽样，并覆盖双巨行、空行成簇、集中长尾和边界尺寸。

真实输入为NIST [BCSSTK18](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/bcsstruc2/bcsstk18.html) 和 [SHERMAN5](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/sherman/sherman5.html)。原矩阵分别由 Prof Mac Will 与 Andy Sherman 提供。BCSSTK18保存80519项，对称展开为149090项；SHERMAN5为20793项非对称矩阵。NIST矩阵页未单列许可，本轮仅保留本地输入，不在Git重新分发；下载地址、原头部、gzip/MTX校验和和f32转换说明见JSON。SuiteSparse下载遇TLS失败后换用这两份NIST数据，没有将下载失败误记成已测输入。

基线生成器遵循其MIT许可，v1生成器及本轮脚本按原项目GPL-3.0-or-later。merge的BSD-3-Clause版权/许可保留在核心源码和 `docs/merge-spmv-LICENSE.txt`；未把整个旧benchmark/MKL依赖移入v2。

## 复现

依赖：WSL/Linux、GCC、GNU Make/time、binutils、Python3、NumPy、Matplotlib。两个仓库保持兄弟目录，核心需要有原始、v1、v2对应提交。先在核心检出 `optimization/v2`（确切版本查交付JSON），保持工作区干净；`build` 阶段读取当前核心源码并记录完整SHA，其余两版从固定Git提交归档。

```sh
cd ~/计算机组成原理课设/csrspmv
git switch optimization/v2
cd ../spmv-course-materials/experiments/2026-10-26-v2
python3 restore_reused_inputs.py
python3 run_experiments.py inputs
python3 run_experiments.py build
python3 run_experiments.py verify
python3 run_experiments.py pilot
python3 run_experiments.py screen
python3 run_experiments.py heldout
python3 run_experiments.py large
python3 diagnostic.py build
python3 diagnostic.py run
python3 write_report.py
```

初次 `inputs` 需能访问NIST；网络受限时可按JSON地址先下载 `data/nist-bcsstk18.mtx.gz`、`data/nist-sherman5.mtx.gz`。输入校验失败应排查，不能覆盖原校验和。本批真实数据实际通过Windows curl下载，脚本复现也支持Python urllib。

测量按键续跑，不覆盖已有样本。**要做新的独立批次，应先复制本目录脚本到新的 experiments 子目录并去掉复制的结果/测量文件**，保持层级；仅在原目录重新运行会跳过已完成键，不能当作新实测。原始/v1生成器仍位于原实验目录，数据存那里并校验；此前历史记录保留。大矩阵MTX、gzip、预期向量、构建物、临时输出均被 `experiments/.gitignore` 排除。

本轮用5%总成本中位改善及区间支持收益作为主目标门槛，这是一项工程约定。若未过门槛，核心工作区切回 master，远端 v2 分支保留；无论最终表现如何都不合并到原始 master。

工具原始输出保留原字节，含GCC和SVG生成的行尾空格。本目录 `.gitattributes` 仅对 raw/ 和SVG导出关闭空白格式告警，源码、脚本、文档仍检查；属性语义见 [Git官方文档](https://git-scm.com/docs/gitattributes#_checking_whitespace_errors)。
