"""Fetch official bilingual source documents; retain raw bytes and reproducible hashes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib, html, json, re, sys, urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'datasets'))
from collect_dataset import TextExtractor

WEB = ROOT / 'hk-web'
CATALOG = WEB / 'data/knowledge.json'


def collect(spec):
    sid, title, url, publisher, language, topics = spec
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'RainGuard-HK-C6004-Research/0.6'})
        with urllib.request.urlopen(req, timeout=35) as response:
            raw, final = response.read(), response.url
            if response.status != 200:
                raise ValueError('HTTP status')
        decoded = raw.decode('utf-8-sig')
        parser = TextExtractor(); parser.feed(decoded)
        text = '\n'.join(line for line in (re.sub(r'\s+', ' ', x).strip() for x in ''.join(parser.parts).splitlines()) if line)
        if len(text) < 350 or re.search(r'<title>[^<]*(404|not found|error)', decoded, re.I):
            raise ValueError('Not a usable source document')
        page_title = re.search(r'<title[^>]*>(.*?)</title>', decoded, re.S|re.I)
        if language=='en' and page_title:
            title=html.unescape(re.sub('<[^>]+>','',page_title[1])).split('｜')[0].strip()
        relative = 'data/knowledge/' + sid + '.html'
        (WEB / relative).write_bytes(raw)
        return {'id': sid, 'title': title, 'publisher': publisher, 'url': url, 'finalUrl': final,
                'importedAt': datetime.now(timezone.utc).isoformat(), 'sha256': hashlib.sha256(raw).hexdigest(),
                'rawFile': relative, 'language': language, 'topics': topics, 'format': 'html',
                'tags': ' '.join(topics), 'collection': 'official-bilingual-2026-10',
                'chunks': [{'id': f'{sid}-{i // 900 + 1}', 'text': text[i:i+1350]} for i in range(0,len(text),900)]}
    except Exception as error:
        return {'id': sid, 'url': url, 'error': type(error).__name__}


def main():
    kb = json.loads(CATALOG.read_text(encoding='utf-8'))
    specs = []
    for d in kb['documents']:
        if d.get('collection') or 'hko.gov.hk/' not in d['url']:
            continue
        topics = [t for key,t in [('rain','rainfall'),('flood','flooding'),('thunder','lightning'),('hot','heat'),('cyclone','typhoon'),('monsoon','wind'),('landslip','landslide')] if key in d['id']] or ['warnings']
        url = d['url'].replace('/sc/','/en/').replace('/tc/','/en/')
        specs.append((d['id']+'-en', d['title']+' · English', url, d['publisher'], 'en', topics))
    specs.extend([
        ('dsd-flood-en','Flood damage prevention','https://www.dsd.gov.hk/EN/Flood_Prevention/How_to_Reduce_Flood_Damage/index.html','渠务署','en',['flooding','facilities']),
        ('work-arrangements-en','Work arrangements in adverse weather','https://www.labour.gov.hk/eng/public/typhoon.htm','劳工处','en',['work','typhoon','rainfall']),
        ('hko-uv-en','UV Index and sun protection','https://www.hko.gov.hk/en/wxinfo/uvindex/wisuvindex.htm','香港天文台','en',['heat','outdoor']),
        ('hko-uv-zh','紫外线指数与防晒','https://www.hko.gov.hk/tc/wxinfo/uvindex/wisuvindex.htm','香港天文台','zh-Hant',['heat','outdoor']),
        ('hko-lightning-nowcast','Lightning nowcast and outdoor activities','https://www.hko.gov.hk/en/education/weather/meteorology-basics/00495-observe-the-observatory-to-prevent-lightning-strokes.html','香港天文台','en',['lightning','outdoor']),
        ('hko-convection-en','Squall and lightning in convective weather','https://www.hko.gov.hk/en/education/weather/thunderstorm-and-lightning/00763-Squall-and-Lightning-Associated-with-Severe-Convective-Weather.html','香港天文台','en',['lightning','wind','outdoor']),
        ('hko-rain-publication-en','Rainstorm warning signals','https://www.hko.gov.hk/en/publica/gen_pub/rain.htm','香港天文台','en',['rainfall','warnings']),
    ])
    results = list(ThreadPoolExecutor(max_workers=5).map(collect, specs))
    additions = [r for r in results if 'error' not in r]
    if not additions:
        raise RuntimeError('No verified official sources fetched; existing library unchanged')
    ids = {d['id'] for d in additions}
    kb['documents'] = [d for d in kb['documents'] if d['id'] not in ids] + additions
    for d in kb['documents']:
        d.setdefault('language', 'zh-Hant' if '/tc/' in d['url'] or '/TC/' in d['url'] else 'zh-Hans')
        d.setdefault('topics', [t for key,t in [('rain','rainfall'),('flood','flooding'),('thunder','lightning'),('hot','heat'),('heat','heat'),('cyclone','typhoon'),('work','work'),('landslip','landslide')] if key in d['id']] or ['warnings'])
    kb['updatedAt'] = datetime.now(timezone.utc).isoformat()
    kb['method'] = 'SHA-256 verified official HTML/PDF text, original source language preserved; bilingual retrieval uses explicit query synonyms.'
    CATALOG.write_text(json.dumps(kb,ensure_ascii=False),encoding='utf-8')
    report = {'collectedAt': kb['updatedAt'], 'successes': [{k:d[k] for k in ('id','url','sha256','importedAt','language')} for d in additions], 'failures':[r for r in results if 'error' in r]}
    (WEB/'data/knowledge-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'sources':len(kb['documents']), 'chunks':sum(len(d['chunks']) for d in kb['documents']), 'added':len(additions),'failed':len(report['failures'])}))


if __name__ == '__main__':
    main()
