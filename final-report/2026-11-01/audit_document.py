#!/usr/bin/env python3
"""Audit report typography, figure numbering and archived numeric values."""
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
import json,re,hashlib
from docx import Document
from docx.oxml.ns import qn
from lxml import etree
import fitz
H=Path(__file__).resolve().parent
OUT=Path(r'D:\Users\Nova\Desktop\计算机组成原理课设\实验报告')
DOCX=OUT/'csrspmv实验报告.docx';PDF=DOCX.with_suffix('.pdf')
blocks=json.loads((H/'report-content.json').read_text(encoding='utf-8'))
m=json.loads((H/'report-manifest.json').read_text(encoding='utf-8'))
d=Document(DOCX)
def effective(p,key):
    v=getattr(p.paragraph_format,key)
    st=p.style
    while v is None and st is not None:
        v=getattr(st.paragraph_format,key);st=st.base_style
    return v
def runcheck(run,size,bold):
    resolved=run.font.size;sty=run._parent.style
    while resolved is None and sty is not None:
        resolved=sty.font.size;sty=sty.base_style
    assert resolved is not None and resolved.pt==size,(run.text,resolved,size)
    chain=[];st=run._parent.style
    while st is not None:chain.append(st);st=st.base_style
    fonts={}
    for st in reversed(chain):
        if st.element.rPr is not None and st.element.rPr.rFonts is not None:
            fonts.update(st.element.rPr.rFonts.attrib)
    if run._r.rPr is not None and run._r.rPr.rFonts is not None:
        fonts.update(run._r.rPr.rFonts.attrib)
    assert fonts.get(qn('w:ascii'))=='Times New Roman'
    assert fonts.get(qn('w:hAnsi'))=='Times New Roman'
    assert fonts.get(qn('w:eastAsia')) in ['宋体','SimSun']
    if bold:assert (run.bold if run.bold is not None else run._parent.style.font.bold) is True
index={p.text:p for p in d.paragraphs}
body=[b for b in blocks if b['type']=='body']
headings=[b for b in blocks if b['type']=='heading']
for b in body:
    p=index[b['text']]
    assert p._p.pPr.ind.get(qn('w:firstLineChars'))=='200'
    assert effective(p,'line_spacing')==1.5
    for run in p.runs:
        if run.text:runcheck(run,12,False)
for b in headings:
    p=index[b['text']];n=b['level']
    assert p.style.name=='Heading '+str(n)
    assert effective(p,'line_spacing')==1.5
    for run in p.runs:
        if run.text:runcheck(run,{1:15,2:14,3:12}[n],True)
captions=[p.text for p in d.paragraphs if p.style.name=='Caption']
expected=[f"图{b['number']} {b['caption']}" for b in blocks if b['type']=='figure']
assert captions==expected,(captions,expected)
for sec in [1,3,5,7]:
    nums=[int(re.match(r'图(\d+)-(\d+)',x)[2]) for x in captions if x.startswith('图'+str(sec)+'-')]
    assert nums==list(range(1,len(nums)+1))
assert len(d.inline_shapes)==len(captions)==12
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with ZipFile(DOCX) as z:
    root=etree.fromstring(z.read('word/document.xml'));styles=etree.fromstring(z.read('word/styles.xml'))
    assert not root.xpath('//w:pBdr',namespaces=ns)
    assert not styles.xpath('//w:pBdr',namespaces=ns)
    assert not root.xpath('//w:ins|//w:del',namespaces=ns)
    hyperlinks=etree.fromstring(z.read('word/_rels/document.xml.rels'))
    targets=[x.get('Target') for x in hyperlinks if x.get('Type','').endswith('/hyperlink')]
    assert 'https://github.com/jamtrott/csrspmv/pull/1' in targets
for tb in d.tables:
    for row in tb.rows:
        for cell in row.cells:
            for p in cell.paragraphs:assert effective(p,'line_spacing')==1.5
charts=json.loads((H/'chart-data.json').read_text(encoding='utf-8'))
source=json.loads((H/'report-data.json').read_text(encoding='utf-8'))['summary']
for group in charts:
    for row in group['values']:assert row in source
book=fitz.open(PDF);fonts=set();caption_pages={}
for page in book:
    pd=page.get_text('dict')
    for block in pd['blocks']:
        if 'lines' not in block:continue
        for line in block['lines']:
            for span in line['spans']:
                fonts.add(span['font'])
                box=fitz.Rect(span['bbox'])
                assert box.x0>=0 and box.y0>=0 and box.x1<=page.rect.width+.2 and box.y1<=page.rect.height+.2
    compact=re.sub(r'\s+','',page.get_text())
    for cap in captions:
        if re.sub(r'\s+','',cap) in compact:
            assert page.get_images(),cap
            caption_pages[cap]=page.number+1
assert len(caption_pages)==12,caption_pages
assert all('TimesNewRoman' in n or n=='SimSun' for n in fonts),fonts
result=dict(passed=True,pages=len(book),body_paragraphs_checked=len(body),headings_checked=len(headings),figures_checked=len(captions),chapter_count=7,paragraph_indent_characters=2,line_spacing=1.5,font_sizes_pt={'body':12,'h1':15,'h2':14,'h3':12},chinese_font='宋体',latin_font='Times New Roman',headings_bold=True,blue_rules_removed=True,caption_pages=caption_pages,pdf_fonts=sorted(fonts),chart_rows_verified=sum(len(x['values']) for x in charts),all_figures_have_images_on_caption_page=True,tracked_changes=False,docx_sha256=hashlib.sha256(DOCX.read_bytes()).hexdigest(),pdf_sha256=hashlib.sha256(PDF.read_bytes()).hexdigest())
(H/'document-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='caption_pages'},ensure_ascii=False,indent=2))
