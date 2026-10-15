import {chromium} from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.RAINGUARD_LANGUAGE_BASE||'http://127.0.0.1:8100';
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||'C:/Users/35348/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'});
fs.mkdirSync('docs/screenshots/multilingual',{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/');
 await page.waitForSelector('#playbookDetail h3',{state:'attached'});
 await page.waitForFunction(()=>!document.querySelector('#dataMode').disabled,null,{timeout:60000});
 await page.locator('#dataMode').selectOption('snapshot');
 await page.locator('nav button[data-page="operations"]').click();await page.locator('#newFacility').click();await page.locator('#facilityName').fill('用户填写的设施 Keep Original');await page.locator('#facilityDialog [data-close]').first().click();
 const canonical=await page.locator('#facilityRegion option').evaluateAll(nodes=>nodes.map(n=>n.value));
 for(const language of ['en','yue-HK','zh-CN']){
  await page.locator('[data-language-picker]').selectOption(language);
  await page.waitForFunction(lang=>document.documentElement.lang===lang,language);
  assert.equal(await page.locator('#facilityName').inputValue(),'用户填写的设施 Keep Original');
  assert.deepEqual(await page.locator('#facilityRegion option').evaluateAll(nodes=>nodes.map(n=>n.value)),canonical);
  assert.equal(await page.locator('#dataMode').inputValue(),'snapshot');
  const nav=await page.locator('nav button').allTextContents();
  assert.equal(nav.length,12);
  if(language==='en'){assert(nav.every(s=>!/[\u3400-\u9fff]/.test(s)),nav.join('|'));assert(!/[\u3400-\u9fff]/.test(await page.locator('#chatQuestion').getAttribute('placeholder')));assert(!/[\u3400-\u9fff]/.test(await page.locator('#statusText').textContent()));}
  if(language==='zh-CN')assert(nav.some(s=>s.includes('数据工作台')));
  const pages=await page.locator('nav button').evaluateAll(nodes=>nodes.map(n=>n.dataset.page));
  for(const name of pages){await page.locator(`nav button[data-page="${name}"]`).click();await page.locator('#'+name).waitFor({state:'visible'})}
  await page.locator('nav button[data-page="knowledge"]').click();
  await page.locator('#kbLanguage').selectOption('en');
  await page.locator('#knowledgeSearch').fill('rainstorm');await page.locator('#knowledgeSearch').dispatchEvent('input');
  await page.waitForSelector('.knowledge-hit');
  const source=await page.locator('.knowledge-hit p').first().textContent();assert(/[A-Za-z]{5}/.test(source));
  if(!(await page.locator('[data-bookmark]').first().textContent()).includes('★'))await page.locator('[data-bookmark]').first().click();
  await page.locator('#kbBookmarks').check();assert(await page.locator('.knowledge-hit').count()>0);
  await page.locator('#kbBookmarks').uncheck();
  const downloadPromise=page.waitForEvent('download');await page.locator('#kbExport').click();const download=await downloadPromise;assert(download.suggestedFilename().endsWith('.json'));
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`docs/screenshots/multilingual/knowledge-${language}.png`,fullPage:false});
  await page.locator('#kbLanguage').selectOption('');await page.locator('#knowledgeSearch').fill('');await page.locator('#knowledgeSearch').dispatchEvent('input');
  await page.locator('nav button[data-page="planner"]').click();
  await page.locator('[data-playbook="heat"]').click();
  await page.locator('[data-check="0"]').check();
  await page.locator('#playbookDraft').click();assert(await page.locator('#taskDialog').isVisible());await page.locator('#taskDialog [data-close]').first().click();
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`docs/screenshots/multilingual/playbooks-${language}.png`,fullPage:false});
 }
 await page.locator('[data-language-picker]').selectOption('en');await page.reload();await page.waitForSelector('#playbookDetail h3',{state:'attached'});assert.equal(await page.locator('html').getAttribute('lang'),'en');
 await page.locator('.global-search-trigger').click();await page.locator('#commandQuery').fill('rainstorm');await page.waitForSelector('#commandResults a');assert(await page.locator('#commandResults a').count()>0);await page.locator('#closeCommand').click();
 await page.setViewportSize({width:390,height:844});
 for(const name of ['overview','knowledge','planner','resources','assistant']){
  await page.locator(`nav button[data-page="${name}"]`).click();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);assert(overflow<=3,`${name} overflow ${overflow}`);
 }
 await page.screenshot({path:'docs/screenshots/multilingual/english-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('PASS: three languages, 12 pages, persistence, canonical option values, unchanged user input, bilingual filters/bookmarks/export, playbook drafts, search and mobile layout.');
}finally{await browser.close()}
