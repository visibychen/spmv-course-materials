#!/usr/bin/env python3
"""Native Word export and PDF page rendering when packaged LibreOffice is absent."""
import argparse,json,hashlib,time,zipfile,re
from pathlib import Path
import fitz
from PIL import Image,ImageOps,ImageDraw
import win32com.client
import pythoncom
def main(docx,qa):
    qa.mkdir(exist_ok=True,parents=True)
    pdf=docx.with_suffix('.pdf')
    pythoncom.CoInitialize()
    app=win32com.client.DispatchEx('Word.Application')
    app.Visible=False;app.DisplayAlerts=0
    doc=None
    try:
        doc=app.Documents.Open(str(docx),ConfirmConversions=False,ReadOnly=False,AddToRecentFiles=False)
        doc.Fields.Update();doc.Repaginate();pages=doc.ComputeStatistics(2);doc.Save()
        doc.ExportAsFixedFormat(str(pdf),17,OpenAfterExport=False,OptimizeFor=0,DocStructureTags=True)
    finally:
        if doc is not None:doc.Close(False)
        app.Quit()
        pythoncom.CoUninitialize()
    book=fitz.open(pdf);records=[];thumbs=[]
    for i,page in enumerate(book):
        pix=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False)
        name=qa/f'page-{i+1:02}.png';pix.save(name)
        lines=page.get_text()
        fonts=sorted({span['font'] for block in page.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for span in line['spans']})
        records.append(dict(page=i+1,width=page.rect.width,height=page.rect.height,text_characters=len(lines),text=lines,fonts=fonts,images=len(page.get_images())))
        im=Image.open(name).convert('RGB');im.thumbnail((300,440))
        canvas=Image.new('RGB',(320,470),'#ddd');canvas.paste(im,((320-im.width)//2,10))
        ImageDraw.Draw(canvas).text((12,450),str(i+1),fill='black')
        thumbs.append(canvas)
    for start in range(0,len(thumbs),12):
        group=thumbs[start:start+12];contact=Image.new('RGB',(320*4,470*3),'white')
        for j,im in enumerate(group):contact.paste(im,((j%4)*320,(j//4)*470))
        contact.save(qa/f'contact-{start//12+1}.png')
    record=dict(renderer='Microsoft Word native PDF export; PyMuPDF PNG rendering',word_pages=pages,pdf_pages=len(book),docx_sha256=hashlib.sha256(docx.read_bytes()).hexdigest(),pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),pages=records)
    (qa/'render-audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('EXPORTED',pdf,'PAGES',len(book))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('docx',type=Path);p.add_argument('--qa',type=Path,required=True);a=p.parse_args();main(a.docx.resolve(),a.qa)
