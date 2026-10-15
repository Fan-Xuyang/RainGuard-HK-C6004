import fs from 'node:fs';
import {chromium} from 'playwright-core';
import {parseHTML} from 'linkedom';
import {templateText,canonicalText} from '../hk-web/i18n.mjs';
const strings=new Set(),add=s=>{s=canonicalText(s);if(/[\u3400-\u9fff]/.test(s)&&s.length<900&&!s.includes('${')&&!/[{}<>]/.test(s))strings.add(templateText(s).key)};
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||'C:/Users/35348/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'});
try{
 const page=await browser.newPage();
 await page.route('**/api/**',route=>route.abort()); // Failed requests explicitly select frozen evidence; no model calls.
 await page.goto(process.env.RAINGUARD_LOCALE_BASE||'http://127.0.0.1:8122/');
 await page.waitForSelector('#playbookDetail h3',{state:'attached'});
 await page.waitForTimeout(1200);
 const gathered=await page.evaluate(()=>{
  const strings=[],walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  let n;while(n=walker.nextNode())if(!n.parentElement?.closest('script,style,textarea,pre,code,[data-original],[data-i18n-skip],.chat-bubble,.knowledge-hit p,.source-card p,.leaflet-container'))strings.push(n.nodeValue);
  for(const n of document.querySelectorAll('[placeholder],[aria-label],[title]'))for(const key of ['placeholder','aria-label','title'])if(n.hasAttribute(key))strings.push(n.getAttribute(key));return strings;
 });gathered.forEach(add);
}finally{await browser.close()}
for(const filename of ['hk-web/index.html','enterprise/ui/index.html']){
 const {document}=parseHTML(fs.readFileSync(filename,'utf8'));const walker=document.createTreeWalker(document.body,4);let n;
 while(n=walker.nextNode())if(!n.parentElement?.closest('script,style,textarea,pre,code'))add(n.nodeValue);
 for(const n of document.querySelectorAll('[placeholder],[aria-label],[title]'))for(const key of ['placeholder','aria-label','title'])if(n.hasAttribute(key))add(n.getAttribute(key));
}
for(const filename of [...fs.readdirSync('hk-web').filter(f=>/\.(js|mjs)$/.test(f)&&!['simplify.mjs','i18n.mjs'].includes(f)).map(f=>'hk-web/'+f),'enterprise/ui/app.js']){
 const text=fs.readFileSync(filename,'utf8');
 for(const m of text.matchAll(/(["'])((?:\\.|(?!\1)[^\\\r\n])*?)\1/g)){
  const value=m[2].replace(/\\n/g,'\n');
  if(value.includes('<')&&value.includes('>')){
   try{const {document}=parseHTML('<body>'+value+'</body>');const walker=document.createTreeWalker(document.body,4);let n;while(n=walker.nextNode())add(n.nodeValue)}catch{}
  }else if(value.length<500&&!value.includes('=>')&&!value.includes('function'))add(value);
 }
}
fs.writeFileSync('runtime/locale-strings.json',JSON.stringify([...strings].sort(),null,2));
console.log('Collected',strings.size,'UI phrases; source quotations and user records excluded.');
