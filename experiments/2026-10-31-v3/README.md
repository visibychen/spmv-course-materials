# v3独立最终路线实验

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
