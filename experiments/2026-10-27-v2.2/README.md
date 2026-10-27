# v2.2：固定提交的三方实验

本目录对应资料设计提交 `645b292`，核心代码提交 `10f6b89`（父提交为 v2 `9b652e8`）。先推送设计，再推送实现，最后运行正式实验。原始版本固定为 `9352c86`。各版本从 Git archive 单独构建；不会用当前工作树替换已发布源码。

## 实验范围与复现

以下展示本轮执行顺序。需要重新采样时，将脚本复制到资料仓库experiments下的独立新目录，并新建data/build/raw，保留原归档目录及其CSV不动。计时脚本按六字段键续跑，已有CSV会跳过已完成样本；直接在原目录重跑不会得到一轮新样本，build/inputs还会覆盖来源记录。审计脚本用于核验本次归档；新一轮需建立自己的冻结哈希、构建及测试来源记录，不能沿用本次哈希冒充新记录。

在 Ubuntu 22.04 / WSL、GCC 11.4、Ryzen 9 7845HX 上顺序执行。原始 CSR、多线程及自动向量化保持开启。统一 `-O3 -march=native -g -Wall -iquote src -fopenmp`，各优化版本原有的局部浮点编译约束保留。未添加全局 fast-math。OpenMP 设置见 environment.json；请求线程数是上限，实际计算线程数另列。

优化版本的实际团队来自程序输出。上游原始版本没有团队日志，CSV中其actual_threads在OMP_DYNAMIC=FALSE下按请求值记录，属于环境约束下的推定值，不能称为逐次测得的原始团队规模。

```bash
mkdir -p data build raw
python3 run_experiments.py build
# 下载下述 NIST 文件到 data/nist-NAME.mtx.gz 后：
python3 run_experiments.py inputs
python3 run_experiments.py verify
for phase in critical screen heldout large large-sensitivity ablations; do
    python3 run_experiments.py "$phase"
done
python3 diagnostic.py
python3 write_report.py
python3 plot_results.py
python3 audit_results.py
```

依赖 Python 3、NumPy、Matplotlib、GCC、OpenMP、binutils、GNU time。先复现旧 `2026-10-26-v2.1` 的输入生成步骤，保留其 data/；本轮复用其中52份矩阵并核验 SHA256。大型主矩阵为1200万行、9600万非零项。原有矩阵不冒充新保留集。新生成12个不同种子/尺寸/结构的输入，另增加4个真实输入，共68份。新数据完全不用于调参。

真实新增矩阵来自 NIST Matrix Market：

| 名称 | 下载来源 | 元数据 |
| --- | --- | --- |
| bcsstk14 | [MTX.gz](https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/bcsstruc2/bcsstk14.mtx.gz) | [NIST](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/bcsstruc2/bcsstk14.html) |
| bcsstk15 | [MTX.gz](https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/bcsstruc2/bcsstk15.mtx.gz) | [NIST](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/bcsstruc2/bcsstk15.html) |
| sherman1 | [MTX.gz](https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/sherman/sherman1.mtx.gz) | [NIST](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/sherman/sherman1.html) |
| west0655 | [MTX.gz](https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/chemwest/west0655.mtx.gz) | [NIST](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/chemwest/west0655.html) |

下载/解压数据与构建文件忽略提交；来源、SHA、对称展开、类型转换及复现参数记录于 matrices.json。NIST 页面没有单独授权声明，因此本仓库不再分发其矩阵文件。

## 指标与样本

主要指标是**逐进程 P（准备）+E（R次执行）+D（清理），再取中位数**。读取/COO转CSR不计入该指标，完整程序 wall 另列，不能混用。原始代码没有独立计划准备阶段，因此 P=D=0。控制版本也保留首次执行开销，没有只给候选预热。

预先冻结 protocol.json。正式进程计划1960个：关键条件560、旧输入筛查660、新保留集480、大矩阵配对80、规模/重复次数敏感性60、消融120。关键条件和主大矩阵分别对原始及v2各10个相邻随机AB/BA进程对，共320对；候选每条件20样本，每个控制10样本。其他条件每方5个独立进程。两组候选合并计算条件中位数，区间仅使用对应控制的10对；配对点值可能与全体中位数之比不同。

95%区间采用固定种子20261027、20000次配对比值中位数 bootstrap，是本环境下的样本区间。其余五进程组只报告描述统计。任何门槛都是工程准入标准，不能据此声称普适性能保证。规则在代码推送前冻结，正式实验后不调参数或删除负样本。

v2.2 的 `--v22-policy=v2` 完全委托旧v2；`--v22-empty=off` 只关闭非零矩阵的非空行索引，零矩阵加零路径仍启用。显式 `--execution=serial` 委托旧v2串行路径，因此不能把这一组称为“只改一个线程参数的v2.2”。同二进制诊断用于减少链接布局/浮点方式的干扰，只有一个进程中的轮转观察，不作为独立进程重复。

v2.2委托路线的validation_s字段为0，表示包装层没有单独转录旧v2的分项计时；它仍执行原有完整验证，耗时包含在P中。不能把该字段读成跳过验证或真实零成本。CSV保留上一轮解析器的profile相关空列，只为格式连续；v2.2没有读取profile。

日志nonempty_rows是已建索引的长度，未建索引时为0，并非矩阵非空行的普遍统计；委托路线empty_rows也没有重新统计。分析应结合route和输入元数据阅读这些诊断字段。

同二进制内v2与v2.2调用的旧内核使用相同浮点编译方式；original继续链接生产csr.o。它没有把原始及优化内核强行改成同一编译选项，不能据其差值单独证明某个指令或浮点选项的收益。

## 文件索引

- `protocol.json`、`frozen-harness.json`：正式实验前的约定与脚本哈希。
- `source-provenance.json`、`build.json`、`git-provenance.json`：固定提交、源文件/程序哈希与分支记录。
- `calibration.json`：提交代码前180个独立CLI校准观察及完整命令，不与正式样本混合。
- `verification-builds.json`、`correctness.json`：七种单元测试配置，以及完整向量/类型兼容检查。
- `measurements.csv`、`raw/`：每次正式进程的命令、标准输出、错误输出和资源记录；原始日志保留。
- `summary.csv/json`、`comparisons.csv`、`comparison-cases.json`：全条件摘要和三方逐例比较。
- `paired-analysis.json`、`decision.json`、`结果分析.md`：配对证据、冻结门槛判定与负结果。
- `diagnostic.json`、`csr-object-proof.json`、`raw/vectorization-*`：同二进制诊断与编译证据。
- `sampling-diagnosis.json`：新空行输入的64点抽样混叠漏选，与实际route交叉核对；只做结构分析，不追加性能样本或改策略。
- `figures/`：可复现图表；`audit.json`：完整性核验。

结果和当前分支以最终“结果分析.md”为准。未锁定宿主机频率，没有DRAM控制器或STREAM测量；不得把逻辑工作集大小或耗时曲线当作已经测得的带宽瓶颈。
