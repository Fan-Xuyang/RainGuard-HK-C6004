import fs from 'node:fs';import path from 'node:path';import {normalize} from './hk-web/core.mjs';
const root=process.cwd(),web=path.join(root,'hk-web');
const raw=JSON.parse(fs.readFileSync(path.join(web,'data/snapshot-raw.json'),'utf8'));for(const [k,v]of Object.entries(raw))v.data=normalize(k,v.data);
fs.writeFileSync(path.join(web,'data/snapshot.json'),JSON.stringify(raw));
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.csv':'text/csv; charset=utf-8','.md':'text/plain; charset=utf-8','.txt':'text/plain; charset=utf-8'};
const assets={};function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const f=path.join(dir,entry.name);if(entry.isDirectory())walk(f);else if(entry.name!=='snapshot-raw.json'){const key='/'+path.relative(web,f).replaceAll('\\','/');assets[key]={type:(f.includes('knowledge')&&f.endsWith('.html')?'text/plain; charset=utf-8':mime[path.extname(f)])||'text/plain; charset=utf-8',body:fs.readFileSync(f,'utf8')}}}}walk(web);
const core=fs.readFileSync(path.join(web,'core.mjs'),'utf8'),api=fs.readFileSync(path.join(root,'server-api.mjs'),'utf8').replace(/^import [^\r\n]*\r?\n/gm,'');
const extras=['hk-web/simplify.mjs','hk-web/retrieval.mjs','agent-tools.mjs','assistant-api.mjs'].map(f=>fs.readFileSync(f,'utf8').replace(/^import [^\r\n]*\r?\n/gm,'')).join('\n');
// The durable enterprise service and its authenticated tool bridge run in Node/Docker only.
const enterpriseBoundary='\nasync function workflowBridge(){return Response.json({error:"企业工具桥仅在 Node/Docker 服务可用"},{status:503})}\n';
const compiled=core+'\n'+extras+enterpriseBoundary+'\nconst ASSETS='+JSON.stringify(assets)+';\n'+api+'\nexport default {fetch(request,env){return handle(request,ASSETS,env)}};';
fs.mkdirSync('worker',{recursive:true});fs.writeFileSync('worker/index.js',compiled);
fs.mkdirSync('dist/server',{recursive:true});fs.writeFileSync('dist/server/index.js',compiled);if(fs.existsSync('.openai/hosting.json')){fs.mkdirSync('dist/.openai',{recursive:true});fs.copyFileSync('.openai/hosting.json','dist/.openai/hosting.json')}
console.log('Built Hong Kong Worker:',Object.keys(assets).length,'assets,',compiled.length,'characters');
