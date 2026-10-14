import {SOURCES,normalize} from './hk-web/core.mjs';
import {answer,assistantStatus} from './assistant-api.mjs';
import {inspectOfficialEvidence} from './agent-tools.mjs';
const memo=new Map();
export async function handle(request,assets,env={}){
 const url=new URL(request.url);let path;try{path=decodeURIComponent(url.pathname)}catch{return new Response('Invalid path',{status:400})}
 if(path==='/api/assistant/status'&&request.method==='GET')return assistantStatus(env);
 if(path==='/api/agent/inspect'&&request.method==='POST')return inspectOfficialEvidence(request,assets,async k=>{const response=await handle(new Request(url.origin+'/api/'+k),assets,env);const packet=await response.json();if(!response.ok)throw Error('官方源查询失败');return packet});
 if(path==='/api/assistant'&&request.method==='POST')return answer(request,assets,env,async k=>{const r=await handle(new Request(url.origin+'/api/'+k),assets,env);const p=await r.json();if(!r.ok)throw Error('upstream');return p});
 if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405});
 if(path.startsWith('/api/')){
  const key=path.slice(5),source=SOURCES[key];if(!source)return Response.json({error:'Unknown data source'},{status:404});
  const cached=memo.get(key);if(cached&&Date.now()-cached.time<180000)return Response.json(cached.packet,{headers:{'Cache-Control':'private,max-age=60'}});
  try{const r=await fetch(source.url,{signal:AbortSignal.timeout(25000),headers:{'Accept':'application/json,text/csv'}});if(!r.ok)throw Error('Upstream HTTP '+r.status);
   const bytes=await r.arrayBuffer(),text=new TextDecoder().decode(bytes),raw=source.format==='json'?JSON.parse(text):text,data=normalize(key,raw);
   if(key==='rain'&&!Array.isArray(data.hourlyRainfall))throw Error('Invalid rainfall schema');
   if((key==='tides'||key==='nowcast')&&!data.length)throw Error('Empty upstream data');
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');
   const packet={data,source:source.url,receivedAt:new Date().toISOString(),sha256:hash};memo.set(key,{time:Date.now(),packet});return Response.json(packet,{headers:{'Cache-Control':'private,max-age=60'}});
  }catch(e){return Response.json({error:e.message,source:source.url,failedAt:new Date().toISOString()},{status:502})}
 }
 const entry=assets[path==='/'?'/index.html':path];if(!entry)return new Response('Not found',{status:404});
 return new Response(request.method==='HEAD'?null:entry.body,{headers:{'Content-Type':entry.type,'Cache-Control':path.includes('/data/')?'no-cache':'public,max-age=120','X-Content-Type-Options':'nosniff','Referrer-Policy':'strict-origin-when-cross-origin'}});
}
