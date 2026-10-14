import http from 'node:http';import fs from 'node:fs';import path from 'node:path';import {handle} from './server-api.mjs';
import {createWorkspaceStore} from './workspace-store.mjs';
if(fs.existsSync('.env.local')){for(const line of fs.readFileSync('.env.local','utf8').split(/\r?\n/)){const m=line.match(/^([A-Z_]+)=(.*)$/);if(m&&!process.env[m[1]])process.env[m[1]]=m[2].replace(/^[\"']|[\"']$/g,'')}}
const web=path.join(process.cwd(),'hk-web'),assets={},types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.csv':'text/csv; charset=utf-8','.md':'text/plain; charset=utf-8','.txt':'text/plain; charset=utf-8'};
function scan(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const f=path.join(dir,e.name);if(e.isDirectory())scan(f);else assets['/'+path.relative(web,f).replaceAll('\\','/')]={type:(f.includes('knowledge')&&f.endsWith('.html')?'text/plain; charset=utf-8':types[path.extname(f)])||'text/plain',body:fs.readFileSync(f,'utf8')}}}scan(web);
const store=process.env.WORKSPACE_TOKEN?createWorkspaceStore({path:process.env.WORKSPACE_DB||'runtime/workspace.sqlite',token:process.env.WORKSPACE_TOKEN}):null;
const port=Number(process.env.PORT||8095),host=process.env.HOST||'127.0.0.1';
http.createServer(async(req,res)=>{try{
 const request=new Request((process.env.PUBLIC_ORIGIN||'http://'+(req.headers.host||'localhost:'+port))+req.url,{method:req.method,headers:req.headers,...(['GET','HEAD'].includes(req.method)?{}:{body:req,duplex:'half'})});
 let response;
 if(new URL(request.url).pathname.startsWith('/api/workspace'))response=store?await store.handle(request):Response.json({configured:false,error:'此服务未配置共享存储'},{status:request.method==='GET'&&req.url==='/api/workspace/status'?200:503,headers:{'Cache-Control':'no-store'}});
 else response=await handle(request,assets,process.env);
 res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
}catch{res.writeHead(500);res.end('Service error')}}).listen(port,host,()=>console.log('RainGuard HK: http://'+host+':'+port+' · Shared workspace '+(store?'enabled':'disabled')));
