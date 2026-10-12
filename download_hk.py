"""Fetch actual HKO data, keep exact source bytes and SHA256 evidence."""
import pathlib,urllib.request,concurrent.futures,json,datetime,hashlib,csv,io
ROOT=pathlib.Path(__file__).parent/'hk-web';DATA=ROOT/'data';RAW=DATA/'raw';RAW.mkdir(parents=True,exist_ok=True)
BASE='https://data.weather.gov.hk/weatherAPI/'
URLS={
 'rain':BASE+'opendata/hourlyRainfall.php?lang=tc','weather':BASE+'opendata/weather.php?dataType=rhrread&lang=tc','warnings':BASE+'opendata/weather.php?dataType=warnsum&lang=tc','warningInfo':BASE+'opendata/weather.php?dataType=warningInfo&lang=tc','forecast':BASE+'opendata/weather.php?dataType=fnd&lang=tc','local':BASE+'opendata/weather.php?dataType=flw&lang=tc','tides':BASE+'hko_data/tide/ALL_en.csv','nowcast':BASE+'hko_data/F3/Gridded_rainfall_nowcast.csv'}
def get(key,url):
    with urllib.request.urlopen(url,timeout=90) as r:raw=r.read();cors=r.headers.get('Access-Control-Allow-Origin')
    ext='csv' if key in ['tides','nowcast'] or key.startswith('daily-') else 'json';filename=key+'.'+ext;(RAW/filename).write_bytes(raw)
    text=raw.decode('utf-8-sig');payload=json.loads(text) if ext=='json' else text
    return key,{'data':payload,'receivedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':url,'rawFile':'data/raw/'+filename,'sha256':hashlib.sha256(raw).hexdigest(),'cors':cors}
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as p:packets=dict(p.map(lambda kv:get(*kv),URLS.items()))
    (DATA/'snapshot-raw.json').write_text(json.dumps(packets,ensure_ascii=False),encoding='utf8')
    history={}
    for code,name in [('HKO','香港天文台'),('LFS','流浮山'),('SHA','沙田')]:
        url=BASE+f'cis/csvfile/{code}/ALL/daily_{code}_RF_ALL.csv';_,packet=get('daily-'+code,url);rows=[]
        for r in csv.reader(io.StringIO(packet['data'])):
            if len(r)<5 or not r[0].isdigit() or not 2000<=int(r[0])<=2026:continue
            try:date=datetime.date(*map(int,r[:3])).isoformat()
            except ValueError:continue
            try:value=float(r[3])
            except ValueError:value=None
            rows.append({'date':date,'value':value,'raw':r[3],'complete':r[4]})
        history[code]={'name':name,'records':rows,'source':url,'receivedAt':packet['receivedAt'],'sha256':packet['sha256'],'rawFile':packet['rawFile']}
    (DATA/'history.json').write_text(json.dumps(history,ensure_ascii=False),encoding='utf8')
    (ROOT/'vendor').mkdir(exist_ok=True)
    for name in ['leaflet.js','leaflet.css']:
        (ROOT/'vendor'/name).write_bytes(urllib.request.urlopen('https://unpkg.com/leaflet@1.9.4/dist/'+name,timeout=40).read())
    (ROOT/'vendor'/'LEAFLET-LICENSE.txt').write_bytes(urllib.request.urlopen('https://unpkg.com/leaflet@1.9.4/LICENSE',timeout=40).read())
    print(json.dumps({'sources':list(packets),'history':{k:len(v['records']) for k,v in history.items()}},ensure_ascii=False))
