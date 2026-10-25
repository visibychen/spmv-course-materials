# 2026-10-25：优化方案 v1 实现与对照实验

本目录记录原始 CSR、局部标量 CSR、AOCL 风格 CSR 收集和无排序 SELL8/SELL16 的实现验证与测量。**保留全部收益、退化和回退结果，不以线程扩展或原有 CSR 作为新增贡献。**

- [结果分析与采用决定](结果分析.md)
- [完整汇总表](汇总表.md)、[补充 1/24 线程](补充线程对照.md)、[逐进程数据](measurements.csv)、[汇总 CSV](summary.csv)
- [正确性](correctness.json)、[额外类型兼容性](correctness-compatibility.json)、[Sanitizer](correctness-sanitize.json)、[审计](audit.json)
- [输入清单](输入清单.md)、[矩阵校验和](matrices.json)、[构建](build.json)、[源码 SHA-256](source-provenance.json)、[环境](environment.json)、[协议](protocol.json)
- `raw/`：每次运行的完整参数、OpenMP 环境、标准输出、错误输出及 GNU time 资源记录；另含编译诊断、汇编、线程位置和测试日志。

## 实现与原方法的关系

核心仓库以原始 `9352c865044f4c8b344d6fe5a277200a89f7a08b` 为基点，在独立 `optimization/v1` 分支实现。原始默认分支实际名为 `master`，资料仓库默认分支为 `main`。最终代码提交和推送状态见 [Git 记录](git-provenance.json)。

首轮范围为调研方案阶段 A 与 B1/B2：f32/f32/f32 的局部标量、手动取 x / 组装 AVX2 和 σ=1 的 SELL8/SELL16。SELL 的每条 lane 处理独立的一行；保留原 CSR，输出仍为 `y += Ax`。原 OpenMP 区域本来就在重复循环之外，本次没有把创建线程移出循环作为优化。

方法来自 [SELL-C-σ 论文](https://doi.org/10.1137/130930352)、固定版本的 [GHOST](https://github.com/RRZE-HPC/GHOST/tree/22a004dbbfb604d7b04b0bde813c8100d403cfcc) 和 [AMD AOCL-Sparse](https://github.com/amd/aocl-sparse/tree/d633b58d3cfa266a2a0a8e2fb0f22cc97ee7355c)。按其算法独立实现，没有直接粘贴第三方源码或引入外部运行依赖。核心 `docs/v1.md` 保留具体文件链接、许可证及接口说明；[前期调研](../../research/2026-10-25-spmv-optimization/README.md) 保留完整来源。

此轮没有实现局部排序、工作量均衡或 merge-based 巨行拆分。巨行、长尾和大量空行的实测用于检验首轮边界，不能声称这些瓶颈已经解决。

## 测量方法

- GCC 11.4，`-O3 -march=native -g -Wall -iquote src -fopenmp`；无全局 fast-math。新增两个显式 SIMD 源文件单独使用 `-ffp-contract=off`。局部标量以 GCC 函数属性禁止循环 / SLP 自动向量化。另构建完整原始 novec 对照，并测量新二进制的 original 路径以检查包装影响。
- 全部原始构建通过 `git archive` 从同一原始提交导出；新构建复制实际 v1 源码，记录每个源文件和二进制 SHA-256。没有在原始分支中改代码跑“原始版本”。
- 主测量 5 个独立进程 / 条件；单独先导为 1 个进程，不混入正式汇总。每一轮包含所有条件，以固定种子随机打乱顺序；逐次原始样本全部保留。
- 线程为 1/12/24，22 类极端输入均测 12 线程，其中 10 类另测 1/24 线程；超大矩阵的所有主候选均测 1/12/24。线程固定 `OMP_DYNAMIC=FALSE`、`OMP_PLACES=cores`、`OMP_PROC_BIND=spread`、`OMP_WAIT_POLICY=PASSIVE`；清除继承的 OMP/GOMP 设置，保存实际放置探针。
- 不插入预热。主要 R=9；零元、小缓存和极宽小行数输入在主 12 线程测量用 R=100，降低计时量化影响；小缓存的其他线程也为 R=100。超大矩阵另实测 24 线程 R=1/100。每个比较均匹配 R；表中明确区分。
- `execute` 沿用原程序乘法计时，包含并行区域进入 / 退出和逐次屏障，排除文件读入、CSR 创建、准备、输出和释放。`prepare` 独立计时；另记录 `prepare+execute` 以及整个进程 wall、最大 RSS 和 major faults。不同后端的准备过程会自然改变缓存状态，没有额外人为刷新缓存或让一方独享预热。
- 准备成本 P 包括输入检查与转换，回退时的检查也计入。模型回本次数由实测 P、T0、T1 计算；不能把单次内核提升等同于端到端提升，也不能把模型值当作每次运行的保证。
- 本机为 WSL2；没有锁定 CPU 频率、宿主机调度或建立持续 DRAM 带宽上限。报告中位数与极差，不把本次合成输入结果推广到所有真实矩阵；不把 perf 采样占比当作缓存未命中率。

## 输入与数值验证

`generate_cases.c`（MIT）生成固定种子 `0x20261025` 的合成矩阵，不使用第三方数据集。12 种均匀行长为 1/2/4/7/8/9/15/16/17/32/64/256；另有带状、热 x 区域、集中与分散长尾、百万元素巨行、99% 空行、零元、小缓存、宽矩形和高矩形。超大 1200 万阶 / 9600 万非零元矩阵复用上次 baseline 的文件和校验和。

这里的随机列采用分层抽样：按行长划分列区间，每个区间取一项，再保持列序；不是在所有稀疏结构上均匀抽样。区间结构本身可能影响 SELL 的 x 局部性。行长扫描大多保持约 200 万 nnz 并改变行数，行长 1 因行数上限仅 100 万 nnz；不是只改变内循环长度的严格单变量实验。hot / banded 输入虽分配了完整 x，实际访问的 x 子集很小。

性能输入用全 1 x 和精确二进制分数 a，方便全量输出检查。它不替代一般浮点测试：核心测试还用非零初始 y、变化的 x、乱序和重复列、负值、显式零、NaN/Inf、消去、subnormal、带符号零、矩形及零维度，并以 long double 和按行长 / Σ|a·x| 制定的前向误差界验证。CSR-pack 的横向归约与原始求和次序不同；SELL 显式乘加与原始可能的 FMA 尾部也可能不同，因此不承诺一般浮点数逐位相等。

填充通道以 -1 索引掩蔽 gather，尾部写回也掩蔽；无效项不会读取 x[0]，避免 0×NaN/Inf 污染。SELL 在填充超过 2 倍、超过额外内存预算（默认 1024 MiB 与运行时 Linux 可用内存一半取小）、分配失败或类型 / ISA 不支持时回到原始内核。这些阈值是本实现的保守策略，不是论文的通用最优参数。

## 复现

在两个仓库相邻的 Linux/WSL 目录运行，先切到核心 v1 分支。上次的大矩阵须位于 baseline 的 `data/`；若不存在，先按 baseline README 生成。以下操作会运行完整实验，耗时较长：

```sh
cd spmv-course-materials/experiments/2026-10-25-v1
python3 run_experiments.py build
python3 run_experiments.py generate
python3 run_experiments.py correctness
python3 run_experiments.py pilot
python3 run_experiments.py formal
python3 run_experiments.py large
python3 run_experiments.py amortization
python3 run_experiments.py summarize
python3 analyze_results.py
python3 verify_kernels.py
python3 audit_and_compatibility.py
```

测量脚本重启会跳过已有键，不会覆盖采样。要做新的独立复现实验，应复制脚本和生成器到新目录，保留本次结果。`build/`、`data/` 及 perf 二进制数据均被忽略；生成器、输入 SHA-256、构建参数和文本原始记录进入 Git。
