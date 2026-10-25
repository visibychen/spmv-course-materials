#!/usr/bin/env python3
"""Generate tables/figures from recorded process samples; no benchmark runs."""
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
DATA=json.loads((HERE/'summary.json').read_text())
MATRICES=json.loads((HERE/'matrices.json').read_text())
MAIN=['original','csr-scalar','csr-pack','sell8','sell16']

def find(name,v,t=12,r=None):
    rows=[x for x in DATA if x['matrix']==name and x['variant']==v and int(x['threads'])==t and (r is None or int(x['repeat'])==r)]
    assert len(rows)==1,(name,v,t,r,len(rows))
    return rows[0]

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def state(original,new):
    if new['max_ms']<original['min_ms']:return '5 次区间均更快'
    if new['min_ms']>original['max_ms']:return '5 次区间均更慢'
    return '区间重叠'

def generate():
    names=[m['name'] for m in MATRICES if m['name']!='large']
    inputs=[]
    for m in MATRICES:
        inputs.append([m['name'],f'{m["rows"]:,} × {m["columns"]:,}',f'{m["nonzeros"]:,}',
                       m['profile'],f'{m["file_bytes"]/1024**2:.2f}',m['sha256'][:16]+'…'])
    (HERE/'输入清单.md').write_text('# 输入清单\n\n合成输入、生成命令与完整 SHA-256 见 `matrices.json`。文件大小是文本 Matrix Market，不是 CSR 工作集。\n\n'+
        table(['输入','行 × 列','nnz','结构','MTX / MiB','SHA-256 前缀'],inputs)+'\n')
    extra=[]
    for name in names:
        for t in [1,24]:
            if not any(x['matrix']==name and x['variant']=='original' and int(x['threads'])==t for x in DATA):continue
            extra.append([name,t]+[f'{find(name,v,t)["median_ms"]:.4f}' for v in MAIN])
    (HERE/'补充线程对照.md').write_text('# 中等规模输入：补充线程对照\n\n单位 ms / SpMV，5 个进程的中位数。每个比较的 R 相同；完整极差与准备成本见 summary.csv。\n\n'+
        table(['输入','线程',*MAIN],extra)+'\n')
    md=['# v1 实测汇总表','',
        '由 `python3 analyze_results.py` 从 `summary.json` 生成。每格为 5 个独立进程的中位数；原始样本及极差另见 CSV。',
        '', '## 12 线程：各类输入的单次 SpMV / ms','']
    rows=[]
    for name in names:
        rows.append([name]+[f'{find(name,v)["median_ms"]:.4f}' for v in MAIN])
    md += [table(['输入',*MAIN],rows),'','## 12 线程：SELL 相对原始版本、适用性和准备成本','']
    rows=[]
    observations={}
    for name in names:
        old=find(name,'original'); strongest=min((find(name,v) for v in MAIN[:3]),key=lambda x:x['median_ms'])
        observations[name]={}
        for v in ['sell8','sell16']:
            new=find(name,v)
            rows.append([name,v,f'{old["median_ms"]/new["median_ms"]:.3f}×',
                         f'{strongest["median_ms"]/new["median_ms"]:.3f}×',f'{new["prepare_median_s"]*1000:.3f}',
                         new['reason'],state(old,new)])
            observations[name][v]=dict(original_speedup=old['median_ms']/new['median_ms'],
                                      strongest_csr=strongest['variant'],strongest_csr_speedup=strongest['median_ms']/new['median_ms'],
                                      interval_classification=state(old,new))
    md += [table(['输入','后端','相对原始加速比','相对最快已测 CSR','准备 / ms','选择原因','极差关系'],rows),'',
           '最快已测 CSR 是逐输入在 original / csr-scalar / csr-pack 中事后取最小中位数，仅作强对照；未据此实现自动选择。极差不重叠只是描述性证据，不是统计显著性检验。',
           '', '## 超大矩阵：同线程、同 R=9 对比','']
    rows=[];break_even={}
    for t in [1,12,24]:
        old=find('large','original',t,9)
        for v in MAIN+(['original-novec','v1-original'] if t==24 else []):
            x=find('large',v,t,9);delta=(old['median_ms']-x['median_ms'])/1000
            threshold=math.floor(x['prepare_median_s']/delta)+1 if delta>0 else None
            break_even[f'{t}/{v}']=threshold
            rows.append([t,v,f'{x["median_ms"]:.3f}',f'{x["min_ms"]:.3f}–{x["max_ms"]:.3f}',
                         f'{old["median_ms"]/x["median_ms"]:.3f}×',f'{x["prepare_median_s"]:.4f}',
                         f'{x["compute_total_median_s"]:.4f}',f'{x["wall_median_s"]:.2f}',
                         f'{x["peak_rss_kib"]/1024**2:.3f}',threshold if threshold else '不回本'])
    md += [table(['线程','后端','单次 / ms','最小–最大 / ms','内核加速比','准备 P / s','P+9T / s','进程 wall / s','峰值 RSS / GiB','模型回本 R'],rows),'',
           '回本列使用各项中位数的模型 P/(T0−T1)，严格更快取 floor+1；不是每次运行的保证。P+9T 列为每个进程 P+execute 后再取中位数。',
           '', '## 超大矩阵：24 线程，实际不同调用次数','']
    rows=[]
    for r in [1,9,100]:
        for v in ['original','sell8','sell16']:
            x=find('large',v,24,r)
            rows.append([r,v,f'{x["median_ms"]:.3f}',f'{x["prepare_median_s"]:.4f}',f'{x["compute_total_median_s"]:.4f}',f'{x["wall_median_s"]:.2f}'])
    md += [table(['R','后端','单次 / ms','准备 / s','准备+执行 / s','进程 wall / s'],rows),'',
           '准备+执行以共同 CSR 已建好为起点；不包含文件读取、CSR 创建、释放和输出。进程 wall 包含整个程序；性能实验不写结果向量。','']
    (HERE/'汇总表.md').write_text('\n'.join(md))
    (HERE/'comparisons.json').write_text(json.dumps(dict(extremes=observations,break_even=break_even),ensure_ascii=False,indent=2)+'\n')

    plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':0.25})
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    pos=np.arange(3);width=.15
    for i,v in enumerate(MAIN):
        points=[find('large',v,t,9) for t in [1,12,24]]
        y=[p['median_ms'] for p in points]
        err=[[p['median_ms']-p['min_ms'] for p in points],
             [p['max_ms']-p['median_ms'] for p in points]]
        axes[0].bar(pos+(i-2)*width,y,width,label=v,yerr=err,capsize=2,error_kw={'elinewidth':.8})
    axes[0].set_xticks(pos,['1','12','24']);axes[0].set_yscale('log')
    axes[0].set_ylim(60,1100)
    axes[0].set(xlabel='OpenMP threads',ylabel='ms / SpMV (log scale)',title='96M nonzeros: median + min/max, R=9')
    axes[0].legend(fontsize=8)
    for v in ['original','sell8','sell16']:
        y=[find('large',v,24,r)['compute_total_median_s'] for r in [1,9,100]]
        axes[1].plot([1,9,100],y,'o-',label=v)
    axes[1].set_xscale('log');axes[1].set_yscale('log')
    axes[1].set(xlabel='Actual calls R (log scale)',ylabel='Prepare + execute / seconds (log scale)',title='24 threads: measured amortization')
    axes[1].legend(fontsize=8)
    for suffix in ['png','svg']:fig.savefig(HERE/f'large-comparison.{suffix}',dpi=180)
    plt.close(fig)

    fig,ax=plt.subplots(figsize=(11,7.5),constrained_layout=True)
    ypos=np.arange(len(names));height=.35
    for i,v in enumerate(['sell8','sell16']):
        ratios=[find(n,'original')['median_ms']/find(n,v)['median_ms'] for n in names]
        ax.barh(ypos+(i-.5)*height,ratios,height,label=v)
    labels=[n+(' [fallback]' if find(n,'sell8')['selected']=='original' and find(n,'sell16')['selected']=='original' else '') for n in names]
    ax.set_yticks(ypos,labels);ax.invert_yaxis();ax.axvline(1,color='black',linewidth=1)
    ax.set(xlabel='Speedup vs original (above 1 is faster)',title='Requested SELL: 12 threads, median of 5 processes')
    ax.legend();
    for suffix in ['png','svg']:fig.savefig(HERE/f'extreme-comparison.{suffix}',dpi=180)
    plt.close(fig)
    print('tables, comparisons and figures generated')

if __name__=='__main__':generate()
