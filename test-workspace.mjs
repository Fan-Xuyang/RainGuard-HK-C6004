import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createWorkspaceStore,validDocument} from './workspace-store.mjs';
const dir=mkdtempSync(join(tmpdir(),'rainguard-workspace-')),path=join(dir,'records.sqlite');
const token='test-only-workspace-password-123456';
let store=createWorkspaceStore({path,token});
const request=(method='GET',body,extra={})=>new Request('http://localhost/api/workspace',{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json',...extra},...(body?{body:JSON.stringify(body)}:{})});
try{
 assert.equal((await store.handle(request('GET',null,{Authorization:'Bearer invalid'}))).status,401);
 assert.equal((await store.handle(request('GET',null,{origin:'https://untrusted.example'}))).status,403);
 const initial=await (await store.handle(request())).json();assert.equal(initial.revision,0);
 const document=initial.document;
 document.workspace.facilities.push({id:'real-inspection-test',name:'测试验证专用（非真实物业）',region:'沙田',notes:''});
 assert(validDocument(document));
 assert.equal((await store.handle(request('PUT',{revision:0,actor:'tester',document}))).status,200);
 // Two clients read the same revision. Only the first write can succeed.
 const a=await (await store.handle(request())).json(),b=await (await store.handle(request())).json();
 assert.equal((await store.handle(request('PUT',{revision:a.revision,actor:'client-a',document:a.document}))).status,200);
 assert.equal((await store.handle(request('PUT',{revision:b.revision,actor:'client-b',document:b.document}))).status,409);
 const invalid=structuredClone(document);invalid.workspace.facilities=[null];
 assert.equal((await store.handle(request('PUT',{revision:2,actor:'tester',document:invalid}))).status,400);
 const unfinished=structuredClone(document);unfinished.workspace.tasks=[{id:'task-test',title:'Test workflow',region:'沙田',status:'done',owner:'',note:'',checks:[false,false,false],logs:[],evidence:{warnings:[]}}];
 assert.equal((await store.handle(request('PUT',{revision:2,actor:'tester',document:unfinished}))).status,400);
 assert.equal((await store.handle(request('PUT',{revision:2,actor:'',document}))).status,400);
 const huge=new Request('http://localhost/api/workspace',{method:'PUT',headers:{Authorization:'Bearer '+token},body:' '.repeat(4_000_001)});
 assert.equal((await store.handle(huge)).status,413);
 store.close();store=createWorkspaceStore({path,token});
 const persisted=await (await store.handle(request())).json();assert.equal(persisted.revision,2);assert.equal(persisted.document.workspace.facilities.length,1);
 const audit=await (await store.handle(new Request('http://localhost/api/workspace/audit',{headers:{Authorization:'Bearer '+token}}))).json();assert.equal(audit.entries.length,2);assert.equal(audit.entries[0].actor,'client-a');
 console.log('PASS: shared auth, cross-origin rejection, schema/size limits, concurrent revision conflict, SQLite restart persistence and audit.');
}finally{store.close();assert(dir.startsWith(join(tmpdir(),'rainguard-workspace-')));rmSync(dir,{recursive:true,force:true})}
