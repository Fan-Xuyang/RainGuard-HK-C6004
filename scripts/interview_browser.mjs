// Dedicated local browser profile. Never reads the provider API key.
// --verify-agent makes one bounded, billable chat request through the real UI.
import {chromium} from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const verify=process.argv.includes('--verify-agent');
const output=process.env.RAINGUARD_INTERVIEW_OUTPUT||'runtime/interview-2026-10-20';
fs.mkdirSync(output,{recursive:true});
const context=await chromium.launchPersistentContext(path.resolve('runtime/interview-browser'),{
  headless:verify,viewport:{width:1440,height:1000},
  executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||'C:/Users/35348/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe',
});
try{
 const page=context.pages()[0]||await context.newPage();
 await page.goto('http://127.0.0.1:8100/#overview');
 await page.waitForSelector('#resourceCoverage tbody tr',{state:'attached'});
 await page.waitForFunction(()=>!document.querySelector('#dataMode').disabled,null,{timeout:60000});
 if(verify){
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(output,'01-live-overview.png'),fullPage:false});
  await page.locator('nav button[data-page="assistant"]').click();
  await page.locator('#chatQuestion').fill('请只调用 knowledge_inventory 工具，核对当前知识库实际有多少份官方资料、多少个片段、包含哪些发布部门。简体中文150字以内回答，不要推断现场安全，也不要创建任何草稿或业务任务。');
  const response=page.waitForResponse(r=>r.url().endsWith('/api/assistant')&&r.request().method()==='POST',{timeout:140000});
  await page.locator('#chatSend').click();
  const r=await response,p=await r.json();assert.equal(r.status(),200,p.error||'Chat failed');
  assert(p.answer?.trim());assert(p.toolTrace?.some(t=>t.tool==='knowledge_inventory'&&t.ok));
  const inventory=p.toolTrace.find(t=>t.tool==='knowledge_inventory').result;
  assert.equal(inventory.sources,44);assert.equal(inventory.chunks,370);
  assert.equal(p.drafts?.length||0,0);
  await page.waitForFunction(()=>!document.querySelector('#chatSend').disabled);
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(output,'02-real-web-agent.png'),fullPage:false});
  fs.writeFileSync(path.join(output,'web-agent-check.json'),JSON.stringify({passed:true,checkedAt:new Date().toISOString(),model:p.model,answer:p.answer,tools:p.toolTrace.map(t=>({tool:t.tool,ok:t.ok,elapsedMs:t.elapsedMs})),inventory:{sources:inventory.sources,chunks:inventory.chunks},contextMode:p.context?.mode,billable:true,businessWrites:false},null,2));
  console.log('PASS: real browser chat -> Node -> DeepSeek -> knowledge_inventory, actual 44 sources/370 chunks, no draft or business writes.');
 }else{
  // A separate host keeps rehearsal cookies separate from the formal 127.0.0.1 entry.
  const assistant=await context.newPage();await assistant.goto('http://127.0.0.1:8100/#assistant');
  if(fs.existsSync('runtime/enterprise-qa-access.json')){
   const qa=JSON.parse(fs.readFileSync('runtime/enterprise-qa-access.json','utf8'));
   const workflow=await context.newPage();await workflow.goto('http://localhost:8110/enterprise/');
   const login=await workflow.request.post('http://localhost:8110/api/auth/login',{data:{username:qa.username,password:qa.password}});
   if(login.ok()){await workflow.reload();await workflow.locator('#appView').waitFor({state:'visible'});if(fs.existsSync('runtime/interview-2026-10-20/rehearsal-ready.json')){const prepared=JSON.parse(fs.readFileSync('runtime/interview-2026-10-20/rehearsal-ready.json','utf8'));await workflow.locator(`[data-run="${prepared.runId}"]`).click();await workflow.locator('#detail h2').waitFor();await workflow.screenshot({path:path.join(output,'03-real-agent-human-approval.png'),fullPage:true});}}
  }
  await page.bringToFront();console.log('Interview browser ready: live dashboard, cached real assistant response, isolated workflow rehearsal.');
  await new Promise(resolve=>context.on('close',resolve));
 }
}finally{await context.close().catch(()=>{})}
