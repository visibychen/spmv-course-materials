#!/usr/bin/env python3
"""Capture verbatim fixed-commit source/log text for browser screenshots."""
from pathlib import Path
import subprocess,json,hashlib,html
from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
H=Path(__file__).resolve().parent;M=H.parents[1];C=M.parent/'csrspmv'
def git(root,*args):return subprocess.check_output(['git',*args],cwd=root,text=True)
def source(ref,path):return git(C,'show',ref+':'+path).splitlines()
records=[]
def imagepage(name,title,subtitle,content,code=False,start=1):
    p=H/'assets'/f'{name}.html'
    if code:
        fmt=HtmlFormatter(nowrap=True,style='friendly')
        fragments=highlight(content,CLexer(),fmt).splitlines()
        assert len(fragments)==len(content.splitlines())
        body='<div class="source">'+''.join('<div class="code-row"><span class="line-num">'+str(start+i)+'</span><pre>'+line+'</pre></div>' for i,line in enumerate(fragments))+'</div>'
        css=fmt.get_style_defs('.source')+'''
.code-row{display:grid;grid-template-columns:56px minmax(0,1fr);background:#f3f3f3}
.line-num{font:18px/25px Consolas,monospace;color:#777;text-align:right;padding-right:14px}
.code-row pre{font:18px/25px Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;min-height:25px;margin:0;padding-left:12px;border-left:1px solid #ddd}
'''
    else:
        body='<pre>'+html.escape(content)+'</pre>';css=''
    p.write_text('''<!doctype html><meta charset="utf-8"><title>'''+html.escape(title)+'''</title>
<style>*{box-sizing:border-box}body{margin:0;width:1240px;background:white;color:#111;font-family:Arial,"SimSun",serif}
article{padding:20px 24px;border:1px solid #aaa}header{font:20px Arial,"SimSun",serif;margin:0 0 6px;font-weight:bold}
small{display:block;font:16px Arial,"SimSun",serif;color:#444;margin-bottom:15px}pre{font:19px/1.48 Consolas,"SimSun",monospace;margin:0;white-space:pre-wrap;overflow-wrap:normal}
.source pre{font:18px/1.38 Consolas,monospace;white-space:pre}table{border-collapse:collapse}td.linenos{padding-right:14px;color:#777;vertical-align:top}.source td.code{padding-left:10px;border-left:1px solid #ddd}
'''+css+'</style><article><header>'+html.escape(title)+'</header><small>'+html.escape(subtitle)+'</small>'+body+'</article>')
def capture(name,ref,path,a,b,title):
    lines=source(ref,path);text='\n'.join(lines[a-1:b])+'\n'
    imagepage(name,title,f'{path}   lines {a}-{b}   commit {ref[:8]}',text,True,a)
    (H/'assets'/f'{name}.txt').write_text(text)
    records.append(dict(name=name,commit=ref,path=path,lines=[a,b],sha256=hashlib.sha256(text.encode()).hexdigest(),kind='verbatim source excerpt'))
master='9352c865044f4c8b344d6fe5a277200a89f7a08b'
v2='9b652e8da85b7a1ad255e0b4f8ddadc5e0558f1a'
capture('fig1-1',master,'src/csr.c',1278,1300,'Original f32 CSR multiplication and OpenMP worksharing')
capture('fig1-2',master,'src/main.c',403,411,'Original outer OpenMP team and repeated SpMV calls')
capture('fig3-1',v2,'src/spmv_v2.c',139,166,'v2 backend and partition selection')
capture('fig3-2',v2,'src/spmv_v2.c',60,88,'v2 work cuts and stable merge-path search')
capture('fig3-3',v2,'src/spmv_v2.c',171,199,'v2 ordered direct rows and fixed-eight unrolling')
capture('fig3-4',v2,'src/spmv_v2.c',207,235,'v2 split-row fragments and delayed update')
for name,root,title,args in [
 ('fig7-1',C,'csrspmv — optimization commits across retained branches',
  ['log','--all','--author=visiby','--date=short','--pretty=format:%h  %ad  %s']),
 ('fig7-2',M,'spmv-course-materials — design and experiment commits',
  ['log','--date=short','--pretty=format:%h  %ad  %s','-18'])]:
    command='git '+' '.join(args)
    text=git(root,*args)+'\n'
    content='$ cd '+str(root)+'\n$ '+command+'\n\n'+text
    imagepage(name,title,'Verbatim Git output • captured 2026-11-01 • no history rewritten',content)
    (H/'assets'/f'{name}.txt').write_text(content)
    records.append(dict(name=name,repo=str(root),argv=['git',*args],output_sha256=hashlib.sha256(text.encode()).hexdigest(),kind='verbatim git output'))
(H/'figure-sources.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
p=M/'experiments/2026-10-26-v2'
s=json.loads((p/'summary.json').read_text());meta=json.loads((p/'matrices.json').read_text())
data=dict(summary=s,matrices=meta,decision=json.loads((p/'decision.json').read_text()),paired=json.loads((p/'paired-analysis.json').read_text()),environment=json.loads((p/'environment.json').read_text()),source_dir='experiments/2026-10-26-v2',source_material_commit='3bf5ff5f',final_code_commit=git(C,'rev-parse','HEAD').strip())
(H/'report-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('EXTRACTED',len(records),'SCREENSHOT SOURCES; REPORT DATA CAPTURED')
