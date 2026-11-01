#!/usr/bin/env python3
"""Create the course report from fixed data, content blocks and screenshots."""
import argparse,json,hashlib,zipfile,re
from pathlib import Path
from docx import Document
from docx.shared import Pt,Cm,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
H=Path(__file__).resolve().parent
DATA=json.loads((H/'report-data.json').read_text(encoding='utf-8'))
BLOCKS=json.loads((H/'report-content.json').read_text(encoding='utf-8'))
S=DATA['summary'];A=H/'assets'
for name in ['simsun.ttc','times.ttf','timesbd.ttf']:
    font_manager.fontManager.addfont(str(Path('C:/Windows/Fonts')/name))
plt.rcParams.update({'font.family':['Times New Roman','SimSun'],'font.size':11,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False})
def pick(phase,m,t,R,v):
    rows=[x for x in S if x['phase']==phase and x['matrix']==m and str(x['threads'])==str(t) and str(x['repeat'])==str(R) and x['variant']==v]
    assert len(rows)==1,(phase,m,t,R,v)
    return rows[0]
def pair(phase,m,t,R):return [pick(phase,m,t,R,v) for v in ['original','v2-auto']]
def graphs():
    used=[]
    fig,axes=plt.subplots(1,3,figsize=(8,3.3))
    for ax,t in zip(axes,[1,12,24]):
        xs=pair('large','large',t,9);ys=[x['total_s_median'] for x in xs]
        ax.bar(['原始','v2'],ys,color=['#b6bdc6','#39738f'],width=.58)
        for i,y in enumerate(ys):ax.text(i,y+max(ys)*.035,f'{y:.3f}',ha='center',fontname='Times New Roman')
        ax.set_ylim(0,max(ys)*1.24);ax.set_title(f'T={t}');ax.set_ylabel('总成本 / s');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        used.append(dict(figure='5-1',matrix='large',threads=t,repeat=9,values=xs))
    fig.suptitle('主矩阵 R=9 计算总成本',y=1.01);fig.tight_layout();fig.savefig(A/'fig5-1.png',dpi=300,bbox_inches='tight');plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,3.5));orig=[];opt=[]
    for phase,m in [('screen','heavy-clustered'),('screen','giant-row'),('heldout','heldout-longtail')]:
        xs=pair(phase,m,12,9);orig.append(xs[0]['total_s_median']*1000);opt.append(xs[1]['total_s_median']*1000)
        used.append(dict(figure='5-2',matrix=m,threads=12,repeat=9,values=xs))
    import numpy as np
    pos=np.arange(3);ax.bar(pos-.18,orig,.36,label='原始',color='#b6bdc6');ax.bar(pos+.18,opt,.36,label='v2',color='#39738f')
    for x,y in zip(pos-.18,orig):ax.text(x,y+1,f'{y:.3f}',ha='center',fontname='Times New Roman',fontsize=10)
    for x,y in zip(pos+.18,opt):ax.text(x,y+1,f'{y:.3f}',ha='center',fontname='Times New Roman',fontsize=10)
    ax.set_xticks(pos,['集中长尾','单巨行','保留集长尾']);ax.set_ylabel('总成本 / ms');ax.set_ylim(0,max(orig)*1.23);ax.legend(frameon=False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(A/'fig5-2.png',dpi=300);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(8,3.4))
    for ax,t in zip(axes,[1,12]):
        xs=pair('heldout','sherman5',t,9);ys=[x['total_s_median']*1000 for x in xs]
        ax.bar(['原始','v2'],ys,color=['#b6bdc6','#39738f'],width=.56)
        for i,y in enumerate(ys):ax.text(i,y+max(ys)*.035,f'{y:.3f}',ha='center',fontname='Times New Roman')
        ax.set_ylim(0,max(ys)*1.28);ax.set_ylabel('总成本 / ms');ax.set_title(f'请求 T={t}，实际 T={t}/1');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        used.append(dict(figure='5-3',matrix='sherman5',threads=t,repeat=9,values=xs))
    fig.suptitle('SHERMAN5 小任务策略',y=1.01);fig.tight_layout();fig.savefig(A/'fig5-3.png',dpi=300,bbox_inches='tight');plt.close(fig)
    (H/'chart-data.json').write_text(json.dumps(used,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def font(run,size=12,bold=False):
    run.font.name='Times New Roman';run.font.size=Pt(size);run.font.bold=bold;run.font.color.rgb=RGBColor(0,0,0)
    rf=run._element.get_or_add_rPr().get_or_add_rFonts()
    for k,v in [('ascii','Times New Roman'),('hAnsi','Times New Roman'),('eastAsia','宋体'),('cs','Times New Roman')]:rf.set(qn('w:'+k),v)
    for attr in list(rf.attrib):
        if 'Theme' in attr or 'theme' in attr:del rf.attrib[attr]
def indent(p,size=12,on=True):
    p.paragraph_format.first_line_indent=Pt(size*2 if on else 0)
    p._p.get_or_add_pPr().find(qn('w:ind')).set(qn('w:firstLineChars'),'200' if on else '0')
def text(p,value,size=12,bold=False):
    run=p.add_run(value);font(run,size,bold);return run
def link(p,label,url):
    rid=p.part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    h=OxmlElement('w:hyperlink');h.set(qn('r:id'),rid)
    r=OxmlElement('w:r');rp=OxmlElement('w:rPr');f=OxmlElement('w:rFonts')
    for k,v in [('ascii','Times New Roman'),('hAnsi','Times New Roman'),('eastAsia','宋体')]:f.set(qn('w:'+k),v)
    rp.append(f);sz=OxmlElement('w:sz');sz.set(qn('w:val'),'24');rp.append(sz);r.append(rp)
    t=OxmlElement('w:t');t.text=label;r.append(t);h.append(r);p._p.append(h)
def build(outdir):
    graphs();d=Document();figs=[];headings=[];body=[]
    sec=d.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=Cm(2.3);sec.bottom_margin=Cm(2.2);sec.left_margin=Cm(2.6);sec.right_margin=Cm(2.4);sec.header_distance=Cm(1.1);sec.footer_distance=Cm(1.1)
    for name,size,bold in [('Normal',12,False),('Title',15,True),('Heading 1',15,True),('Heading 2',14,True),('Heading 3',12,True),('Caption',12,False)]:
        st=d.styles[name];st.font.name='Times New Roman';st.font.size=Pt(size);st.font.bold=bold;st.font.color.rgb=RGBColor(0,0,0)
        rf=st.element.get_or_add_rPr().get_or_add_rFonts()
        for k,v in [('ascii','Times New Roman'),('hAnsi','Times New Roman'),('eastAsia','宋体'),('cs','Times New Roman')]:rf.set(qn('w:'+k),v)
        for attr in list(rf.attrib):
            if 'Theme' in attr or 'theme' in attr:del rf.attrib[attr]
        pf=st.paragraph_format;pf.line_spacing=1.5;pf.space_after=Pt(0);pf.widow_control=True
        if name.startswith('Heading'):pf.space_before=Pt(10);pf.space_after=Pt(5);pf.keep_with_next=True
    for style in d.styles:
        for border in style.element.xpath('.//w:pBdr'):
            border.getparent().remove(border)
    d.styles['Normal'].paragraph_format.first_line_indent=Pt(24)
    p=sec.header.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER;indent(p,on=False);text(p,'计算机组成原理课程设计')
    p=sec.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER;indent(p,on=False)
    f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');p._p.append(f)
    d.core_properties.title='CSR稀疏矩阵向量乘法优化实验报告';d.core_properties.subject='csrspmv v2方法与实验';d.core_properties.author='visiby'
    p=d.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;indent(p,on=False);text(p,'CSR 稀疏矩阵向量乘法优化实验报告',15,True)
    p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;indent(p,on=False);text(p,'2026年11月1日')
    def table(number,caption,headers,rows,widths):
        p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;indent(p,on=False);p.paragraph_format.keep_with_next=True;text(p,f'表{number} {caption}')
        tb=d.add_table(rows=1,cols=len(headers));tb.alignment=WD_TABLE_ALIGNMENT.CENTER;tb.autofit=False
        for c,w in zip(tb.columns,widths):c.width=Cm(w)
        for i,vals in enumerate([headers]+rows):
            cells=tb.rows[0].cells if i==0 else tb.add_row().cells
            trpr=cells[0]._tc.getparent().get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
            if i==0:trpr.append(OxmlElement('w:tblHeader'))
            for j,(cell,val) in enumerate(zip(cells,vals)):
                cell.width=Cm(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;tcpr=cell._tc.get_or_add_tcPr()
                mar=OxmlElement('w:tcMar')
                for side in ['top','left','bottom','right']:
                    x=OxmlElement('w:'+side);x.set(qn('w:w'),'80');x.set(qn('w:type'),'dxa');mar.append(x)
                tcpr.append(mar);b=OxmlElement('w:tcBorders')
                for side in ['top','left','bottom','right']:
                    x=OxmlElement('w:'+side);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'4');x.set(qn('w:color'),'D9D9D9');b.append(x)
                tcpr.append(b)
                if i==0:
                    x=OxmlElement('w:shd');x.set(qn('w:fill'),'E7EDF0');tcpr.append(x)
                p=cell.paragraphs[0];indent(p,on=False);p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.line_spacing=1.5;p.paragraph_format.keep_with_next=(i < len(rows));text(p,str(val),12,i==0)
    for b in BLOCKS:
        kind=b['type']
        if kind=='heading':
            n=b['level'];size=[0,15,14,12][n];p=d.add_paragraph(style='Heading '+str(n));indent(p,size)
            text(p,b['text'],size,True);headings.append((n,b['text']))
        elif kind=='body':
            p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY;indent(p);text(p,b['text']);body.append(b['text'])
        elif kind=='figure':
            path=A/f"fig{b['number']}.png"
            with Image.open(path) as im:w,h=im.size
            width=min(16.0,b['maxheight']*w/h)
            p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;indent(p,on=False);p.paragraph_format.keep_with_next=True;p.paragraph_format.space_before=Pt(5)
            shape=p.add_run().add_picture(str(path),width=Cm(width));shape._inline.docPr.set('descr',b['caption'])
            p=d.add_paragraph(style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;indent(p,on=False);text(p,f"图{b['number']} {b['caption']}");p.paragraph_format.space_after=Pt(6)
            figs.append(dict(number=b['number'],caption=b['caption'],asset=path.name,width_cm=width))
        elif kind=='table':table(b['number'],b['caption'],b['headers'],b['rows'],b['widths'])
        elif kind=='matrix_table':
            names=['large','heavy-clustered','giant-row','heldout-longtail','bcsstk18','sherman5'];labels=['主矩阵','集中长尾','单巨行','保留长尾','BCSSTK18','SHERMAN5'];meta={x['name']:x for x in DATA['matrices']};rows=[]
            for n,label in zip(names,labels):
                x=meta[n];rows.append([label,f"{x['rows']:,}",f"{x['columns']:,}",f"{x.get('expanded_nonzeros_verified',x['nonzeros']):,}"])
            table('4-1','主要输入规模',['输入','行数','列数','运行非零元'],rows,[4.2,3.6,3.6,4.6])
        elif kind=='main_table':
            rows=[]
            for t in [1,12,24]:
                x,y=pair('large','large',t,9);rows.append([str(t),f"{x['total_s_median']:.6f}",f"{y['total_s_median']:.6f}",f"{x['total_s_median']/y['total_s_median']:.3f}"])
            table('5-1','主矩阵R等于9的总成本',['T','原始/s','v2/s','加速比'],rows,[2,4.8,4.8,4.4])
        elif kind in ['references','pr_links']:
            refs=[('[1] 原始csrspmv源码与README','https://github.com/jamtrott/csrspmv/tree/9352c865044f4c8b344d6fe5a277200a89f7a08b'),('[2] v2固定批次实验 数据与完整结果','https://github.com/visibychen/spmv-course-materials/tree/main/experiments/2026-10-26-v2'),('[3] v1开发与格式转换实验','https://github.com/visibychen/spmv-course-materials/tree/main/experiments/2026-10-25-v1'),('[4] v3最终路线实验与验收','https://github.com/visibychen/spmv-course-materials/tree/main/experiments/2026-10-31-v3'),('[5] Merrill与Garland的CPU merge实现','https://github.com/dumerrill/merge-spmv/blob/18895571ce9af960ee207dae541b0ffc701ea4bb/cpu_spmv.cpp'),('[6] NIST Matrix Market矩阵集合','https://math.nist.gov/MatrixMarket/'),('[7] v2方法说明与许可来源','https://github.com/visibychen/csrspmv/blob/optimization/v2/docs/v2.md')]
            if kind=='pr_links':refs=[('上游PR #1','https://github.com/jamtrott/csrspmv/pull/1'),('核心最终提交a566fd1','https://github.com/visibychen/csrspmv/commit/a566fd1fe68471f9360897f0a4c030c55e19a217'),('材料仓库提交历史','https://github.com/visibychen/spmv-course-materials/commits/main/')]
            for label,url in refs:
                p=d.add_paragraph();indent(p);link(p,label,url)
    outdir.mkdir(exist_ok=True,parents=True);out=outdir/'csrspmv实验报告.docx';d.save(out)
    manifest=dict(title=d.core_properties.title,date='2026-11-01 Asia/Shanghai',chapters=[t for n,t in headings if n==1],headings=headings,figures=figs,body_paragraphs=len(body),body_characters=sum(map(len,body)),source_batch=DATA['source_dir'],core_final_commit=DATA['final_code_commit'],pr='https://github.com/jamtrott/csrspmv/pull/1',font_policy=dict(chinese='宋体',latin='Times New Roman',body_pt=12,h1_pt=15,h2_pt=14,h3_pt=12,heading_bold=True,line_spacing=1.5,first_line_chars=2),runtime='The workspace dependency-loader tool and primary runtime bundle are unavailable. Existing Windows Python packages and native Microsoft Word export are used with installed SimSun and Times New Roman.')
    (H/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CREATED',out,'BODY',len(body),'FIGURES',len(figs))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);build(p.parse_args().output_dir)
