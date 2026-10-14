import {DatabaseSync} from 'node:sqlite';
import {mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {createHash,timingSafeEqual} from 'node:crypto';
import {REGIONS} from './hk-web/core.mjs';

const LIMIT=4_000_000;
const empty=()=>({workspace:{favorites:[],facilities:[],tasks:[],rules:{rain:30,tide:2.5}},incidents:[]});
const string=(v,max)=>typeof v==='string'&&v.length<=max;
export function validDocument(d){
 const w=d?.workspace;
 if(!w||!Array.isArray(w.favorites)||w.favorites.length>100||!w.favorites.every(v=>string(v,120))||!Array.isArray(w.facilities)||w.facilities.length>100||!Array.isArray(w.tasks)||w.tasks.length>200||!w.rules||!Number.isFinite(w.rules.rain)||w.rules.rain<1||w.rules.rain>200||!Number.isFinite(w.rules.tide)||w.rules.tide<.1||w.rules.tide>6||!Array.isArray(d.incidents)||d.incidents.length>200)return false;
 const region=v=>REGIONS.some(r=>r.name===v);
 if(![w.facilities,w.tasks,d.incidents].every(rows=>rows.every(r=>r&&typeof r==='object'&&!Array.isArray(r))))return false;
 const unique=rows=>new Set(rows.map(r=>r.id)).size===rows.length;
 if(![w.facilities,w.tasks,d.incidents].every(unique))return false;
 if(w.facilities.some(f=>!string(f.id,100)||!f.id||!string(f.name,120)||!f.name.trim()||!region(f.region)||!string(f.notes??'',1000)))return false;
 if(w.tasks.some(t=>!string(t.id,100)||!t.id||!string(t.title,240)||!t.title.trim()||!region(t.region)||!['open','working','done'].includes(t.status)||!string(t.owner??'',100)||!string(t.note??'',1200)||!Array.isArray(t.checks)||t.checks.length!==3||!t.checks.every(v=>typeof v==='boolean')||!Array.isArray(t.logs)||t.logs.length>500||t.logs.some(l=>!string(l.text,1000)||!string(l.time,60))||!t.evidence||!Array.isArray(t.evidence.warnings)||t.evidence.warnings.length>100||t.attachment&&(!string(t.attachment,1_000_000)||!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(t.attachment))))return false;
 if(w.tasks.some(t=>t.status==='done'&&(!t.owner?.trim()||!t.note?.trim()||!t.checks.every(Boolean))))return false;
 if(d.incidents.some(i=>!string(i.id,100)||!i.id||!string(i.place,240)||!i.place.trim()||!string(i.kind,100)||!string(i.note,2000)||!region(i.region)||typeof i.closed!=='boolean'||!string(i.time,60)||!string(i.weatherStatus,120)))return false;
 return true;
}

export function createWorkspaceStore({path,token}){
 if(typeof token!=='string'||token.length<24)throw Error('WORKSPACE_TOKEN must contain at least 24 characters');
 mkdirSync(dirname(path),{recursive:true});
 const db=new DatabaseSync(path);db.exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, body TEXT NOT NULL, updated_at TEXT); CREATE TABLE IF NOT EXISTS audit (revision INTEGER PRIMARY KEY, actor TEXT NOT NULL, updated_at TEXT NOT NULL, facilities INTEGER, tasks INTEGER, incidents INTEGER)');
 db.prepare('INSERT OR IGNORE INTO workspace VALUES(1,0,?,NULL)').run(JSON.stringify(empty()));
 const digest=createHash('sha256').update(token).digest();
 const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
 const read=()=>{const row=db.prepare('SELECT * FROM workspace WHERE id=1').get();return {revision:row.revision,updatedAt:row.updated_at,document:JSON.parse(row.body)}};
 return {
  close:()=>db.close(),
  async handle(request){
   const path=new URL(request.url).pathname;
   if(path==='/api/workspace/status'&&request.method==='GET')return json({configured:true,storage:'SQLite',mode:'manual_revision_sync'});
   if(!['/api/workspace','/api/workspace/audit'].includes(path))return json({error:'未知共享接口'},404);
   const supplied=request.headers.get('authorization')?.replace(/^Bearer /,'')||'';
   if(!timingSafeEqual(digest,createHash('sha256').update(supplied).digest()))return json({error:'共享口令无效'},401);
   const origin=request.headers.get('origin');
   if(origin&&origin!==new URL(request.url).origin)return json({error:'不允许跨站访问共享记录'},403);
   if(path.endsWith('/audit'))return request.method==='GET'?json({entries:db.prepare('SELECT * FROM audit ORDER BY revision DESC LIMIT 100').all()}):json({error:'方法不支持'},405);
   if(request.method==='GET')return json(read());
   if(request.method!=='PUT')return json({error:'方法不支持'},405);
   if(Number(request.headers.get('content-length')||0)>LIMIT)return json({error:'共享记录超过 4 MB，请导出图片后重试'},413);
   let body;try{const reader=request.body?.getReader();if(!reader)return json({error:'记录格式无效'},400);let bytes=0;const chunks=[];while(true){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(bytes>LIMIT){await reader.cancel();return json({error:'共享记录超过 4 MB'},413)}chunks.push(value)}body=JSON.parse(Buffer.concat(chunks).toString('utf8'))}catch{return json({error:'记录格式无效'},400)}
   if(!Number.isSafeInteger(body.revision)||body.revision<0||!string(body.actor,60)||!body.actor.trim()||!validDocument(body.document))return json({error:'请填写操作人，检查设施、工单及现场记录格式'},400);
   const now=new Date().toISOString();
   db.exec('BEGIN IMMEDIATE');
   try{
    const current=read();
    if(current.revision!==body.revision){db.exec('ROLLBACK');return json({error:'另一位组员已更新。请先备份本机记录，再载入共享版本并重新整理。',revision:current.revision},409)}
    const revision=current.revision+1;
    db.prepare('UPDATE workspace SET revision=?,body=?,updated_at=? WHERE id=1').run(revision,JSON.stringify(body.document),now);
    db.prepare('INSERT INTO audit VALUES(?,?,?,?,?,?)').run(revision,body.actor.trim(),now,body.document.workspace.facilities.length,body.document.workspace.tasks.length,body.document.incidents.length);
    db.exec('COMMIT');return json({revision,updatedAt:now});
   }catch{db.exec('ROLLBACK');return json({error:'共享存储失败，本机记录未被覆盖'},500)}
  }
 };
}
