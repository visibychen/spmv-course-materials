#!/usr/bin/env python3
"""Render the reviewed interpretation with numbers directly from summaries."""
from pathlib import Path
import json
from analyze_results import find,table,MAIN

HERE=Path(__file__).resolve().parent

def main():
    old=find('large','original',24,9)
    sell=find('large','sell16',24,9)
    best=min((find('large',v,t,9) for v in MAIN[1:] for t in [1,12,24]),key=lambda x:x['compute_total_median_s'])
    lines=['# v1 结果分析与采用决定','',
        '**结论：v1 有明确的适用输入，但不适合作为原始项目的统一替换。** 本轮完整实现了调研方案的首轮 CSR 对照与无排序 SELL8/16，未将任何候选自动设为默认。为保留当前工程基线，实验后核心仓库切回原始 `master`；已实现的代码、测试和说明保留在 GitHub 的 `optimization/v1` 分支。',
        '',
        '采用判断以此前 baseline 的超大矩阵为主，同时看 R=9、原始最佳线程数、准备成本和样本波动。单线程或 12 线程的加速不能代替相对原始最佳配置的比较；不同输入上有效也不代表适合所有输入。这里的“保留原始”不表示所有 v1 内核都更慢。',
        '', '## 1. 超大矩阵：同线程与工程最佳配置','']
    rows=[]
    for t in [1,12,24]:
        a=find('large','original',t,9);b=find('large','sell16',t,9);c=find('large','csr-scalar',t,9)
        rows.append([t,f'{a["median_ms"]:.3f}',f'{c["median_ms"]:.3f}',f'{b["median_ms"]:.3f}',
                     f'{a["median_ms"]/b["median_ms"]:.3f}×',f'{b["prepare_median_s"]:.3f}',
                     f'{a["compute_total_median_s"]:.3f}',f'{b["compute_total_median_s"]:.3f}'])
    lines += [table(['线程','原始 / ms','标量 CSR / ms','SELL16 / ms','SELL16 内核加速','SELL16 准备 / s','原始 9 次 / s','SELL16 准备+9次 / s'],rows),'',
        f'原始最佳配置为 24 线程：单次 **{old["median_ms"]:.3f} ms**。SELL16 同线程为 **{sell["median_ms"]:.3f} ms**，内核比值 **{old["median_ms"]/sell["median_ms"]:.3f}×**；但准备+9次的中位数为 **{sell["compute_total_median_s"]:.3f} s**，原始为 **{old["compute_total_median_s"]:.3f} s**。',
        '',
        '历史 baseline 的 24 线程为 96.908 ms，本轮重测有差异。这里始终用本轮匹配条件的原始样本作分母，不把历史较慢数字与新内核直接相除来夸大收益；历史记录没有改写。WSL 宿主调度和未锁频率是本实验的限制。',
        '',
        f'在所有新增候选和 1/12/24 线程中，按准备+9次中位数事后选择的最小值是 `{best["variant"]}` / {best["threads"]} 线程的 **{best["compute_total_median_s"]:.3f} s**。这个事后最小值只是描述已测数据，没有实现或免费获得自动调参器。全表保留各候选极差；接近或重叠的数值不能解释为稳定的通用提升。',
        '',
        '原始 novec 的 24 线程和新二进制的 original 路径已各补测 5 次。前者说明“关闭向量化”也要分线程和输入评估；后者用于观察包装、代码布局、缓存状态与系统波动的影响。不能把回退路径偶然更快的中位数算作 SELL 的算法收益。',
        '', '## 2. 调用次数与转换成本','']
    rows=[]
    for r in [1,9,100]:
        a=find('large','original',24,r);b=find('large','sell16',24,r)
        rows.append([r,f'{a["median_ms"]:.3f}',f'{b["median_ms"]:.3f}',f'{b["prepare_median_s"]:.3f}',
                     f'{a["compute_total_median_s"]:.3f}',f'{b["compute_total_median_s"]:.3f}',
                     f'{a["compute_total_median_s"]/b["compute_total_median_s"]:.3f}×'])
    lines += [table(['实际 R','原始单次 / ms','SELL16 单次 / ms','准备 / s','原始计算总计 / s','SELL16 准备+执行 / s','含准备加速比'],rows),'',
        '这是独立运行的 R=1/9/100，并非把同一组单次数据简单乘以 R。准备+执行为逐进程相加后取中位数；全过程 wall 另见汇总表，包含约秒级的文本读取与 CSR 构建，因此常会遮蔽内核差异。',
        '',
        '回本模型采用 R>P/(T0−T1)，仅在 T1<T0 时成立。模型用中位数估计，实际 R 改变可能同时改变频率、缓存与同步占比；所以表中的实测总成本优先于外推。P 的波动和释放成本也会影响最终用户体验，不能保证达到模型次数后每次都获益。',
        '', '![超大矩阵内核及转换成本](large-comparison.png)',
        '', '## 3. 极端输入：收益、退化和保护','']
    cases=[('random1','sell16'),('random4','sell16'),('random8','sell8'),('random15','sell16'),
           ('heavy-clustered','sell16'),('heavy-scattered','sell16'),('giant-row','csr-pack'),
           ('giant-row','sell16'),('empty99','sell16'),('cache-small','sell16')]
    rows=[]
    for name,v in cases:
        a=find(name,'original');b=find(name,v)
        rows.append([name,v,f'{a["median_ms"]:.4f}',f'{b["median_ms"]:.4f}',f'{a["median_ms"]/b["median_ms"]:.3f}×',b['reason']])
    lines += [table(['12线程输入','候选','原始 / ms','候选 / ms','内核加速比','实际路径原因'],rows),'',
        '以上用例同时展示正收益、退化与回退，完整 22 类输入以及额外 1/24 线程结果均在 [汇总表](汇总表.md) / CSV 中。每个正式条件 5 个独立进程，没有删去慢样本。',
        '', '![极端输入；回退行已标注](extreme-comparison.png)',
        '',
        '- **短行与局部访问**：SELL 在部分短行、带状和热 x 输入有效，但 C=16 并非总优于 C=8；部分行长退化。与最强已测标量 / pack CSR 的差距通常小于与原始自动向量化 CSR 的差距，不能将全部收益归功于布局。',
        '- **集中长尾**：SELL16 在本构造中较快，但仍按连续 slice 分配任务，集中长行仍主要落在少数线程上。这里没有实现工作量均衡；分层抽样的列区间结构也可能改善跨行访问局部性，不能据此推断真实长尾矩阵同样加速。',
        '- **分散长尾、巨行和 99% 空行**：SELL 预检拒绝过量填充。巨行的 C=8/16 槽数为 8,099,992 / 16,099,984（原 nnz=1,099,999）；99% 空行为原 nnz 的 8/16 倍。拒绝前仍发生检查，绝不是零开销。回退时只执行原始内核，表中差异不是 SELL 解决了这些问题。',
        '- **百万元素巨行**：CSR-pack 的多累加器与横向归约有收益，但仍整行归一个线程。要让一条巨行跨线程，必须做调研中的 merge / 分段修正，不能只换普通行调度。pack 的求和结合顺序已改变，必须保留数值测试。',
        '- **小缓存 / 极少行 / 零元**：固定 PASSIVE 等待策略和逐次屏障可能主导计时。微小百分比且极差重叠的差异没有足够证据作为优化结论；更宽的 SIMD 也会减少独立 slice 数。',
        '', '## 4. 数值、资源与功能边界','',
        '核心测试每种配置 850 项：实际 native 构建、1/12/24 线程 ASan+UBSan，以及不带 `-march=native` 的 portable 构建，均通过。CLI / 全量矩阵检查 93 项，另有 35 项类型与对称输入兼容性对照。类型兼容性包括原程序本来不支持的组合：要求相同失败行为，不将它们误记为成功算数。',
        '',
        '超大矩阵在五个主后端、12 线程、R=3 下，全部 1200 万个输出与生成器期望值精确相等。它使用全 1 x 和精确二进制分数，只证明这个输入；一般浮点测试另外使用变化的 x、非零 y、无序 / 重复项、显式零、负值、NaN/Inf、消去、subnormal 与带符号零输入，并用 long double 及行长 / Σ|a·x| 误差界验证。不承诺普遍逐位一致。',
        '',
        '无效 lane 的 gather 与尾部写回均掩蔽；测试包含空行和 x[0]=Inf/NaN，避免填充项读 x[0]。三处分配失败已通过链接器包装逐一注入，检查回退和释放；也检查非法 CSR、尺寸、超大计数、零内存预算。没有实际分配数十 GB 制造物理 OOM，也没有模拟缺少 AVX 的 CPU。',
        '',
        '新增主程序在 nnz=0 且 --flops>0 时清楚报错；原始版本以 2 秒超时确认不终止。负的 repeat / flops 被拒绝。f64、混合精度、整数、复数及对称展开保持原始分派；足够大的对称用例还实际执行了两种 SELL。',
        '']
    for v in ['sell8','sell16']:
        b=find('large',v,24,9)
        lines += [f'- `{v}` 超大输入额外数组 **{b["extra_bytes"]:,} B**（{b["extra_bytes"]/1024**2:.2f} MiB）；加上原 CSR 和 x/y 的模型合计 **{(960000008+b["extra_bytes"])/1024**3:.3f} GiB**，另有少量运行库空间；进程最大 RSS **{b["peak_rss_kib"]/1024**2:.3f} GiB**。']
    lines += ['',
        '额外数组包括 f32 值、int32 列号及 int64 slice_ptr；宽度由相邻指针差推得，不分配 row_map / row_length / slice_width。原 CSR 仍保留。最大 RSS 是全程峰值，可能出现在原 COO 与 CSR 共存的更早阶段，不能用“两个版本最大 RSS 接近”推断 SELL 没有额外驻留内存。实际 steady-state 应加上原 CSR、x/y 与上述派生数组。',
        '', '## 5. 编译器证据、局限与下一步','',
        '编译诊断和实际汇编保存在 raw/：原始 f32 自动向量化；局部标量没有 packed gather；pack 的八项主块出现 vmovss/vinsertps 取数和组装；SELL8/16 分别使用向量 gather 与跨行累加。pack 的编译器生成尾部路径仍可出现 gather 指令，因此没有声称整个函数完全不含 gather。新增显式 SIMD 单元局部关闭 FMA contraction；全局没有 fast-math。',
        '',
        '五次进程的中位数和极差足以展示本机输入敏感性，不构成跨平台保证，也不是正式显著性检验。未测真实矩阵、未锁 CPU 频率或宿主机负载、未测持续 DRAM 带宽；因此只将随机 x、缓存与访存压力作为有来源的解释方向，不宣称已证明达到带宽上限。',
        '',
        '本次停止在方案规定的首轮阶段 A+B1/B2，不因为有个别正收益就继续扩大格式复杂度。下一轮可独立研究按工作量划分与 merge-based 巨行拆分；排序、重排、对齐 / 预取等也必须逐项消融，不能先假设有收益。矩阵数值或结构变化必须重建 SELL 计划；x/y 可以逐次变化。',
        '',
        '原始记录、完整输入定义、校验和、复现命令和审计入口均见 [README](README.md)。代码提交与推送证据见 [git-provenance.json](git-provenance.json)；本资料仓库按用户指定消息提交到 main，核心 v1 只提交到独立分支，未合并原始 master。','']
    (HERE/'结果分析.md').write_text('\n'.join(lines))
    print('结果分析.md generated')

if __name__=='__main__':main()
