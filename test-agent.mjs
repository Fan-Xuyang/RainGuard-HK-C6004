import assert from 'node:assert/strict';
import fs from 'node:fs';
import {runToolAgent,executeAgentTool,inspectOfficialEvidence,resolveQuestionRegion} from './agent-tools.mjs';
const assets={};for(const name of ['snapshot','history','experiments','knowledge'])assets['/data/'+name+'.json']={body:fs.readFileSync('hk-web/data/'+name+'.json','utf8')};
const snapshots=JSON.parse(assets['/data/snapshot.json'].body),session={assets,citations:[],drafts:[],packet:async k=>({...snapshots[k],origin:'snapshot'})};
const warnings=await executeAgentTool('weather_window',{region:'沙田',maximum_halfhour_mm:1,duration_minutes:30},session);assert(warnings.blocked);assert.equal(warnings.windows.length,0);
const history=await executeAgentTool('historical_events',{station:'HKO',from_year:2023,minimum_mm:100},session);assert(history.events.length);assert(history.events.every(r=>r.value>=100&&r.complete==='C'));assert(history.source.startsWith('https://data.weather.gov.hk/'));
const firstPage=await executeAgentTool('historical_events',{station:'SHA',from_year:2025,minimum_mm:100},session);assert(firstPage.total>10);assert.equal(firstPage.query.fromDate,'2025-01-01');assert(firstPage.query.throughDate>='2026-01-01');assert(firstPage.events.some(row=>row.date.startsWith('2026')));assert.equal(firstPage.returnedCount,10);assert.equal(firstPage.hasMore,true);assert.equal(firstPage.nextOffset,10);assert(firstPage.paginationNote.includes('不表示原始数据缺失'));
const remaining=await executeAgentTool('historical_events',{station:'SHA',from_year:2025,minimum_mm:100,offset:firstPage.nextOffset,limit:50},session);assert.equal(firstPage.events.length+remaining.events.length,firstPage.total);assert.equal(remaining.hasMore,false);assert.equal(remaining.nextOffset,null);assert.equal(new Set([...firstPage.events,...remaining.events].map(r=>r.date)).size,firstPage.total);
for(const args of [{offset:-1},{offset:0.5},{limit:0},{limit:51}])await assert.rejects(executeAgentTool('historical_events',{station:'SHA',from_year:2025,minimum_mm:100,...args},session));
await assert.rejects(executeAgentTool('historical_events',{station:'../secrets',from_year:2023,minimum_mm:0},session));
await assert.rejects(executeAgentTool('search_knowledge',{query:'test',url:'https://untrusted.example'},session));
assert.equal(resolveQuestionRegion('沙田天气如何','油尖旺').name,'沙田');
const inspect=await inspectOfficialEvidence(new Request('http://local/api/agent/inspect',{method:'POST',body:JSON.stringify({region:'油尖旺',mode:'snapshot',question:'沙田需要核对什么'})}),assets,session.packet);const inspected=await inspect.json();assert.equal(inspected.context.region,'沙田');assert.equal(inspected.toolTrace.length,3);assert(inspected.answer.includes('未调用语言模型'));
const oldFetch=globalThis.fetch;let requests=0;
try{
 globalThis.fetch=async(url,options)=>{
  assert.equal(url,'https://api.deepseek.com/chat/completions');const body=JSON.parse(options.body);assert(body.tools.length>=6);
  if(requests++===0)return Response.json({choices:[{message:{role:'assistant',content:null,tool_calls:[{id:'call-1',type:'function',function:{name:'search_knowledge',arguments:JSON.stringify({query:'黑色暴雨警告'})}},{id:'call-2',type:'function',function:{name:'draft_review',arguments:JSON.stringify({region:'沙田',title:'核对官方警告与现场排水'})}}]}}],usage:{total_tokens:10}});
  assert.equal(body.messages.filter(m=>m.role==='tool').length,2);
  assert(body.messages.some(m=>m.role==='tool'&&m.content.includes('requiresHumanConfirmation')));
  return Response.json({model:'mock-tool-model',choices:[{message:{content:'请核对官方来源 [1]。已生成待人工确认草稿，未保存工单。'}}],usage:{total_tokens:20}});
 };
 const result=await runToolAgent({messages:[{role:'system',content:'test'}],env:{DEEPSEEK_API_KEY:'test'},assets,citations:[],getPacket:session.packet,mode:'snapshot',packets:{}});
 assert.equal(requests,2);assert.equal(result.trace.length,2);assert(result.trace.every(t=>t.ok));assert.equal(result.drafts[0].status,'unsubmitted');assert.equal(result.usage.total_tokens,30);
 let round=0;globalThis.fetch=async()=>Response.json({choices:[{message:{content:null,tool_calls:[{id:'r'+round++,type:'function',function:{name:'shell',arguments:'{}'}}]}}]});
 await assert.rejects(runToolAgent({messages:[],env:{DEEPSEEK_API_KEY:'test'},assets,citations:[],getPacket:session.packet,mode:'snapshot',packets:{}}));assert(round<=4);
 console.log('PASS: actual tool execution against official records, model/tool/model protocol, draft-only action, snapshot blocking, invalid parameters and bounded loops (mock model; no billable API).');
}finally{globalThis.fetch=oldFetch}
