"""RainGuard HK official-data collector. Python 3.10+, PyMuPDF for PDF knowledge.

Run: python collect_dataset.py [--live-only | --offline] [--output PATH]
Every acquisition is immutable in raw/<run-id>. No credentials required.
"""
import argparse
import concurrent.futures as futures
import csv
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import time
import urllib.request

CORE = ('HKO', 'LFS', 'SHA')
BASE = 'https://data.weather.gov.hk/weatherAPI/'
CATALOGS = {
    'rainfall': 'https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-total-rainfall',
    'temperature': 'https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-temperature-info-hko',
    'humidity': 'https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-mean-relative-humidity',
    'pressure': 'https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-mean-pressure',
}
LIVE = {
    'rain': (BASE+'opendata/hourlyRainfall.php?lang=tc', 'json', '15 minutes'),
    'weather': (BASE+'opendata/weather.php?dataType=rhrread&lang=tc', 'json', 'hourly / updates'),
    'warnings': (BASE+'opendata/weather.php?dataType=warnsum&lang=tc', 'json', 'on change'),
    'warningInfo': (BASE+'opendata/weather.php?dataType=warningInfo&lang=tc', 'json', 'on change'),
    'forecast': (BASE+'opendata/weather.php?dataType=fnd&lang=tc', 'json', 'twice daily / updates'),
    'local': (BASE+'opendata/weather.php?dataType=flw&lang=tc', 'json', 'hourly / updates'),
    'tips': (BASE+'opendata/weather.php?dataType=swt&lang=tc', 'json', 'on change'),
    'tides': (BASE+'hko_data/tide/ALL_en.csv', 'csv', '5 minutes'),
    'nowcast': (BASE+'hko_data/F3/Gridded_rainfall_nowcast.csv', 'csv', '12 minutes'),
}
DOCS = [
    ('rain-warning', '暴雨警告系统', '香港天文台', 'https://www.hko.gov.hk/sc/wservice/warning/rainstor.htm'),
    ('flood-prevention', '如何减少水浸损失', '渠务署', 'https://www.dsd.gov.hk/SC/Flood_Prevention/How_to_Reduce_Flood_Damage/index.html'),
    ('work-arrangements', '恶劣天气及极端情况工作安排', '劳工处', 'https://www.labour.gov.hk/tc/public/typhoon.htm'),
    ('local-rain', '局部地区大雨提示', '香港天文台', 'https://www.hko.gov.hk/tc/wservice/warning/lhvyrain.htm'),
    ('north-flood', '新界北部水浸特别报告', '香港天文台', 'https://www.hko.gov.hk/sc/wservice/warning/flood.htm'),
    ('storm-surge', '什么是风暴潮', '香港天文台', 'https://www.hko.gov.hk/sc/education/aviation-and-marine/marine/00168-what-is-a-storm-surge.html'),
    ('thunder', '雷暴警告', '香港天文台', 'https://www.hko.gov.hk/sc/wservice/warning/thunder.htm'),
]
UNITS = {'RF':'mm','MAXT':'degC','MINT':'degC','TEMP':'degC','RH':'percent','MSLP':'hPa'}
TEMP_CODES = {'CLMMAXT':'MAXT','CLMMINT':'MINT','CLMTEMP':'TEMP'}


def write_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def write_csv(p, rows, fields):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip=0; self.parts=[]
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','nav','header','footer'): self.skip+=1
        if tag in ('p','div','li','h1','h2','h3','br','tr'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style','nav','header','footer'): self.skip=max(0,self.skip-1)
        if tag in ('p','div','li','tr'): self.parts.append('\n')
    def handle_data(self, text):
        if not self.skip: self.parts.append(text)


def fetch(root, run, spec):
    sid,url,category,ext,meta=spec
    error=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'RainGuard-HK-C6004-Research/1.0'})
            with urllib.request.urlopen(req, timeout=45) as response:
                raw=response.read(); final_url=response.url; headers=dict(response.headers)
            if not raw: raise ValueError('empty response')
            if ext=='json': json.loads(raw.decode('utf-8-sig').lstrip('\ufeff'))
            if category=='climate' and ('<html' in raw[:500].decode('utf-8',errors='ignore').lower()):
                raise ValueError('HTML returned instead of climate data')
            path=Path('raw')/run/category/(sid+'.'+ext)
            (root/path).parent.mkdir(parents=True,exist_ok=True); (root/path).write_bytes(raw)
            result=dict(id=sid, url=url, final_url=final_url,
                category=category, format=ext, fetched_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                path=path.as_posix(), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                http_status=200, http_date=headers.get('Date'), last_modified=headers.get('Last-Modified'),
                content_type=headers.get('Content-Type'), **{'publisher':'Hong Kong Observatory',**meta})
            print('OK',sid,len(raw),flush=True)
            return result
        except Exception as e:
            error=f'{type(e).__name__}: {e}'
            if attempt<2: time.sleep(1+attempt)
    print('FAILED',sid,error,flush=True)
    return dict(id=sid,url=url,category=category,error=error,**meta)


def acquire(root,run,live_only):
    entries=[]
    if not live_only:
        specs=[('catalog-'+key,url,'metadata','html',{'catalog':key,'publisher':'DATA.GOV.HK / Hong Kong Observatory'}) for key,url in CATALOGS.items()]
        entries.extend(parallel_fetch(root,run,specs))
        specs=[]
        for item in entries:
            if 'error' in item: continue
            text=html.unescape((root/item['path']).read_text(encoding='utf-8'))
            links=list(dict.fromkeys(re.findall(r'https://data\.weather\.gov\.hk/[^\s<>"\']+',text)))
            for url in links:
                match=re.search(r'/csvfile/([^/]+)/ALL/daily_\1_([^/]+)_ALL\.csv$',url)
                if match:
                    station,var=match.groups()
                    if var!='RF' and station not in CORE: continue
                else:
                    match=re.search(r'dataType=(CLMMAXT|CLMMINT|CLMTEMP)&rformat=csv&station=(HKO|LFS|SHA)$',url)
                    if not match: continue
                    var,station=match.groups(); var=TEMP_CODES[var]
                specs.append((f'daily-{station}-{var}',url,'climate','csv',{'station':station,'variable':var,'unit':UNITS[var], 'catalog_url':item['url'],'update_frequency':'monthly'}))
        specs=list({s[0]:s for s in specs}.values())
        if not all(any(s[0]==f'daily-{c}-RF' for s in specs) for c in CORE):
            raise RuntimeError('Official catalog could not establish all three core rainfall sources')
        specs.extend((sid,url,'knowledge','html',{'title':title,'publisher':publisher}) for sid,title,publisher,url in DOCS)
        # Official attachments linked by the Labour Department's work-arrangements index.
        specs.extend([
            ('work-arrangements-code','https://www.labour.gov.hk/tc/public/pdf/wcp/Rainstorm.pdf','knowledge','pdf',{'title':'恶劣天气及「极端情况」下工作守则','publisher':'劳工处','parent_url':'https://www.labour.gov.hk/tc/public/typhoon.htm'}),
            ('work-arrangements-glance','https://www.labour.gov.hk/tc/public/wcp/Rainstorm_glance.pdf','knowledge','pdf',{'title':'恶劣天气及「极端情况」下工作安排一览','publisher':'劳工处','parent_url':'https://www.labour.gov.hk/tc/public/typhoon.htm'}),
        ])
        specs.extend([
            ('hko-open-data','https://www.hko.gov.hk/en/abouthko/opendata_intro.htm','metadata','html',{}),
            ('api-documentation',BASE+'doc/HKO_Open_Data_API_Documentation.pdf','metadata','pdf',{}),
            ('hko-publication-rights','https://www.hko.gov.hk/en/publica/iprightsnotice.htm','metadata','html',{}),
            ('data-gov-terms','https://data.gov.hk/en/terms-and-conditions','metadata','html',{'publisher':'DATA.GOV.HK'}),
        ])
        entries.extend(parallel_fetch(root,run,specs))
    entries.extend(parallel_fetch(root,run,[(key,url,'live',ext,{'update_frequency':frequency,'provisional':True}) for key,(url,ext,frequency) in LIVE.items()]))
    write_json(root/'manifests'/f'{run}.json',{'run_id':run,'entries':entries})
    return entries


def parallel_fetch(root,run,specs):
    with futures.ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda s:fetch(root,run,s),specs))


def parse_climate(root,entry):
    text=(root/entry['path']).read_bytes().decode('utf-8-sig').lstrip('\ufeff')
    lines=list(csv.reader(io.StringIO(text)))
    name=next((r[0] for r in lines if r and (' at ' in r[0] or ' at the ' in r[0])),entry['station'])
    rows=[]; malformed=[]
    for line_number,r in enumerate(lines,1):
        if not r or not r[0].strip().isdigit(): continue
        try:
            date=dt.date(*map(int,r[:3])).isoformat(); raw=r[3].strip()
        except (ValueError,IndexError):
            malformed.append(line_number); continue
        is_trace=raw.lower() in ('trace','t','微量')
        try: value=float(raw)
        except ValueError: value=None
        if value is not None and not math.isfinite(value): value=None
        completeness=r[4].strip() if len(r)>4 else ''
        status='trace' if is_trace else 'missing' if value is None else 'invalid_negative' if entry['variable']=='RF' and value<0 else 'numeric'
        if status=='invalid_negative': value=None
        rows.append(dict(station=entry['station'],station_name=name,variable=entry['variable'],date=date,
            value=value,unit=entry['unit'],raw_value=raw,completeness=completeness,is_trace=int(is_trace),
            quality_status=status,source_id=entry['id'],source_line=line_number,source_path=entry['path']))
    if not rows: raise ValueError(f'No dated observations in {entry["id"]}')
    entry['malformed_date_lines']=malformed
    return rows


def split_for(date):
    if date<'2000-01-01': return 'historical_before_2000'
    if date<'2020-01-01': return 'train'
    if date<'2023-01-01': return 'validation'
    if date<'2026-01-01': return 'test'
    return 'holdout_2026_onward'


def samples_for(rain,policy):
    # Target day d, features are observed on d-1 or earlier. Date-only seasonality is known in advance.
    data={r['date']:r for r in rain}; result=[]; exclusions={}
    for date in sorted(data):
        if date<'2000-01-01': continue
        d=dt.date.fromisoformat(date)
        window=[data.get((d-dt.timedelta(days=n)).isoformat()) for n in range(7,-1,-1)]
        if any(r is None for r in window): reason='calendar_gap'
        elif any(r['completeness']!='C' for r in window): reason='incomplete_flag'
        elif any(r['value'] is None and not r['is_trace'] for r in window): reason='missing_value'
        elif policy=='exclude' and any(r['is_trace'] for r in window): reason='trace_excluded'
        else: reason=None
        if reason: exclusions[reason]=exclusions.get(reason,0)+1; continue
        v=[0.0 if r['is_trace'] else r['value'] for r in window]; past=v[:-1]
        angle=d.timetuple().tm_yday/365.25*2*math.pi
        result.append(dict(station=window[-1]['station'],target_date=date,
            feature_asof_date=(d-dt.timedelta(days=1)).isoformat(),split=split_for(date),trace_policy=policy,
            log1p_lag1=math.log1p(past[-1]),log1p_lag2=math.log1p(past[-2]),log1p_lag3=math.log1p(past[-3]),
            log1p_past7_total=math.log1p(sum(past)),past7_wetdays=sum(v>=1 for v in past),
            sin_dayofyear=math.sin(angle),cos_dayofyear=math.cos(angle),
            lag1_rainfall_mm=past[-1],target_rainfall_mm=v[-1],target_ge25mm=int(v[-1]>=25),
            target_source_path=window[-1]['source_path'],target_source_line=window[-1]['source_line']))
    return result,exclusions


def prepare(root,entries):
    good=[e for e in entries if 'error' not in e]; by_id={e['id']:e for e in good}
    allrows=[]; quality=[]; stations=[]
    for e in good:
        if e['category']!='climate': continue
        rows=parse_climate(root,e); allrows.extend(rows)
        dates=[r['date'] for r in rows]; counts={k:sum(r['quality_status']==k for r in rows) for k in ('numeric','missing','trace','invalid_negative')}
        quality.append(dict(source_id=e['id'],station=e['station'],variable=e['variable'],rows=len(rows),
            min_date=min(dates),max_date=max(dates),duplicate_dates=len(dates)-len(set(dates)),
            incomplete=sum(r['completeness']!='C' for r in rows),malformed_dates=len(e['malformed_date_lines']),**counts))
        if e['variable']=='RF': stations.append(dict(station=e['station'],name=rows[0]['station_name'],core=int(e['station'] in CORE),source_url=e['url'],start_date=min(dates),end_date=max(dates),records=len(rows)))
    allrows.sort(key=lambda r:(r['station'],r['variable'],r['date']))
    fields=list(allrows[0])
    write_csv(root/'processed/climate_daily_all.csv',allrows,fields)
    rain=[r for r in allrows if r['variable']=='RF']
    write_csv(root/'processed/rainfall_all_stations.csv',rain,fields)
    write_csv(root/'processed/stations.csv',stations,list(stations[0]))
    write_csv(root/'quality/source_coverage.csv',quality,list(quality[0]))
    core=[r for r in rain if r['station'] in CORE and r['date']>='2000-01-01']
    write_csv(root/'processed/rainfall_core_2000_onward.csv',core,fields)
    # Optional meteorological features retain missing values; no global filling or interpolation.
    lookup={(r['station'],r['date'],r['variable']):r for r in allrows}
    joined=[]
    for r in core:
        row=dict(r)
        for var in ('MAXT','MINT','TEMP','RH','MSLP'):
            other=lookup.get((r['station'],r['date'],var))
            row[var+'_value']=other['value'] if other and other['completeness']=='C' else None
            row[var+'_raw']=other['raw_value'] if other else None
            row[var+'_completeness']=other['completeness'] if other else None
        joined.append(row)
    write_csv(root/'processed/core_daily_weather.csv',joined,list(joined[0]))
    cases=sorted([r for r in core if r['quality_status']=='numeric' and r['completeness']=='C'],key=lambda r:r['value'],reverse=True)[:50]
    write_csv(root/'processed/top50_observed_rainfall_days.csv',cases,fields)
    feature_rows=[]; split_counts=[]; exclusion_counts=[]
    for policy in ('exclude','zero'):
        core_samples=[]; extension=[]
        for station in sorted({r['station'] for r in rain}):
            rows,excluded=samples_for([r for r in rain if r['station']==station],policy)
            (core_samples if station in CORE else extension).extend(rows)
            for reason,count in excluded.items(): exclusion_counts.append(dict(station=station,trace_policy=policy,reason=reason,count=count))
            for split in ('train','validation','test','holdout_2026_onward'):
                subset=[r for r in rows if r['split']==split]
                split_counts.append(dict(station=station,core=int(station in CORE),trace_policy=policy,split=split,
                    samples=len(subset),positives=sum(r['target_ge25mm'] for r in subset),
                    min_date=min((r['target_date'] for r in subset),default=''),max_date=max((r['target_date'] for r in subset),default='')))
        assert core_samples
        feature_rows.extend(core_samples)
        write_csv(root/f'training/core_features_trace_{policy}.csv',core_samples,list(core_samples[0]))
        if extension: write_csv(root/f'training/extension_features_trace_{policy}.csv',extension,list(extension[0]))
        for split in ('train','validation','test','holdout_2026_onward'):
            write_csv(root/f'training/trace_{policy}/{split}.csv',[r for r in core_samples if r['split']==split],list(core_samples[0]))
    write_csv(root/'quality/split_counts.csv',split_counts,list(split_counts[0]))
    write_csv(root/'quality/exclusions.csv',exclusion_counts,['station','trace_policy','reason','count'])
    # Save source text without machine translation to preserve exact wording for citation.
    documents=[]; chunks=[]; pdf_pages=[]
    for e in good:
        if e['category']!='knowledge': continue
        if e['format']=='pdf':
            try: import fitz
            except ImportError as error: raise RuntimeError('PDF knowledge extraction requires: python -m pip install PyMuPDF') from error
            with fitz.open(root/e['path']) as pdf:
                pages=[page.get_text(sort=True) for page in pdf]
                extracted='\n'.join(pages)
                e['pdf_pages']=len(pdf)
                pdf_pages.extend(dict(document_id=e['id'],physical_pdf_page=i+1,text=text,
                    source_url=e['url'],source_sha256=e['sha256']) for i,text in enumerate(pages))
        else:
            parser=TextExtractor(); parser.feed((root/e['path']).read_bytes().decode('utf-8-sig',errors='replace'))
            extracted=''.join(parser.parts)
        lines=[re.sub(r'\s+',' ',line).strip() for line in extracted.splitlines()]
        text='\n'.join(dict.fromkeys(line for line in lines if len(line)>8))
        if len(text)<100: raise ValueError(f'No readable knowledge text: {e["id"]}')
        path=f'knowledge/{e["id"]}.txt'; (root/path).parent.mkdir(exist_ok=True); (root/path).write_text(text,encoding='utf-8')
        doc=dict(document_id=e['id'],title=e['title'],publisher=e['publisher'],url=e['url'],
            raw_path=e['path'],text_path=path,fetched_at_utc=e['fetched_at_utc'],sha256=e['sha256'])
        documents.append(doc)
        for start in range(0,len(text),650):
            chunks.append(dict(chunk_id=f'{e["id"]}-{start//650+1}',document_id=e['id'],
                start_char=start,end_char=min(start+900,len(text)),text=text[start:start+900],source_url=e['url'],source_sha256=e['sha256']))
    write_json(root/'knowledge/documents.json',documents)
    (root/'knowledge/chunks.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in chunks),encoding='utf-8')
    (root/'knowledge/pdf_pages.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in pdf_pages),encoding='utf-8')
    live=[]
    for e in good:
        if e['category']!='live': continue
        raw=(root/e['path']).read_bytes().decode('utf-8-sig').lstrip('\ufeff')
        live.append(dict(source_id=e['id'],source_url=e['url'],raw_path=e['path'],fetched_at_utc=e['fetched_at_utc'],
            format=e['format'],payload=json.loads(raw) if e['format']=='json' else raw))
    write_json(root/'realtime/latest_snapshot.json',live)
    payloads={e['source_id']:e['payload'] for e in live}
    rain_packet=payloads.get('rain',{})
    station_obs=[dict(observation_time=rain_packet.get('obsTime'),**r) for r in rain_packet.get('hourlyRainfall',[])]
    if station_obs: write_csv(root/'realtime/station_hourly_rainfall.csv',station_obs,list(station_obs[0]))
    district_packet=payloads.get('weather',{}).get('rainfall',{})
    district_obs=[dict(start_time=district_packet.get('startTime'),end_time=district_packet.get('endTime'),**r) for r in district_packet.get('data',[])]
    if district_obs: write_csv(root/'realtime/district_rainfall.csv',district_obs,list(dict.fromkeys(k for r in district_obs for k in r)))
    for sid in ('tides','nowcast'):
        if sid in payloads:
            rows=list(csv.DictReader(io.StringIO(payloads[sid])))
            if rows: write_csv(root/f'realtime/{sid}.csv',rows,list(rows[0]))
    current_hk=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    readiness=[]
    for station in CORE:
        dates={r['date']:r for r in core if r['station']==station}
        required=[(current_hk-dt.timedelta(days=n)).isoformat() for n in range(7,0,-1)]
        unavailable=[date for date in required if date not in dates or dates[date]['completeness']!='C' or dates[date]['value'] is None]
        readiness.append(dict(station=station,checked_on_hk_date=current_hk.isoformat(),latest_historical_date=max(dates),
            ready_for_current_daily_model=not unavailable,missing_or_unusable_dates=unavailable,
            note='Official monthly climate series is not a real-time daily feed. Do not fill missing recent days with zero or reuse August as current input.'))
    write_json(root/'quality/current_inference_readiness.json',readiness)
    # Compatibility exports for the existing prototype; copying into the app is a separate action.
    history={}
    for station in CORE:
        source=by_id[f'daily-{station}-RF']; records=[r for r in core if r['station']==station]
        history[station]={'name':records[0]['station_name'],'source':source['url'],
            'receivedAt':source['fetched_at_utc'],'sha256':source['sha256'],'rawFile':source['path'],
            'records':[{'date':r['date'],'value':r['value'],'raw':r['raw_value'],'complete':r['completeness']} for r in records]}
    write_json(root/'application/history.json',history)
    packets={e['id']:{'data':next(x['payload'] for x in live if x['source_id']==e['id']),
        'receivedAt':e['fetched_at_utc'],'source':e['url'],'rawFile':e['path'],'sha256':e['sha256']} for e in good if e['category']=='live'}
    write_json(root/'application/snapshot-raw.json',packets)
    write_json(root/'application/knowledge.json',{'documents':[{**d,'id':d['document_id'],
        'importedAt':d['fetched_at_utc'],'rawFile':d['raw_path'],'textFile':d['text_path'],
        'chunks':[{'id':c['chunk_id'],'text':c['text']} for c in chunks if c['document_id']==d['document_id']]} for d in documents]})
    db=root/'rainguard_hk.sqlite'
    con=sqlite3.connect(db)
    def table(name,rows):
        con.execute(f'DROP TABLE IF EXISTS {name}')
        if not rows:return
        fields=list(rows[0]); numeric={k for k in fields if any(isinstance(r.get(k),(int,float)) for r in rows)}
        con.execute(f'CREATE TABLE {name} ('+', '.join('"'+k+'" '+('REAL' if k in numeric else 'TEXT') for k in fields)+')')
        con.executemany(f'INSERT INTO {name} VALUES ('+','.join('?' for _ in fields)+')',
            [[json.dumps(r.get(k),ensure_ascii=False) if isinstance(r.get(k),(dict,list)) else r.get(k) for k in fields] for r in rows])
    table('climate_daily',allrows);table('core_features',feature_rows);table('knowledge_documents',documents)
    table('knowledge_chunks',chunks);table('realtime_snapshots',live)
    table('source_manifest',[{k:e.get(k) for k in ('id','url','publisher','category','path','sha256','fetched_at_utc','bytes')} for e in good])
    con.execute('CREATE UNIQUE INDEX climate_key ON climate_daily(station,variable,date)')
    con.execute('CREATE UNIQUE INDEX feature_key ON core_features(station,target_date,trace_policy)')
    con.commit();con.close()
    summary=dict(rainfall_stations=len(stations),climate_rows=len(allrows),rainfall_rows=len(rain),core_rainfall_rows=len(core),
        core_features_exclude=sum(r['trace_policy']=='exclude' for r in feature_rows),core_features_zero=sum(r['trace_policy']=='zero' for r in feature_rows),
        knowledge_documents=len(documents),knowledge_chunks=len(chunks),realtime_sources=len(live),
        failed_sources=[e for e in entries if 'error' in e],coverage=quality)
    write_json(root/'quality/summary.json',summary)
    # Update derived parsing metadata without claiming a new acquisition time.
    write_json(root/'manifest.json',{'prepared_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'entries':entries})
    print(json.dumps({k:v for k,v in summary.items() if k!='coverage'},ensure_ascii=True,indent=2),flush=True)
    return summary


def verify(root):
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for e in manifest['entries']:
        if 'error' in e: continue
        assert hashlib.sha256((root/e['path']).read_bytes()).hexdigest()==e['sha256'],e['id']
    con=sqlite3.connect(root/'rainguard_hk.sqlite')
    assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    for policy in ('exclude','zero'):
        for station in CORE:
            assert con.execute('SELECT count(*) FROM core_features WHERE station=? AND trace_policy=? AND split="test"',(station,policy)).fetchone()[0]>0
    assert con.execute('SELECT count(*) FROM core_features WHERE feature_asof_date>=target_date').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM core_features WHERE split="train" AND target_date>="2020-01-01"').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM core_features WHERE split="test" AND (target_date<"2023-01-01" OR target_date>="2026-01-01")').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM climate_daily WHERE variable="RF" AND value<0').fetchone()[0]==0
    con.row_factory=sqlite3.Row
    checked=0
    for station in CORE:
        for policy in ('exclude','zero'):
            for split in ('train','validation','test','holdout_2026_onward'):
                count=con.execute('SELECT count(*) FROM core_features WHERE station=? AND trace_policy=? AND split=?',(station,policy,split)).fetchone()[0]
                for offset in sorted({0,count//2,count-1}):
                    if offset<0: continue
                    row=con.execute('SELECT * FROM core_features WHERE station=? AND trace_policy=? AND split=? ORDER BY target_date LIMIT 1 OFFSET ?',(station,policy,split,offset)).fetchone()
                    d=dt.date.fromisoformat(row['target_date'])
                    obs=con.execute('SELECT date,value,is_trace,completeness FROM climate_daily WHERE station=? AND variable="RF" AND date BETWEEN ? AND ? ORDER BY date',(station,(d-dt.timedelta(days=7)).isoformat(),row['target_date'])).fetchall()
                    assert len(obs)==8 and all(r['completeness']=='C' for r in obs)
                    values=[0.0 if r['is_trace'] else r['value'] for r in obs]
                    assert policy!='exclude' or not any(r['is_trace'] for r in obs)
                    assert math.isclose(row['log1p_lag1'],math.log1p(values[-2]))
                    assert math.isclose(row['log1p_past7_total'],math.log1p(sum(values[:-1])))
                    assert row['past7_wetdays']==sum(v>=1 for v in values[:-1])
                    assert row['target_ge25mm']==int(values[-1]>=25)
                    checked+=1
    checks={'raw_sha256':'pass','sqlite_integrity':'pass','unique_climate_keys':'pass','temporal_feature_order':'pass','fixed_splits':'pass',
        'core_test_available_both_trace_policies':'pass','rainfall_nonnegative_or_missing':'pass',
        'source_to_feature_numeric_checks':checked,'source_to_feature_numeric_result':'pass'}
    con.close();write_json(root/'quality/verification.json',checks)
    print('VERIFY PASS',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'RainGuard_HK_Dataset')
    p.add_argument('--live-only',action='store_true');p.add_argument('--offline',action='store_true')
    args=p.parse_args(); root=args.output; root.mkdir(parents=True,exist_ok=True)
    if args.offline: entries=json.loads((root/'manifest.json').read_text(encoding='utf-8'))['entries']
    else:
        run=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        entries=acquire(root,run,args.live_only)
        if args.live_only:
            previous=json.loads((root/'manifest.json').read_text(encoding='utf-8'))['entries']
            old={e['id']:e for e in previous}; old.update({e['id']:e for e in entries}); entries=list(old.values())
    prepare(root,entries);verify(root)


if __name__=='__main__':main()
