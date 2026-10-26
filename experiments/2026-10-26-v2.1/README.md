# v2.1 实现与实验记录

日期：2026-10-26（Asia/Shanghai）。源码提交先于正式实验完成，结果由固定提交构建，不在看到保留集成绩后改模型。

先读[结果分析](结果分析.md)与[分支决策](decision.json)，逐次数据见[measurements.csv](measurements.csv)，验证记录见[审计](audit.json)。

| 版本 | 固定提交 | 用途 |
| --- | --- | --- |
| 原始 | `9352c865044f4c8b344d6fe5a277200a89f7a08b` | 原始master、原编译器自动向量化 |
| v2 | `9b652e8da85b7a1ad255e0b4f8ddadc5e0558f1a` | 直接CSR/串行阈值/work/merge |
| v2.1 | `aa1ef3d9bfb93002f19d0bfffdb3074225bb7f15` | v2的子分支，提交“优化方案v2.1”，正式实验前已推送 |
| v1 | `f089579a489723547a354459d591c551a313c4bb` | 仅提供巨行pack强对照，不作为v2.1祖先 |

## 实现范围

核心入口 `--kernel=v2.1`，默认仍original，`--kernel=v2`继续可用。实现有效R预检、一个团队做完整prepare验证、准备/执行团队分别选择、有限离线成本profile、O(T)分区/merge坐标缓存、按拆行输出分配归并所有者，以及局部长行AVX2候选。没有引入格式副本、空行压缩或免费在线试跑；空行加零和每次真实y+=Ax保留。

profile是显式外部提示；缺失/指纹不匹配时保守走original，仍支付额外检查成本。模型是带余量的线性近似，不能保证所有输入更快；未单独拟合冷启动缓存项。实际团队不匹配时统一走未缓存的完整行回退，首版没有动态重绑定缓存。详见[固定源码说明](https://github.com/visibychen/csrspmv/blob/aa1ef3d9bfb93002f19d0bfffdb3074225bb7f15/docs/v2.1.md)。

## 复现与记录

所有构建/测量在WSL Ubuntu-22.04顺序运行，GCC11.4，`-O3 -march=native`，无全局fast-math。原始 `csr.c` 和v2源文件不变。OpenMP主条件为DYNAMIC=FALSE、PLACES=cores、PROC_BIND=spread、WAIT_POLICY=PASSIVE。

1. `run_experiments.py build`：从Git固定提交归档构建，生成构建标识、向量化日志及反汇编。
2. 先按[旧输入恢复脚本](../2026-10-26-v2/restore_reused_inputs.py)及[v2输入说明](../2026-10-26-v2/README.md)恢复忽略的旧矩阵。新真实矩阵使用[下载脚本](download_real.ps1)从NIST固定地址存入忽略的data目录；`run_experiments.py inputs`校验旧输入哈希、生成新种子/尺寸输入、记录新真实矩阵头部/来源/哈希。
3. `run_experiments.py verify`：核对完整输出。合成精确分数输入逐项比较；真实输入按f32转换及对称展开，用独立float64逐行累加和行长/绝对值和误差界。
4. `critical|screen|heldout|large|large-sensitivity|ablations`：按[预先冻结协议](protocol.json)逐阶段运行；原始命令、环境、stdout/stderr、wall/RSS/major-faults保留在raw。任务可恢复，已记录样本不重写。
5. `summarize`：从逐进程数据计算中位数。后续结果分析与审计脚本也随资料保留。

`measurements.csv`中的total逐进程相加P+E+清理后汇总，分项中位数不必相加等于total中位数。全进程wall包含读取和CSR转换，单独比较。原始程序的E计时只输出微秒级六位小数；微小输入主要用R100，不能把量化噪声当作微小加速。

关键组为相邻随机AB/BA独立进程对，分别比较v2.1/原始与v2.1/v2；同条件v2.1因此有20个样本，而每个控制10个，不伪称各方都是10个。其他组为5次随机顺序三方进程比较。所有慢样本保留。超大矩阵R9覆盖T12/24配对，T1补充；R1/R100敏感性集中T24。本轮没有跑满T1/12/24×R1/9/100笛卡尔积，不外推未测点。

## 校准与保留集

[calibrate.c](calibrate.c)使用12个独立形状和种子19871207，在六个团队上轮转五种后端；918条是**同一个校准进程内的观察**，不是918个独立进程。准备模型使用完整prepare的成本。`fit_profile.py`以非负最小二乘拟合并冻结[profile](profile.txt)，工作集8MiB分组和10%余量是本项目规则，不是物理缓存测量或置信区间。所有拟合残差见[calibration-fit.json](calibration-fit.json)，存在较大误差的模型，正式保留集负责检验它。

一次初步校准对original也禁用了收缩，与生产构建不匹配，已排除，原记录保留于raw/calibration-initial-contract-off.csv。最终校准链接生产构建的逐翻译单元对象；校准耗时单列，若每任务重新校准则另行加回，不能视为免费。

正式性能计时前另做模型可辨识性核查：stream-short8每个团队只有一个尺寸点，无法区分规模斜率与调用固定开销，6个模型从最终profile排除，其余观察不变。初版profile/拟合报告保留在raw/pre-identifiability-*，前后SHA和原因记入protocol.json。该修正发生在首条正式性能样本之前，没有利用正式成绩调参。

52个输入中，32个旧输入均为开发/回归证据；16个新合成输入和4个新真实输入是本轮保留输入，没有复用v2旧保留集名义。新结构含相邻双巨行、八巨行、中部单巨行、周期/随机/聚集空行、长尾、带状/热列、原阈值附近与缓存内规模。

新增真实数据为NIST的BCSSTK17、WEST0479、SHERMAN3、SAYLR4，涉及结构工程、化工及两类油藏模拟；不能说来自四个不同应用领域。WEST0479含显式零，保留存储项，不按网站的数值非零数悄悄删项。对称BCSSTK17运行时两边都展开，stored/expanded nnz分别记录。页面未明确独立许可，本轮只保存来源/哈希/头部，不把MTX放进Git。

构建、校准及MTX/输出大文件在build/data中忽略；raw与汇总可提交。`.gitattributes`仅关闭raw生成文本和SVG导出的空白告警，未清洗或删除其原始字节。原先v1/v2实验记录不改写。
