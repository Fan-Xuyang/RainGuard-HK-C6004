"""Collect additional official climate stations and knowledge pages, with resumable provenance."""
from pathlib import Path
import sys,json,re,html,datetime,sqlite3,csv,hashlib,concurrent.futures
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'datasets'))
import collect_dataset as base
DEST=ROOT/'datasets/Extended_Weather_Dataset';DEST.mkdir(exist_ok=True)
baseline=ROOT/'datasets/RainGuard_HK_Dataset'
original=json.loads((baseline/'manifest.json').read_text(encoding='utf-8'))['entries']
existing={e['id'] for e in original if 'error' not in e}
manifest_file=DEST/'manifest.json'
saved=json.loads(manifest_file.read_text(encoding='utf-8'))['entries'] if manifest_file.exists() else []
entries={e['id']:e for e in saved}
run=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def collect(specs):
 pending=[s for s in specs if s[0] not in entries or 'error' in entries[s[0]]]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for entry in pool.map(lambda s:base.fetch(DEST,run,s),pending):
   entries[entry['id']]=entry
   base.write_json(manifest_file,{'entries':list(entries.values())})

collect([(f'catalog-{key}',url,'metadata','html',{'publisher':'DATA.GOV.HK / Hong Kong Observatory'}) for key,url in base.CATALOGS.items() if key!='rainfall'])
specs=[]
for e in list(entries.values()):
 if e['category']!='metadata' or 'error' in e:continue
 text=html.unescape((DEST/e['path']).read_text(encoding='utf-8'))
 for url in dict.fromkeys(re.findall(r'https://data\.weather\.gov\.hk/[^\s<>"\']+',text)):
  match=re.search(r'/csvfile/([^/]+)/ALL/daily_\1_(RH|MSLP)_ALL\.csv$',url)
  if match:station,var=match.groups()
  else:
   match=re.search(r'dataType=(CLMMAXT|CLMMINT|CLMTEMP)&rformat=csv&station=([A-Z0-9]+)$',url)
   if not match:continue
   var,station=match.groups();var=base.TEMP_CODES[var]
  sid=f'daily-{station}-{var}'
  if sid not in existing:specs.append((sid,url,'climate','csv',{'station':station,'variable':var,'unit':base.UNITS[var],'catalog_url':e['url'],'publisher':'香港天文台','update_frequency':'monthly'}))
collect(list({s[0]:s for s in specs}.values()))
# Each successful page becomes a cited document. Unavailable URLs remain reported failures.
knowledge=[
 ('landslip','山泥倾泻警告','https://www.hko.gov.hk/sc/wservice/warning/landslip.htm'),
 ('cyclone-precautions','热带气旋预防措施','https://www.hko.gov.hk/sc/informtc/precaution.htm'),
 ('coldhot','寒冷及酷热天气警告','https://www.hko.gov.hk/tc/wservice/warning/coldhot.htm'),
 ('hot-advisory','炎热天气特别提示','https://www.hko.gov.hk/tc/wservice/warning/hotwxadv.htm'),
 ('monsoon-guidance','强烈季候风信号','https://www.hko.gov.hk/tc/wservice/warning/smse.htm'),
 ('monsoon-publication','强烈季候风与季节风','https://www.hko.gov.hk/tc/publica/gen_pub/sms.htm'),
 ('warning-details','各类警告详细资料','https://www.hko.gov.hk/tc/wservice/warning/details.htm'),
 ('public-warning-service','公共天气服务与霜冻警告','https://www.hko.gov.hk/tc/wservice/tsheet/pubwx.htm'),
 ('cyclone-service','热带气旋警告服务','https://www.hko.gov.hk/tc/wservice/tsheet/tcwarn.htm'),
 ('cyclone-classification','热带气旋分类','https://www.hko.gov.hk/tc/informtc/class.htm'),
 ('cyclone-advisory','热带气旋警告下各部门安排','https://www.hko.gov.hk/tc/informtc/advisorye.htm'),
 ('cyclone-reference','三号及八号信号参考指标','https://www.hko.gov.hk/tc/informtc/tcsignal3_ref.htm'),
 ('uv-definition','紫外线指数定义','https://www.hko.gov.hk/tc/wxinfo/uvindex/wisuvindex.htm'),
 ('warning-legend','各类天气警告图示','https://www.hko.gov.hk/tc/wxinfo/dailywx/warnlegend.htm'),
]

collect([(sid,url,'knowledge','html',{'title':title,'publisher':'香港天文台'}) for sid,title,url in knowledge])
collect([('heat-stress-guide','https://www.labour.gov.hk/common/public/oh/Heat_Stress_GN_tc.pdf','knowledge','pdf',{'title':'预防工作时中暑指引','publisher':'劳工处','parent_url':'https://www.hko.gov.hk/tc/wservice/warning/coldhot.htm'})])
allrows=[];coverage=[]
for e in entries.values():
 if e['category']!='climate' or 'error' in e:continue
 rows=base.parse_climate(DEST,e);allrows.extend(rows)
 coverage.append({'source':e['id'],'station':e['station'],'variable':e['variable'],'rows':len(rows),'min_date':min(r['date'] for r in rows),'max_date':max(r['date'] for r in rows),'missing':sum(r['value'] is None for r in rows),'source_url':e['url'],'source_sha256':e['sha256']})
if not allrows:raise RuntimeError('No additional actual climate records collected')
base.write_csv(DEST/'climate_daily_extended.csv',allrows,list(allrows[0]))
base.write_csv(DEST/'coverage.csv',coverage,list(coverage[0]))
db=sqlite3.connect(DEST/'extended_weather.sqlite');db.execute('DROP TABLE IF EXISTS climate_daily')
fields=list(allrows[0]);db.execute('CREATE TABLE climate_daily ('+','.join('"'+k+'" '+('REAL' if k in ['value','is_trace','source_line'] else 'TEXT') for k in fields)+')')
db.executemany('INSERT INTO climate_daily VALUES('+','.join('?' for _ in fields)+')',[[r[k] for k in fields] for r in allrows]);db.execute('CREATE UNIQUE INDEX climate_key ON climate_daily(station,variable,date)');db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
docs=[];pdf_pages=[]
(DEST/'knowledge').mkdir(exist_ok=True)
for e in entries.values():
 if e['category']!='knowledge' or 'error' in e:continue
 if e['format']=='pdf':
  import fitz
  with fitz.open(DEST/e['path']) as pdf:
   texts=[page.get_text(sort=True) for page in pdf]
   pdf_pages.extend(dict(document_id=e['id'],physical_pdf_page=i+1,text=t,source_url=e['url'],source_sha256=e['sha256']) for i,t in enumerate(texts))
  extracted='\n'.join(texts)
 else:
  parser=base.TextExtractor();parser.feed((DEST/e['path']).read_text(encoding='utf-8-sig'));extracted=''.join(parser.parts)
 text='\n'.join(dict.fromkeys(re.sub(r'\s+',' ',line).strip() for line in extracted.splitlines() if len(line.strip())>8))
 if len(text)<150:e['extraction_error']='Insufficient readable text';continue
 path=f'knowledge/{e["id"]}.txt';(DEST/path).write_text(text,encoding='utf-8')
 docs.append({'document_id':e['id'],'title':e['title'],'publisher':e['publisher'],'url':e['url'],'raw_path':e['path'],'text_path':path,'fetched_at_utc':e['fetched_at_utc'],'sha256':e['sha256']})
base.write_json(DEST/'knowledge/documents.json',docs)
(DEST/'knowledge/pdf_pages.jsonl').write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in pdf_pages),encoding='utf-8')
for e in entries.values():
 if 'error' not in e:assert hashlib.sha256((DEST/e['path']).read_bytes()).hexdigest()==e['sha256']
base.write_json(manifest_file,{'entries':list(entries.values())})
summary={'additional_climate_rows':len(allrows),'additional_station_variable_series':len(coverage),'additional_weather_stations':len({r['station'] for r in allrows}),'combined_climate_rows':671724+len(allrows),'additional_knowledge_documents':len(docs),'combined_knowledge_documents':9+len(docs),'failed_sources':[e for e in entries.values() if 'error' in e or 'extraction_error' in e],'source_sha256_verified':True,'sqlite_integrity':'ok'}
base.write_json(DEST/'summary.json',summary)
base.write_json(ROOT/'hk-web/data/extended-catalog.json',{'summary':summary,'coverage':coverage,'knowledge':docs,'collected_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
(DEST/'README.md').write_text('''# 香港官方扩展气象数据\n\n本包是 v0.1.0 冻结数据的增量，不包含重复核心系列。按官方目录补充其他站点的日最高/最低/平均温度、平均湿度、平均气压。原文、来源 URL、HTTP 时间和 SHA-256 见 manifest.json；实际规模、失败来源见 summary.json。\n\n日数据仍按月发布。缺测保留 NULL/空白，没有补零或生成虚构观测。基线模型仍使用冻结三站雨量数据，没有偷偷更换测试集。新增知识文档为实际可用官方网页，失败页不作为已采集资料计数。\n\nCSV 一行=站点/变量/日期；变量、单位和质量字段与核心包 DATA_DICTIONARY.md 一致。SQLite 表 climate_daily 可按 station,variable,date 查询。与核心包合并前应使用唯一键去重；额外温湿压特征必须滞后并仅在训练集拟合预处理。\n''',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2),flush=True)
