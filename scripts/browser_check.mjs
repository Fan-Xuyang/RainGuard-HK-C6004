import {chromium} from 'playwright-core';
import {spawn} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const root=process.cwd(),port=8112,output=resolve(process.env.RAINGUARD_SCREENSHOTS||'runtime/screenshots');mkdirSync(output,{recursive:true});
const server=spawn(process.execPath,['serve-hk.mjs'],{cwd:root,env:{...process.env,PORT:String(port),HOST:'127.0.0.1',DEEPSEEK_API_KEY:'',WORKSPACE_TOKEN:''},stdio:['ignore','pipe','pipe']});
let browser;
try{
 for(let i=0;i<80;i++){try{if((await fetch('http://127.0.0.1:'+port)).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
 browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+port+'/#resources');await page.waitForSelector('#resourceCoverage tbody tr');
 assert.equal(await page.locator('nav button').count(),12);
 await page.locator('#resourceQuery').click();await page.waitForSelector('.climate-chart');
 await page.screenshot({path:resolve(output,'data-desktop.png'),fullPage:true});
 await page.locator('nav button[data-page="assistant"]').click();await page.locator('#dataMode').selectOption('snapshot');
 await page.locator('#chatQuestion').fill('沙田当前来源是否可用？核对暴雨警告与30分钟窗口');await page.locator('#inspectSources').click();
 await page.waitForSelector('.agent-trace details');assert.equal(await page.locator('.agent-trace details').count(),3);assert((await page.locator('#answerEvidence').textContent()).includes('沙田'));
 assert((await page.locator('#chatMessages').textContent()).includes('未调用语言模型'));
 await page.waitForTimeout(4100);await page.screenshot({path:resolve(output,'agent-desktop.png'),fullPage:false});
 await page.setViewportSize({width:390,height:844});await page.locator('nav button[data-page="resources"]').click();
 await page.screenshot({path:resolve(output,'data-mobile.png'),fullPage:true});
 const dimensions=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));assert(dimensions.scroll<=dimensions.width+3,JSON.stringify(dimensions));
 await page.locator('nav button[data-page="assistant"]').click();await page.screenshot({path:resolve(output,'agent-mobile.png'),fullPage:true});const chatWidth=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);assert(chatWidth<=3);
 assert.deepEqual(errors,[]);console.log('PASS: Chromium desktop/mobile, actual climate query, no-key tool inspection, 12 pages, no uncaught JS errors or horizontal page overflow. Screenshots:',output);
}finally{await browser?.close();server.kill()}
