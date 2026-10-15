const {toSimple}=require('./simplify');
const CONCEPTS=[['暴雨','大雨','落大雨','rainstorm','rainfall','heavy rain'],['水浸','浸水','排水','flood','flooding','drainage'],['台风','打风','热带气旋','typhoon','cyclone'],['雷暴','闪电','行雷','lightning','thunderstorm'],['酷热','中暑','好热','heat','hot weather','heatstroke'],['风暴潮','storm surge'],['山泥倾泻','landslide','landslip'],['停工','返工','工作安排','work arrangements'],['紫外线','防晒','ultraviolet','uv index']];
function expandQuery(text){const query=toSimple(text).toLowerCase();return query+' '+CONCEPTS.filter(group=>group.some(term=>query.includes(term))).flat().join(' ')}
function tokens(text){const s=expandQuery(text);return [...new Set([...(s.match(/[a-z0-9]{2,}/g)||[]),...(s.match(/[\u3400-\u9fff]+/g)||[]).flatMap(w=>w.length===1?[w]:Array.from({length:w.length-1},(_,i)=>w.slice(i,i+2)))])]}
function retrieve(query,documents,limit=6){
 if(!Number.isInteger(limit)||limit<=0)return [];
 const terms=tokens(query);if(!terms.length)return [];
 const chunks=documents.flatMap(d=>d.chunks.map(c=>({...c,documentId:d.id,title:d.title,publisher:d.publisher,url:d.url,importedAt:d.importedAt,sha256:d.sha256,language:d.language,topics:d.topics,local:!!d.local,tags:d.tags||''})));
 if(!chunks.length)return [];
 const bodies=chunks.map(c=>toSimple(c.text).toLowerCase());
 const average=bodies.reduce((sum,s)=>sum+s.length,0)/bodies.length;
 const df=new Map(terms.map(t=>[t,bodies.filter(s=>s.includes(t)).length]));
 const ranked=chunks.map((c,i)=>{
  const body=bodies[i],title=toSimple(c.title+' '+c.tags).toLowerCase();let score=0;
  for(const term of terms){
   const frequency=body.split(term).length-1,n=df.get(term);
   if(frequency)score+=Math.log(1+(chunks.length-n+.5)/(n+.5))*frequency*2.2/(frequency+1.2*(.25+.75*body.length/average));
   if(title.includes(term))score+=2.5;
  }
  return {...c,score};
 }).filter(c=>c.score>0).sort((a,b)=>b.score-a.score||a.id.localeCompare(b.id));
 const selected=[],counts=new Map();
 for(const c of ranked){if((counts.get(c.documentId)||0)>=2)continue;selected.push(c);counts.set(c.documentId,(counts.get(c.documentId)||0)+1);if(selected.length>=limit)break}
 return selected;
}

module.exports={tokens,retrieve};
