import {SOURCES,REGIONS,isStale,regionRain,numeric,nearestNowcast,observationTime} from './hk-web/core.mjs';
import {retrieve} from './hk-web/retrieval.mjs';
const agentFunction=(name,description,properties,required)=>({type:'function',function:{name,description,parameters:{type:'object',properties,required,additionalProperties:false}}});
const agentRegion={type:'string',description:'香港18区名称，简体或繁体'};
export const AGENT_TOOLS=[
 agentFunction('search_knowledge','检索官方天气与运营知识，返回可引用编号和PDF页号',{query:{type:'string'}},['query']),
 agentFunction('compare_regions','比较多个香港地区当前雨量，报告时效与来源',{regions:{type:'array',items:agentRegion}},['regions']),
 agentFunction('historical_events','检索真实历史高雨量记录，不是物业水浸事件',{station:{type:'string',enum:['HKO','LFS','SHA']},from_year:{type:'integer'},minimum_mm:{type:'number'}},['station','from_year','minimum_mm']),
 agentFunction('model_results','读取已完成的五方法离线实验，不能当作当前预测',{station:{type:'string',enum:['HKO','LFS','SHA']},trace_policy:{type:'string',enum:['exclude','zero']}},['station','trace_policy']),
 agentFunction('weather_window','核验未来完整30或60分钟降雨窗口。过期/快照/警告阻止作业建议',{region:agentRegion,maximum_halfhour_mm:{type:'number'},duration_minutes:{type:'integer',enum:[30,60]}},['region','maximum_halfhour_mm','duration_minutes']),
 agentFunction('knowledge_inventory','查看已验证知识库的来源、语言和主题覆盖，不生成来源内容',{},[]),
 agentFunction('observation_health','检查多个真实天气接口的时效、缺测、来源和校验值',{keys:{type:'array',items:{type:'string',enum:['rain','weather','warnings','tides','nowcast','local']}}},['keys']),
 agentFunction('draft_review','生成人工复核草稿，不保存工单、不发布停工指令',{region:agentRegion,title:{type:'string'}},['region','title']),
];
const REGION_ENGLISH=['Central and Western','Eastern','Southern','Wan Chai','Kowloon City','Kwun Tong','Sham Shui Po','Wong Tai Sin','Yau Tsim Mong','Islands','Kwai Tsing','North','Sai Kung','Sha Tin','Tai Po','Tsuen Wan','Tuen Mun','Yuen Long'];
const agentCanonical=value=>REGIONS.find((r,i)=>r.name===value||toSimple(r.name)===toSimple(value)||REGION_ENGLISH[i].toLowerCase()===String(value).toLowerCase());
import {toSimple} from './hk-web/simplify.mjs';
export function resolveQuestionRegion(question,fallback){const text=toSimple(question||'');const english=REGION_ENGLISH.map((name,index)=>{const alias=['North','Eastern','Southern','Islands'].includes(name)?name+' District':name;const found=new RegExp('\\b'+alias+'\\b','i').exec(text);return found?{index,position:found.index}:null}).filter(Boolean).sort((a,b)=>a.position-b.position)[0];if(english)return REGIONS[english.index];return REGIONS.filter(r=>text.includes(toSimple(r.name))).sort((a,b)=>text.indexOf(toSimple(a.name))-text.indexOf(toSimple(b.name)))[0]||agentCanonical(fallback)}
const agentAsset=(assets,name)=>JSON.parse(assets['/data/'+name+'.json'].body);
export async function readAgentJSON(request,maximum){
 const reader=request.body?.getReader();if(!reader)throw Object.assign(Error('请求无效'),{status:400});
 let size=0,text='';const decoder=new TextDecoder();
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>maximum){await reader.cancel();throw Object.assign(Error('请求过大'),{status:413})}text+=decoder.decode(value,{stream:true})}
 const input=JSON.parse(text+decoder.decode());if(!input||typeof input!=='object'||Array.isArray(input))throw Object.assign(Error('请求无效'),{status:400});return input;
}

export async function executeAgentTool(name,args,session){
 const spec=AGENT_TOOLS.find(t=>t.function.name===name)?.function.parameters;
 if(!spec||!args||typeof args!=='object'||Array.isArray(args)||Object.keys(args).some(k=>!Object.hasOwn(spec.properties,k))||spec.required.some(k=>!Object.hasOwn(args,k)))throw Error('工具名或参数无效');
 const station=()=>{if(!['HKO','LFS','SHA'].includes(args.station))throw Error('未知历史站点');return args.station};
 if(name==='knowledge_inventory'){
  const kb=agentAsset(session.assets,'knowledge');return {sources:kb.documents.length,chunks:kb.documents.reduce((n,d)=>n+d.chunks.length,0),updatedAt:kb.updatedAt||null,documents:kb.documents.map(({id,title,url,publisher,language,topics,sha256})=>({id,title,url,publisher,language,topics,sha256})),limitation:'资料抓取时间不是官方规则生效时间，现场决策仍需人工核对'};
 }
 if(name==='observation_health'){
  if(!Array.isArray(args.keys)||args.keys.length<1||args.keys.length>6||args.keys.some(k=>!['rain','weather','warnings','tides','nowcast','local'].includes(k)))throw Error('数据源列表无效');
  return {checkedAt:new Date().toISOString(),sources:await Promise.all([...new Set(args.keys)].map(async id=>{try{const p=await session.packet(id);return {id,url:SOURCES[id].url,origin:p.origin,receivedAt:p.receivedAt,observedAt:p.data?observationTime(id,p.data):null,stale:!p.data||isStale(id,p),sha256:p.sha256,error:p.error||null}}catch{return {id,url:SOURCES[id].url,error:'本次来源不可用',stale:true}}})),limitation:'接口可用或数据新鲜不代表现场安全'};
 }
 if(name==='search_knowledge'){
  if(typeof args.query!=='string'||!args.query.trim()||args.query.length>500)throw Error('检索词须为1–500字符');
  return {citations:retrieve(args.query,agentAsset(session.assets,'knowledge').documents,6).map(h=>{
   let citation=session.citations.find(c=>c.id===h.id);
   if(!citation){citation={number:session.citations.length+1,id:h.id,title:h.title,url:h.url,publisher:h.publisher,importedAt:h.importedAt,sha256:h.sha256,page:h.page||null,text:h.text};session.citations.push(citation)}
   return citation;
  })};
 }
 if(name==='compare_regions'){
  if(!Array.isArray(args.regions)||!args.regions.length||args.regions.length>5)throw Error('选择1–5个地区');
  const regions=args.regions.map(agentCanonical);if(regions.some(r=>!r))throw Error('未知地区');
  const p=await session.packet('weather');
  return {observedAt:p.data?.rainfall?.endTime,origin:p.origin,stale:isStale('weather',p),source:SOURCES.weather.url,sha256:p.sha256,measurement:'地区过去一小时雨量上限，不是平均值',rows:regions.map(r=>({region:toSimple(r.name),mm:numeric(regionRain(p.data,r.name)?.max)}))};
 }
 if(name==='historical_events'){
  const code=station();if(!Number.isInteger(args.from_year)||args.from_year<2000||args.from_year>2026||!Number.isFinite(args.minimum_mm)||args.minimum_mm<0||args.minimum_mm>1000)throw Error('年份或雨量条件无效');
  const h=agentAsset(session.assets,'history')[code];
  const all=h.records.filter(r=>r.complete==='C'&&r.value!==null&&r.date>=args.from_year+'-01-01'&&r.value>=args.minimum_mm).sort((a,b)=>b.value-a.value);
  return {station:code,total:all.length,events:all.slice(0,10),source:h.source,sha256:h.sha256,limitation:'这是站点高雨量日，没有实际物业水浸标签'};
 }
 if(name==='model_results'){
  const code=station();if(!['exclude','zero'].includes(args.trace_policy))throw Error('处理策略无效');
  const e=agentAsset(session.assets,'experiments');return {results:e.results.filter(r=>r.station===code&&r.trace_policy===args.trace_policy),protocol:e.protocol,splits:e.splits,source_hashes:e.source_hashes,limitation:e.target};
 }
 if(name==='weather_window'){
  const r=agentCanonical(args.region);if(!r||!Number.isFinite(args.maximum_halfhour_mm)||args.maximum_halfhour_mm<0||args.maximum_halfhour_mm>100||![30,60].includes(args.duration_minutes))throw Error('窗口参数无效');
  const [p,w]=await Promise.all([session.packet('nowcast'),session.packet('warnings')]);
  const warnings=Object.values(w.data||{}).filter(x=>x?.name&&x.actionCode!=='CANCEL');
  const blocked=p.origin!=='online'||w.origin!=='online'||isStale('nowcast',p)||isStale('warnings',w)||warnings.length>0;
  if(blocked)return {blocked:true,reason:'快照、过期、缺失或官方警告生效，停止生成当前作业建议',warnings:warnings.map(x=>x.name),windows:[],sources:[SOURCES.nowcast.url,SOURCES.warnings.url]};
  const points=nearestNowcast(p.data,r.lat,r.lon),n=args.duration_minutes/30,windows=[];
  for(let i=0;i<=points.length-n;i++){
   const segment=points.slice(i,i+n),start=Date.parse(segment[0].end)-1800000;
   if(start>=Date.now()&&segment.every((x,j)=>x.value!==null&&x.value<=args.maximum_halfhour_mm&&(!j||Date.parse(x.end)-Date.parse(segment[j-1].end)===1800000)))windows.push({start:new Date(start).toISOString(),end:segment.at(-1).end,total_mm:segment.reduce((s,x)=>s+x.value,0)});
  }
  return {blocked:false,region:toSimple(r.name),issued:points[0]?.issued,windows,source:SOURCES.nowcast.url,sha256:p.sha256,limitation:'仅符合降雨条件，不能保证现场安全'};
 }
 if(name==='draft_review'){
  const r=agentCanonical(args.region);if(!r||typeof args.title!=='string'||!args.title.trim()||args.title.length>180)throw Error('草稿地区或标题无效');
  const draft={id:'draft-'+(session.drafts.length+1),region:r.name,title:args.title.trim(),status:'unsubmitted',checks:['核对官方来源与观测时间','核对实际现场情况','记录负责人和后续安排'],createdAt:new Date().toISOString()};session.drafts.push(draft);return {draft,saved:false,requiresHumanConfirmation:true};
 }
}

export async function runToolAgent({messages,env,assets,citations,getPacket,mode,packets}){
 const trace=[],drafts=[],usage={};let calls=0;const deadline=Date.now()+75000;
 const session={assets,citations,drafts,packet:async k=>{
  if(packets[k]?.data)return packets[k];
  const p=mode==='snapshot'?{...agentAsset(assets,'snapshot')[k],origin:'snapshot'}:{...await getPacket(k),origin:'online'};packets[k]=p;return p;
 }};
 for(let round=0;round<4;round++){
  if(Date.now()>=deadline)throw Error('Agent执行预算已用尽');
  const response=await fetch('https://api.deepseek.com/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+env.DEEPSEEK_API_KEY,'Content-Type':'application/json'},body:JSON.stringify({model:env.DEEPSEEK_MODEL||'deepseek-flash',messages,tools:AGENT_TOOLS,tool_choice:round===3||calls>=8?'none':'auto',max_tokens:1800,stream:false,thinking:{type:'disabled'}}),signal:AbortSignal.timeout(Math.max(1,Math.min(25000,deadline-Date.now())))});
  if(!response.ok){const error=Error('DeepSeek HTTP '+response.status);error.providerStatus=response.status;throw error}
  const result=await response.json(),message=result.choices?.[0]?.message;
  for(const [k,v]of Object.entries(result.usage||{}))if(typeof v==='number')usage[k]=(usage[k]||0)+v;
  if(!message)throw Error('空模型响应');
  if(!message.tool_calls?.length){if(typeof message.content!=='string'||!message.content.trim())throw Error('空回答');return {answer:message.content,model:result.model||env.DEEPSEEK_MODEL,usage,trace,drafts}}
  if(!Array.isArray(message.tool_calls)||message.tool_calls.length>8-calls||round===3)throw Error('工具调用超出预算');
  messages.push({role:'assistant',content:message.content||null,tool_calls:message.tool_calls});
  for(const call of message.tool_calls){
   calls++;const started=Date.now();let output,args={};
   try{if(typeof call.id!=='string'||typeof call.function?.arguments!=='string'||call.function.arguments.length>4000)throw Error('工具格式无效');args=JSON.parse(call.function.arguments);output=await executeAgentTool(call.function.name,args,session)}catch(e){output={error:e.message}}
   trace.push({step:calls,tool:call.function?.name||'unknown',arguments:args,ok:!output.error,elapsedMs:Date.now()-started,summary:output.error||Object.keys(output).join(', '),result:output});
   messages.push({role:'tool',tool_call_id:call.id,content:JSON.stringify(output).slice(0,24000)});
  }
 }
 throw Error('Agent未在预算内完成回答');
}

export async function inspectOfficialEvidence(request,assets,getPacket){
 const headers={'Cache-Control':'no-store'};
 if(request.headers.get('origin')&&request.headers.get('origin')!==new URL(request.url).origin)return Response.json({error:'不允许跨站调用'},{status:403,headers});
 let input;try{input=await readAgentJSON(request,8000)}catch(e){return Response.json({error:'请求格式无效或过大'},{status:e.status||400,headers})}
 const r=resolveQuestionRegion(input.question,input.region);if(!r||typeof input.question!=='string'||!input.question.trim()||input.question.length>500)return Response.json({error:'请选择有效区域，问题为1–500字符'},{status:400,headers});
 const packets={},citations=[],drafts=[],trace=[];
 const session={assets,citations,drafts,packet:async k=>{
  if(packets[k])return packets[k];
  packets[k]=input.mode==='snapshot'?{...agentAsset(assets,'snapshot')[k],origin:'snapshot'}:{...await getPacket(k),origin:'online'};return packets[k];
 }};
 const plan=[['search_knowledge',{query:input.question}],['compare_regions',{regions:[r.name]}],['weather_window',{region:r.name,maximum_halfhour_mm:1,duration_minutes:30}]];
 for(const [tool,args]of plan){const start=Date.now();let result;try{result=await executeAgentTool(tool,args,session)}catch(e){result={error:e.message}}trace.push({step:trace.length+1,tool,arguments:args,ok:!result.error,elapsedMs:Date.now()-start,summary:result.error||'官方来源核验',result})}
 const sources=Object.entries(packets).map(([k,p])=>({id:k,url:SOURCES[k].url,origin:p.origin,receivedAt:p.receivedAt,observationAt:p.data?observationTime(k,p.data):null,sha256:p.sha256,stale:!p.data||isStale(k,p)}));
 return Response.json({answer:input.language==='en'?'Source checks completed without a language model. Official knowledge, district rainfall and the 30-minute forecast window were checked. See the tool trace for values, missing data and blocking reasons. This does not establish site safety.':input.language==='yue-HK'?'已完成來源核對，冇調用語言模型。已檢索官方資料，同時核對地區雨量同30分鐘預報時段；實際數值、缺失資料同停止篩選嘅原因，請睇工具紀錄。呢個結果唔代表現場安全。':'来源核验已完成，未调用语言模型。已检索官方知识并核对地区雨量与30分钟预报窗口；具体数值、缺失或停止筛选原因见工具轨迹。此结果不是现场安全判断。',model:'官方工具核验（非模型回答）',citations,drafts,toolTrace:trace,context:{region:toSimple(r.name),mode:input.mode==='snapshot'?'历史快照，不能表述为当前情况':'在线来源核验',sources},evidenceCheck:{scope:'确定性工具执行，无生成式推理；不代表事实评分',unknownReferences:[],staleOrSnapshotSources:sources.filter(s=>s.stale||s.origin!=='online').map(s=>s.id)},generatedAt:new Date().toISOString()},{headers});
}
