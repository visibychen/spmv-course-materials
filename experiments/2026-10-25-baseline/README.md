# 原始 csrspmv 大矩阵基线（2026-10-25）

## 实验目标与原始版本

测试未经修改的上游版本 `9352c865044f4c8b344d6fe5a277200a89f7a08b`。该版本已经实现 CSR 和 OpenMP，本实验将它们视为基线已有能力。核心仓库保持原状，通过 `git archive HEAD` 将源码导出到本目录被忽略的 `build/`，使用原始 Makefile 构建各配置。

本目录的脚本、数据生成器和说明属于实验资料；没有修改或提交核心仓库，也不执行任何 Git 提交或推送。

后续改进以同线程数、同数值类型、同构建选项的原始代码为对照，同时保留原始代码最佳线程配置作为工程基线。原始代码的单线程到多线程加速用于说明已有并行能力。

## 环境与编译配置

- WSL2 / Ubuntu 22.04，GCC 11.4.0，GNU Make 4.3。
- WSL 报告 AMD Ryzen 9 7845HX，12 核 / 24 逻辑处理器，L3 为 32 MiB。此处保留虚拟机报告值，不据此断言宿主机完整缓存拓扑。
- 开始时 WSL 总内存约 15.26 GiB；完整环境、线程实际落点和运行前后内存状态见 `environment.json`、`final-memory.json`。
- 所有数值显式选择 f32；列索引为 int32，行指针为 int64。

| 配置名称 | 编译选项 | 用途 |
| --- | --- | --- |
| `strict` | `-O3 -march=native -g -Wall -iquote src -fopenmp` | 正式基线，保留编译器默认浮点规则，没有开启 `-ffast-math` |
| `novec` | 在 strict 上增加 `-fno-tree-loop-vectorize -fno-tree-slp-vectorize` | 关闭 GCC 循环和 SLP 自动向量化的对照，测试 1、12 线程 |
| `fastmath_diagnostic` | 在 strict 上增加 `-ffast-math` | 仅用于编译诊断和小矩阵正确性检查，未纳入性能基线；此选项改变浮点优化规则 |

每个构建还附加 `-fopt-info-vec-all=...` 保存诊断。`strict` 是配置名称，不代表禁止 FMA：编译器默认的 `-ffp-contract` 等状态保存在 `optimizer-*.txt`。实际命令、二进制及源码 SHA-256 保存在 `provenance.json`。

显式传入 Makefile 的命令行 `CFLAGS` 会覆盖普通变量追加规则，因此命令中写全 `-fopenmp` 和包含目录等必要参数，避免误编译为无 OpenMP 的程序。

## 大矩阵与可复现数据

矩阵由 `generate_matrix.c` 本地生成，没有引用外部数据集。生成器使用 MIT 许可，见 `LICENSE-generator.txt`；上游源码仍遵循原 GPL-3.0-or-later 许可。

- 尺寸：12,000,000 × 12,000,000。
- 非零元：96,000,000，每行恰好 8 个，密度约 `6.666667e-7`，即 `0.0000666667%`。
- 固定种子：`0x20261025`，算法版本 v1。
- 将列范围分为 8 个区间，每行在各区间用确定性 mix64 选择一列；列索引严格递增且无重复，行长一致，避免将负载不均衡混入本次基本对照。
- 数值为 `q/4`，`q=1..7`，来自哈希高位，均可被二进制浮点精确表示。
- 输入向量为原程序默认全 1。小矩阵另用非均匀向量检查列索引和乘法逻辑。
- `.mtx` 文件为 2,030,223,365 字节（约 2.03 GB）；精确 SHA-256 和生成命令见 `matrix.json`。
- CSR 为 864,000,008 字节，x、y 各为 48,000,000 字节；核心工作集约 960 MB。矩阵远超报告的 L3，x 本身也超过报告的 32 MiB。

这是均匀行长、全局分散访问 x 的一种合成负载。它不代表所有真实矩阵，不能据此推广到带状矩阵、不均匀行长、所有稀疏度或 HPCG 完整应用。

## 正确性与计时口径

1. 独立 NumPy 稠密参考检查矩形矩阵、无序坐标、重复坐标、空行、负数和非均匀 x。三个编译配置分别在 1、12 线程和重复 1、7 次下检查，精确匹配。
2. 独立读取生成器的小矩阵，用非均匀 x 与 NumPy 结果比较，并检查生成器写出的全 1 输入参考值。
3. 对大矩阵，分别在 1 线程重复 1 次、12 线程重复 3 次下核对全部 12,000,000 个输出元素，采用实际语义 `y ← y + Ax`，参考为 `repeat × Ax`。数值特意采用精确二进制分数，不把本次精确相等推广为一般浮点正确性准则。
4. 正式性能来自原程序 `csr_matrix_int32_spmv:` 的计时，排除文件读取、CSR 转换和结果写出。原来的并行区域进入、退出、每轮隐式屏障及第一轮计算均保留。
5. 没有修改源码加入预热；单次进程内重复计算以摊薄第一轮影响。先导运行用于选择各配置共用的重复次数，先导数据单独保存，不混入正式统计。
6. 测试 1、2、4、8、12、24 线程，每种正式配置取三个独立进程样本。每轮按固定种子打乱顺序，统计每次 SpMV 的中位数、最小值和最大值。三个样本提供初步稳定性信息，不构成严格置信区间。
7. 固定 `OMP_DYNAMIC=FALSE`、`OMP_PLACES=cores`、`OMP_PROC_BIND=spread`、`OMP_WAIT_POLICY=PASSIVE`。12 线程使用 12 个核位置，24 线程包含 SMT；实际映射见 `environment.json`。
8. `/usr/bin/time` 单独记录整个进程的 wall time、最大 RSS 和缺页计数，不能把进程总耗时、总计数解释成内核指标。计时期间不并行运行其他本实验的计算任务，也不修改宿主机的电源与调度设置。

### 带宽数字的含义

`summary.csv` 中的 `logical_access_model_GBps` 仅为明确声明的逻辑访问量模型：

```text
每次逻辑字节数 = 4*nnz(values) + 4*nnz(column_indices)
               + 4*nnz(x 引用) + 8*(rows+1)(row_ptr)
               + 8*rows(y 读写)
逻辑访问吞吐 = 每次逻辑字节数 / 每次 SpMV 耗时 / 1e9
```

该模型省略缓存行放大、x 的缓存复用、写分配等因素，**不是实测 DRAM 带宽，也不是已经完成的 Roofline 分析**。判断是否达到内存带宽上限还需要独立带宽上限测量和更细的内存访问证据。

## 自动向量化证据

`vectorization-strict.txt` 对 `src/csr.c:1295` 的 f32 内层循环报告 64 和 32 字节向量化。`assembly-strict.txt` 的 `csr_matrix_int32_spmv_f32_f32_f32()` 对应部分含 `vgatherdps`、`vmulps`，随后以 `vaddss` 链求和。

对本矩阵每行 8 个非零元，汇编的长度分支进入 8 元素的 256 位处理路径；不能因为二进制中也有 512 位路径，就说本次主要使用 512 位宽度。

因此，当前 CPU/编译器/选项下的 f32 基线已经包含自动向量化，但仍保留顺序累加链。该结论不能直接推广到 f64：无 fast-math 配置对 f64 内层循环报告未向量化，fast-math 诊断构建则可以生成其向量路径。是否更快以实测 strict/novec 对照为准。

## 数据文件与复现

| 文件 | 内容 |
| --- | --- |
| `provenance.json`、`build-*.log`、`optimizer-*.txt` | 原始版本、源码/二进制哈希、实际构建命令、优化器状态 |
| `environment.json`、`matrix.json`、`protocol.json` | 环境、矩阵来源和校验和、完整实验协议 |
| `correctness-small.json`、`correctness-large.json` | 独立参考与大矩阵逐元素校验结果 |
| `raw/` | 各次运行的命令、标准输出、标准错误和资源消耗记录；先导与正式样本分开命名 |
| `measurements.csv` | 正式运行的逐次原始数据，GFLOP/s 由 FLOPs 和耗时重算，避免原程序显示位数造成精度损失 |
| `summary.csv`、`summary.json` | 三次样本的汇总统计 |
| `baseline.png`、`baseline.svg` | 时间和线程加速比图，误差线为三个样本的最小值、最大值 |
| `结果分析.md` | 本次实测结果和结论 |
| `profile_baseline.py`、`profile.json`、`perf-*.txt` | 与正式计时分开的可选 perf 采样及其范围说明 |
| `audit_results.py`、`audit.json` | 核心仓库未改动、源码/二进制/输入哈希、原始输出与汇总一致性的最终校验 |
| `data/`、`build/` | 本地大矩阵、校验向量、源码快照和编译产物，被上级 `.gitignore` 排除 |

在 WSL 中执行，路径可自行调整：

```bash
cd ~/计算机组成原理课设/spmv-course-materials/experiments/2026-10-25-baseline
python3 run_baseline.py --stage prepare
python3 run_baseline.py --stage generate
python3 run_baseline.py --stage large-check
python3 run_baseline.py --stage benchmark --samples 3
python3 run_baseline.py --stage summarize
# 可选采样，与正式测试分开执行：
python3 profile_baseline.py
# 采样成功后可再次校验当前全部实验产物：
python3 audit_results.py
```

依赖：GCC、Make、binutils、Python 3、NumPy、Matplotlib、GNU time；perf 为可选依赖。完整一次新实验可运行 `python3 run_baseline.py --stage all`。已有矩阵会检查哈希后复用；已有 `measurements.csv` 时拒绝覆盖，应保留旧结果并复制本实验脚本至新的实验目录后再跑。新目录执行时需要维持 `experiments/<实验目录>` 的层级。

Git 审核时应包含脚本、说明、日志、元数据和汇总，保留原始运行文本；超大矩阵可按固定生成器和哈希重建，不需要提交约 2 GB 的文本输入。`.gitignore` 同时排除 perf 二进制数据，保留可读采样结果。
