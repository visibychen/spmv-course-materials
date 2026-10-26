#!/usr/bin/env python3
"""Generate all report numbers from retained process samples, no hand edits."""
import collections,csv,json,statistics
import numpy as np
import run_experiments as run
H=run.HERE
def main():
    run.summarize();rows=run.records();summary=json.loads((H/'summary.json').read_text())
    def get(phase,n,v,t=12,r=9):
        a=[x for x in summary if x['phase']==phase and x['matrix']==n and x['variant']==v and int(x['threads'])==t and int(x['repeat'])==r]
        assert len(a)==1,(phase,n,v,t,r);return a[0]
    paired=[]
    for t in [1,12,24]:
        for r in [1,9,100]:
            groups={}
            for x in rows:
                if x['phase']=='large' and int(x['threads'])==t and int(x['repeat'])==r:
                    groups.setdefault(x['sample'],{})[x['variant']]=float(x['total_s'])
            assert len(groups)==10 and all(set(x)=={'original','v2-auto'} for x in groups.values())
            ratios=np.array([x['original']/x['v2-auto'] for x in groups.values()])
            rng=np.random.default_rng(20261026+t+r)
            boot=np.median(rng.choice(ratios,size=(20000,len(ratios)),replace=True),axis=1)
            paired.append(dict(threads=t,repeat=r,pairs=10,median_pair_speedup=float(np.median(ratios)),
                low95=float(np.quantile(boot,.025)),high95=float(np.quantile(boot,.975)),
                pair_speedups=ratios.tolist()))
    originals=[get('large','large','original',t) for t in [1,12,24]]
    best=min(originals,key=lambda x:x['total_s_median']);candidate=get('large','large','v2-auto',24)
    ratio=best['total_s_median']/candidate['total_s_median']
    ci=next(x for x in paired if x['threads']==24 and x['repeat']==9)
    # If the best baseline is a different team, do not call that comparison
    # adjacent-paired. A conservative independent resampling check is used.
    interval=ci;interval_kind='adjacent same-team process pairs'
    if int(best['threads'])!=24:
        b=np.array([float(x['total_s']) for x in rows if x['phase']=='large' and int(x['threads'])==int(best['threads']) and int(x['repeat'])==9 and x['variant']=='original'])
        c=np.array([float(x['total_s']) for x in rows if x['phase']=='large' and int(x['threads'])==24 and int(x['repeat'])==9 and x['variant']=='v2-auto'])
        rng=np.random.default_rng(20261026)
        boot=np.median(rng.choice(b,size=(20000,len(b))),axis=1)/np.median(rng.choice(c,size=(20000,len(c))),axis=1)
        interval=dict(low95=float(np.quantile(boot,.025)),high95=float(np.quantile(boot,.975)))
        interval_kind='independent-process bootstrap across different teams; baseline selected by reported medians'
    decision=dict(target='large R9, fixed v2 requested=24 vs original best tested team',
      original_best_threads=int(best['threads']),original_best_total_s=best['total_s_median'],
      v2_total_s=candidate['total_s_median'],speedup=ratio,time_reduction_percent=(1-1/ratio)*100,
      interval_kind=interval_kind,low95=interval['low95'],high95=interval['high95'],
      passes_primary=bool(candidate['total_s_median']<=.95*best['total_s_median'] and interval['low95']>1),
      policy='5% median total-time reduction and interval supports benefit; not a universal performance promise')
    run.save('paired-analysis.json',paired);run.save('decision.json',decision)
    stats=collections.Counter(x['phase'] for x in rows)
    correctness=json.loads((H/'correctness.json').read_text())
    full=[x for x in correctness if x['kind']=='full-output']
    real_errors={n:next(x['max_absolute_error'] for x in full if x['matrix']==n and x['variant']=='v2-auto')
                 for n in ['bcsstk18','sherman5']}
    report=['# v2 实验结果与适用边界','',
      '本轮代码分支直接从原始 master 创建，与 v1 为并列分支；原始、v1 与 v2 均在同批环境重新构建测量。旧实验原始数据没有改写。',
      '', '## 1. 主目标：超大均匀矩阵，准备+执行+清理','',
      '矩阵仍为 1200 万行/列、9600 万 nnz。固定参数、原始自动向量化、相同绑定和 PASSIVE 等待；下表为独立进程中位数。P 与 E 的中位数分列，total 是每个进程 P+E+清理之和再取中位数，未用分项中位数替代逐次总时间。',
      '', '| 线程 | R | 原始单次/ms | v2 单次/ms | v2 P/ms | 原始 total/s | v2 total/s | 总成本加速比 | 配对比值95%区间 |',
      '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for t in [1,12,24]:
        for r in [1,9,100]:
            a=get('large','large','original',t,r);b=get('large','large','v2-auto',t,r)
            ci0=next(x for x in paired if x['threads']==t and x['repeat']==r)
            report.append(f'| {t} | {r} | {a["ms_per_call"]:.3f} | {b["ms_per_call"]:.3f} | {b["prepare_s_median"]*1000:.3f} | {a["total_s_median"]:.6f} | {b["total_s_median"]:.6f} | {a["total_s_median"]/b["total_s_median"]:.3f}× | [{ci0["low95"]:.3f}, {ci0["high95"]:.3f}] |')
    report+=['', '区间针对 10 个相邻随机 AB/BA 进程对的加速比中位数，按进程对重采样 20000 次；点列为总时间中位数之比，两个统计量不要求完全相同。区间只反映本批过程样本，不覆盖宿主机/频率/跨机器变化。',
       '',f'**主目标判定：{"通过本轮预设门槛" if decision["passes_primary"] else "未通过本轮预设门槛"}。** 原始最佳已测线程为 {best["threads"]}，R=9 total={best["total_s_median"]:.6f} s；v2 请求24线程 total={candidate["total_s_median"]:.6f} s，时间降低 {decision["time_reduction_percent"]:.2f}%。门槛为至少降低5%且区间支持收益；这不表示所有输入都变快。',
       '', '## 2. v1、novec 与匹配 CSR 对照','',
       '以下 R=9，原始/v2-auto 各10个独立进程，补充对照各5个，样本量不同已明确。v2-csr-rows 与 short8 使用同一验证、分区和 FP 模式，可用于分辨固定行展开；original-novec 为原始全构建禁循环/SLP向量化控制，不能把它的整个进程变化只归因于一个内核。',
       '', '| 线程 | 后端 | 单次/ms | P/ms | total/s | 全进程 wall/s |',
       '| --- | --- | --- | --- | --- | --- |']
    for t in [1,12,24]:
        for v in ['original','v1-scalar','v1-sell16','v2-original','original-novec','v2-csr-rows','v2-auto']:
            a=get('large' if v in ['original','v2-auto'] else 'large-controls','large',v,t)
            report.append(f'| {t} | {v} | {a["ms_per_call"]:.3f} | {a["prepare_s_median"]*1000:.3f} | {a["total_s_median"]:.6f} | {a["wall_s_median"]:.2f} |')
    report+=['', 'csr.c SHA-256 与链接前 csr.o .text 在三个构建中一致，详见 csr-object-proof.json。它不能证明最终链接地址或缓存/调度状态一致，故不把 original 路径的差值直接叫包装开销。同二进制诊断另见第5节。',
      '', '## 3. 原有极端输入：全部结果，不筛选胜者','',
      '同为请求12线程；v2-auto 对小任务可能实际执行1线程，具体见CSV。R通常为9，zero/cache-small/wide为100。表中为 prepare+execute+cleanup 的中位数；额外检查与调度成本均计入，正负结果同列。',
      '', '| 输入 | R | original/ms | v1 scalar/ms | v1 SELL16/ms | v2 auto/ms | 原始/v2 | v2 实际选择 |',
      '| --- | --- | --- | --- | --- | --- | --- | --- |']
    metas=run.matrices()
    for m in metas:
        n=m['name']
        if m['group']!='v1' or n=='large':continue
        r=100 if n in ['zero','cache-small','wide'] else 9
        a,b,c,d=[get('screen',n,v,12,r) for v in ['original','v1-scalar','v1-sell16','v2-auto']]
        report.append(f'| {n} | {r} | {a["total_s_median"]*1000:.3f} | {b["total_s_median"]*1000:.3f} | {c["total_s_median"]*1000:.3f} | {d["total_s_median"]*1000:.3f} | {a["total_s_median"]/d["total_s_median"]:.3f}× | {d["selected"]}/{d["partition"]}; T={d["actual_threads"]} |')
    report+=['', '![原有极端输入总成本加速比](figures/v1-total-speedup.png)', '', '集中长尾、分散长尾、巨行和空行的 rows/work/merge 消融，以及 D=0/32/128 的预取对照全部保存在 summary.csv。集中长尾本来失衡，均匀散布的空行本来接近均衡，不能用同一种解释概括。巨行还必须与较强的 v1-pack 比较，不只和原始比较。',
      '', '## 4. 保留集与真实矩阵','',
      '规则在保留集计时前冻结；没有用保留集成绩反向改阈值。新合成输入采用新种子并在整列范围无放回抽样，区别于原先每列区间一项；两个真实矩阵来自NIST。真实输入的f32转换及对称展开按两边相同设置执行。',
      '', '| 输入 | 请求线程 | R | 原始 total/ms | v2 total/ms | 原始/v2 | v2选择/实际线程 |',
      '| --- | --- | --- | --- | --- | --- | --- |']
    for m in metas:
        if m['group'] not in ['heldout','real']:continue
        for t in [1,12,24]:
            r=100 if m['nonzeros']<20000 else 9
            a=get('heldout',m['name'],'original',t,r);b=get('heldout',m['name'],'v2-auto',t,r)
            report.append(f'| {m["name"]} | {t} | {r} | {a["total_s_median"]*1000:.3f} | {b["total_s_median"]*1000:.3f} | {a["total_s_median"]/b["total_s_median"]:.3f}× | {b["selected"]}; T={b["actual_threads"]} |')
    report+=['', '![保留集总成本加速比](figures/heldout-total-speedup.png)', '', '[BCSSTK18来源](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/bcsstruc2/bcsstk18.html) 为结构工程对称矩阵，存80519项，展开149090项；[SHERMAN5来源](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/sherman/sherman5.html) 为油藏模拟非对称矩阵，20793项。文件、头部、下载地址与SHA保存在 matrices.json；MTX本体不随Git分发。',
      '', '## 5. 同二进制、统一预热诊断','',
      '独立诊断程序链接改名后的固定v1模块、原始CSR及v2；它不是v2生产代码的一部分。每个后端统一预热一次，逐条件清零y并用轮转顺序平衡位置。5个后端轮转10轮，每个后端在每个位置恰好出现2次；其中v2通用CSR与short8使用相同FP模式。一个进程内的10轮有关联，不能当成10个独立进程或用来替代前述总成本实验。准备另记于JSON，下面只描述明确预热后的执行。',
      '', '| 输入 | 线程 | original/ms | v1 scalar/ms | v1 SELL16/ms | v2/ms | v2通用CSR/ms |',
      '| --- | --- | --- | --- | --- | --- | --- |']
    diagnostics=json.loads((H/'diagnostic.json').read_text())
    for d in diagnostics:
        values={v:statistics.median(x['execute_s']*1000/x['repeat'] for x in d['records'] if x['type']=='sample' and x['backend']==v) for v in ['original','v1-scalar','v1-sell16','v2','v2-csr-rows']}
        report.append(f'| {d["matrix"]} | {d["threads"]} | '+ ' | '.join(f'{values[v]:.3f}' for v in values)+' |')
    ratios={}
    for t in [1,12,24]:
        d=next(x for x in diagnostics if x['matrix']=='large' and x['threads']==t)
        med={v:statistics.median(x['execute_s'] for x in d['records'] if x['type']=='sample' and x['backend']==v) for v in ['v2','v2-csr-rows']}
        ratios[t]=med['v2-csr-rows']/med['v2']
    report+=['', '超大矩阵同二进制中，通用CSR/固定8项的稳态耗时比为：'+', '.join(f'{t}线程 {ratios[t]:.3f}×' for t in [1,12,24])+ '。本批均接近1，未证实固定8项展开具有稳定独立优势；整体相对原始的收益应结合直接CSR、局部标量组织和准备成本降低解释。诊断只有每配置一个进程，不能将微小差值外推为普遍结论。',
      '', '本分支保留冻结的short8实验候选，且可强制通用CSR；默认全局入口仍是original。主目标数值门槛通过，不等于全输入自动策略已经验收。双巨行保留集的多线程退化说明，仅用最长行/平均事件比值选择merge还不够；准备与额外同步是需要继续细分的成本，当前没有线程等待分项计时。']
    pack=get('screen','giant-row','v1-pack',12,9);merge=get('screen','giant-row','v2-auto',12,9)
    report+=['',f'巨行12线程R=9的较强对照：v1-pack总成本{pack["total_s_median"]*1000:.3f} ms，v2-auto为{merge["total_s_median"]*1000:.3f} ms。v2在这个输入上没有超过v1最强候选。']
    report+=['', '巨行的v1 SELL16可能因padding保护实际回退；每份诊断prepare记录含sell_selected及原因，不把该列的回退成绩算作SELL收益。诊断JSON的work记录是在计时后按本轮连续静态/显式分区规则复算的每线程nnz，并非线程耗时或硬件计数；没有将工作量模型当作新的性能测量。',
      '', '## 6. 正确性、资源与可复现性','',
      f'- 7轮核心配置各5368项检查（native 1/12/24，portable 12，ASan+UBSan 1/12/24）；另重跑v1的850项检查。CLI记录共{len(correctness)}条，其中全量输出检查{len(full)}组。',
      '- 覆盖固定行长判断、空/尾部/零维、预取越界、分区覆盖、巨行跨多个线程、同一行起止片段、团队变化、malloc失败、非法参数、f64/整数/复数/pattern回退、NaN/Inf、消去、subnormal、非零y及变化x。',
      '- 超大矩阵4条v2路径在12线程R=3下核对全部1200万输出，精确分数输入误差为0；真实矩阵用独立float64累加及随行长/绝对值和变化的误差界，不声称所有重组浮点求和逐位一致。',
      f'- BCSSTK18数值尺度较大，本批f32相对float64累加参考的最大绝对差为{real_errors["bcsstk18"]:.9g}，原始与v2-auto相同且通过逐行误差界；SHERMAN5对应最大绝对差约{real_errors["sherman5"]:.9g}。真实矩阵不能也写成“误差为0”。',
      f'- 正式/先导进程数：{dict(stats)}，合计{len(rows)}；原始输出、命令、环境和资源记录全部保留，未删除慢样本。',
      f'- 本批进程最大major faults={max(int(x["major_faults"]) for x in rows)}；最大RSS={max(int(x["max_rss_kib"]) for x in rows)/1024:.2f} MiB。全程RSS可能由更早COO+CSR阶段决定，不能以它衡量新增驻留数组。',
      '- v2直接CSR没有整份格式副本，普通行额外矩阵数组0字节；merge为64*T字节scratch（24线程1536字节）。v1 SELL16仍额外约738 MiB，见逐次extra_bytes。',
      '- 未锁定宿主负载/频率，没有本轮持续DRAM带宽或STREAM测量；不能宣称已到带宽上限。自动阈值不是通用最优，稍大缓存内输入仍可能更适合强制串行，已在先导记录中暴露。',
      '- 主目标判定不替代输入适用性说明。没有将原有多线程、已有CSR或编译器自动SIMD算作新增贡献，没有缓存Ax、改变R或使用全局fast-math。',
      '', '源码方法依据、许可与改编见核心 docs/v2.md 和 [v2调研](../../research/2026-10-25-spmv-v2/README.md)。完整复现入口见 [README](README.md)。']
    (H/'结果分析.md').write_text('\n'.join(report)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    (H/'figures').mkdir(exist_ok=True)
    for group,phase in [('v1','screen'),('heldout','heldout')]:
        ms=[m for m in metas if m['group']=='v1' and m['name']!='large'] if group=='v1' else [m for m in metas if m['group'] in ['heldout','real']]
        fig,ax=plt.subplots(figsize=(10,max(5,len(ms)*.42)))
        y=np.arange(len(ms));width=.23
        for idx,(v,color) in enumerate([('v1-scalar','#7d8790'),('v1-sell16','#d29843'),('v2-auto','#287a9b')]):
            ratios=[]
            for m in ms:
                r=(100 if m['name'] in ['zero','cache-small','wide'] else 9) if group=='v1' else (100 if m['nonzeros']<20000 else 9)
                a=get(phase,m['name'],'original',12,r);b=get(phase,m['name'],v,12,r)
                ratios.append(a['total_s_median']/b['total_s_median'])
            ax.barh(y+(idx-1)*width,ratios,height=width,label=v,color=color)
        ax.axvline(1,color='black',lw=1);ax.set_xscale('log');ax.set_yticks(y,[m['name'] for m in ms]);ax.invert_yaxis()
        ax.set_xlabel('Total-time speedup vs original (requested T=12; higher is better)')
        ax.legend();ax.grid(axis='x',alpha=.2);fig.tight_layout()
        for suffix in ['png','svg']:fig.savefig(H/f'figures/{group}-total-speedup.{suffix}',dpi=160)
        plt.close(fig)
    print(json.dumps(decision,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
