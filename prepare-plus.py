import json,hashlib,datetime,pathlib,urllib.request,re
from html.parser import HTMLParser
from opencc import OpenCC
root=pathlib.Path(__file__).parent; web=root/'hk-web'; cc=OpenCC('t2s')
mapping={chr(i):cc.convert(chr(i)) for i in range(0x3400,0xa000) if cc.convert(chr(i))!=chr(i)}
(web/'simplify.mjs').write_text('const MAP='+json.dumps(mapping,ensure_ascii=False)+';\nexport const toSimple=s=>String(s??\'\').replace(/[\\u3400-\\u9fff]/g,c=>MAP[c]||c);\nexport function simplifyPage(){if(typeof MutationObserver===\'undefined\')return;const run=n=>{if(n.nodeType===3&&!n.parentElement?.closest(\'script,style,textarea,[data-original]\')){const s=toSimple(n.nodeValue);if(s!==n.nodeValue)n.nodeValue=s}else if(n.nodeType===1&&!n.matches(\'script,style,textarea,[data-original]\')){for(const a of [\'placeholder\',\'title\',\'aria-label\'])if(n.hasAttribute(a))n.setAttribute(a,toSimple(n.getAttribute(a)));n.childNodes.forEach(run)}};run(document.body);new MutationObserver(ms=>ms.forEach(m=>m.type===\'characterData\'?run(m.target):m.addedNodes.forEach(run))).observe(document.body,{childList:true,subtree:true,characterData:true});}\n',encoding='utf-8')
docs=[
 ('rain-warning','暴雨警告系统','香港天文台','https://www.hko.gov.hk/sc/wservice/warning/rainstor.htm','暴雨 黄雨 红雨 黑雨 停工 出行'),
 ('flood-prevention','如何减少水浸损失','渠务署','https://www.dsd.gov.hk/SC/Flood_Prevention/How_to_Reduce_Flood_Damage/index.html','水浸 排水 防洪 物业 巡查'),
 ('work-arrangements','恶劣天气及极端情况工作安排','劳工处','https://www.labour.gov.hk/tc/public/typhoon.htm','工作 停工 复工 雇员 台风'),
 ('local-rain','局部地区大雨提示','香港天文台','https://www.hko.gov.hk/tc/wservice/warning/lhvyrain.htm','局部 地区 大雨 暴雨'),
 ('north-flood','新界北部水浸特别报告','香港天文台','https://www.hko.gov.hk/sc/wservice/warning/flood.htm','北区 元朗 水浸 河道'),
 ('storm-surge','什么是风暴潮','香港天文台','https://www.hko.gov.hk/sc/education/aviation-and-marine/marine/00168-what-is-a-storm-surge.html','沿岸 潮位 风暴潮 台风 大澳'),
 ('thunder','雷暴警告','香港天文台','https://www.hko.gov.hk/sc/wservice/warning/thunder.htm','雷暴 闪电 户外 安全')]
class Extract(HTMLParser):
 def __init__(self): super().__init__();self.skip=0;self.parts=[]
 def handle_starttag(self,t,a):
  if t in ('script','style','nav','header','footer'):self.skip+=1
  if t in ('p','div','li','h1','h2','h3','br'):self.parts.append('\n')
 def handle_endtag(self,t):
  if t in ('script','style','nav','header','footer'):self.skip=max(0,self.skip-1)
  if t in ('p','div','li'):self.parts.append('\n')
 def handle_data(self,s):
  if not self.skip:self.parts.append(s)
out=[]; dest=web/'data/knowledge';dest.mkdir(exist_ok=True)
for id,title,publisher,url,tags in docs:
 try:
  raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RainGuard-C6004/1.0'}),timeout=25).read(); text=raw.decode('utf-8',errors='replace'); parser=Extract();parser.feed(text)
  lines=[re.sub(r'\s+',' ',x).strip() for x in ''.join(parser.parts).splitlines()]; lines=list(dict.fromkeys(x for x in lines if len(re.findall('[\u3400-\u9fff]',x))>=8))
  cleaned=cc.convert('\n'.join(lines));
  if len(cleaned)<100:raise ValueError('not enough readable text')
  (dest/(id+'.html')).write_bytes(raw);(dest/(id+'.txt')).write_text(cleaned,encoding='utf-8')
  chunks=[{'id':id+'-'+str(i//550+1),'text':cleaned[i:i+800]} for i in range(0,len(cleaned),550)]
  out.append(dict(id=id,title=title,publisher=publisher,url=url,tags=tags,importedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest(),rawFile='data/knowledge/'+id+'.html',textFile='data/knowledge/'+id+'.txt',chunks=chunks))
  print(id,len(chunks),'chunks')
 except Exception as e:print(id,'IMPORT FAILED',type(e).__name__)
(web/'data/knowledge.json').write_text(json.dumps({'documents':out,'method':'官方网页原文提取、简体转换与分块；网页内容不作为系统指令','importedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()},ensure_ascii=False),encoding='utf-8')
if len(out)<4:raise SystemExit('Too few verified documents')
