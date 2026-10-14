"""Verify the frozen dataset and integrate all official knowledge documents into the app."""
from pathlib import Path
import hashlib,json,shutil

root=Path(__file__).resolve().parents[1];dataset=root/'datasets/RainGuard_HK_Dataset';web=root/'hk-web'
docs=json.loads((dataset/'knowledge/documents.json').read_text(encoding='utf-8'))
pages=[json.loads(line) for line in (dataset/'knowledge/pdf_pages.jsonl').read_text(encoding='utf-8').splitlines()]
extension=root/'datasets/Extended_Weather_Dataset'
if (extension/'knowledge/documents.json').exists():
 docs.extend([{**d,'extension':True} for d in json.loads((extension/'knowledge/documents.json').read_text(encoding='utf-8'))])
 pages.extend(json.loads(line) for line in (extension/'knowledge/pdf_pages.jsonl').read_text(encoding='utf-8').splitlines())
elif len(json.loads((web/'data/knowledge.json').read_text(encoding='utf-8'))['documents'])>9:
 raise SystemExit('Download the extension first: python scripts/download_dataset.py --extended')
out=[]
for d in docs:
 source=extension if d.get('extension') else dataset
 raw=source/d['raw_path']
 if hashlib.sha256(raw.read_bytes()).hexdigest()!=d['sha256']:raise ValueError('Original checksum mismatch: '+d['document_id'])
 record={'id':d['document_id'],'title':d['title'],'publisher':d['publisher'],'url':d['url'],'importedAt':d['fetched_at_utc'],'sha256':d['sha256'],'tags':d['title'],'format':raw.suffix.lstrip('.')}
 if raw.suffix=='.pdf':
  record['rawOrigin']='verified_dataset_release'
  record['chunks']=[{'id':f'{d["document_id"]}-p{p["physical_pdf_page"]}-{i//650+1}','text':p['text'][i:i+900],'page':p['physical_pdf_page']} for p in pages if p['document_id']==d['document_id'] for i in range(0,len(p['text']),650) if p['text'][i:i+900].strip()]
 else:
  relative=f'data/knowledge/{d["document_id"]}.html';shutil.copyfile(raw,web/relative);record['rawFile']=relative
  text=(source/d['text_path']).read_text(encoding='utf-8')
  record['chunks']=[{'id':d['document_id']+'-1','text':text}] if len(text)<=2500 else [{'id':f'{d["document_id"]}-{i//650+1}','text':text[i:i+1100]} for i in range(0,len(text),650)]
 out.append(record)
(web/'data/knowledge.json').write_text(json.dumps({'documents':out,'method':'SHA-256 verified official HTML and PDF page text; no model-generated source material'},ensure_ascii=False),encoding='utf-8')
print('Integrated',len(out),'official sources;',sum(len(d['chunks']) for d in out),'chunks, with physical PDF page references.')
