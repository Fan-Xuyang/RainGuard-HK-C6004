import { chromium } from 'playwright-core';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const base = process.env.RAINGUARD_BASE || 'http://127.0.0.1:8100';
const browser = await chromium.launch({headless:true, executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || 'C:/Users/35348/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'});
const page = await browser.newPage({viewport:{width:1440,height:1000}}), errors=[];
page.on('pageerror', e => errors.push(e.message));
fs.mkdirSync('docs/screenshots/unified',{recursive:true});
try {
  await page.goto(base + '/');
  await page.waitForSelector('#resourceCoverage tbody tr', {state:'attached'});
  assert.equal(await page.locator('nav button[data-page]').count(),12);
  await page.waitForFunction(() => !document.querySelector('#dataMode').disabled, null, {timeout:60000});
  const names = await page.locator('nav button[data-page]').evaluateAll(nodes=>nodes.map(n=>n.dataset.page));
  for (const name of names) {
    await page.locator(`nav button[data-page="${name}"]`).click();
    await page.locator(`#${name}`).waitFor({state:'visible'});
  }
  const climate = await page.request.get(base + '/api/climate/series?station=CCH&variable=TEMP&from=2025&to=2025');
  assert.equal(climate.status(),200);
  assert((await climate.json()).rows.length > 300);
  await page.locator('#resourceQuery').click();
  await page.waitForSelector('.climate-chart');
  const csvReady=page.waitForEvent('download');await page.locator('#resourceCSV').click();const csv=await csvReady;assert(csv.suggestedFilename().endsWith('-official.csv'));const stream=await csv.createReadStream(),parts=[];for await(const part of stream)parts.push(part);const csvText=Buffer.concat(parts).toString('utf8');assert(csvText.includes('source_id')&&csvText.includes('2025-01-01'));
  await page.screenshot({path:'docs/screenshots/unified/data-desktop.png',fullPage:true});
  await page.locator('nav button[data-page="assistant"]').click();
  const status = await (await page.request.get(base + '/api/assistant/status')).json();
  assert.equal(status.provider,'DeepSeek');
  assert.equal(status.configured,true);
  await page.locator('#dataMode').selectOption('snapshot');
  await page.locator('#chatQuestion').fill('沙田当前来源是否可用？核对暴雨警告与30分钟窗口');
  await page.locator('#inspectSources').click();
  await page.waitForSelector('.agent-trace details');
  assert.equal(await page.locator('.agent-trace details').count(),3);
  await page.locator('nav button[data-page="overview"]').click();
  await page.evaluate(()=>scrollTo(0,0));
  await page.waitForTimeout(4200);
  await page.screenshot({path:'docs/screenshots/unified/weather-desktop.png',fullPage:false});
  await page.locator('a[href="/enterprise/"]').click();
  await page.waitForURL('**/enterprise/');
  await page.locator('#loginView').waitFor({state:'visible'});
  // No production records or paid model requests are created by this check.
  const env = Object.fromEntries(fs.readFileSync('runtime/enterprise.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>[l.slice(0,l.indexOf('=')),l.slice(l.indexOf('=')+1)]));
  const login = await page.request.post(base + '/api/auth/login',{data:{username:env.BOOTSTRAP_ADMIN_USER || 'admin',password:env.BOOTSTRAP_ADMIN_PASSWORD}});
  assert.equal(login.status(),200,'Local bootstrap login; update local credentials if password was changed');
  await page.reload();
  await page.locator('#appView').waitFor({state:'visible'});
  await page.locator('#appView a.workspace-switch').click();
  await page.waitForSelector('nav button[data-page="overview"]');
  await page.locator('a[href="/enterprise/"]').click();
  await page.locator('#appView').waitFor({state:'visible'});
  await page.locator('#logout').click();
  await page.locator('#loginView').waitFor({state:'visible'});
  await page.locator('#loginView a.workspace-switch').click();
  await page.waitForSelector('#resourceCoverage tbody tr', {state:'attached'});
  await page.setViewportSize({width:390,height:844});
  for (const name of ['resources','assistant']) {
    await page.locator(`nav button[data-page="${name}"]`).click();
    const overflow = await page.evaluate(()=>document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert(overflow<=3,`${name}: overflow ${overflow}`);
    await page.screenshot({path:`docs/screenshots/unified/${name}-mobile.png`,fullPage:true});
  }
  assert.equal((await page.request.post(base + '/api/internal/workflow/tool',{data:{}})).status(),404);
  assert.equal((await page.request.post(base + '/api/agent/inspect',{headers:{origin:'https://untrusted.invalid'},data:{}})).status(),403);
  assert.deepEqual(errors,[]);
  console.log('PASS: original 12 pages, actual climate records, configured assistant, evidence tools, same-origin enterprise navigation/session, mobile layout and API boundaries. No paid model calls or production workflow writes.');
} finally { await browser.close(); }
