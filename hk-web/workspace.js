export function bootWorkspace({getDocument,setDocument,toast}){
 const $=s=>document.querySelector(s);
 if(!$('#sharedWorkspace'))return;
 let revision=null,busy=false;
 const status=s=>$('#workspaceStatus').textContent=s;
 const headers=()=>({'Content-Type':'application/json',Authorization:'Bearer '+$('#workspaceToken').value});
 const backup=()=>{
  const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify({exportedAt:new Date().toISOString(),document:getDocument()},null,2)],{type:'application/json'}));
  a.href=url;a.download='RainGuard-local-before-sync.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 async function perform(action){
  if(busy)return;
  if(!$('#workspaceToken').value)return toast('请填写组内共享口令');
  busy=true;
  try{
   if(action==='save'&&revision===null)throw Error('先连接并读取版本号，再上传本机记录');
   const method=action==='save'?'PUT':'GET';
   const r=await fetch('/api/workspace',{method,headers:headers(),...(method==='PUT'?{body:JSON.stringify({revision,actor:$('#workspaceActor').value.trim(),document:getDocument()})}:{})});
   const p=await r.json();if(!r.ok)throw Error(p.error||'共享服务不可用');
   if(action==='connect'&&p.revision>0&&revision!==p.revision){revision=null;status(`共享已有版本 ${p.revision}。本机数据未改变；请先备份并载入共享记录，再编辑上传。`);return}
   revision=p.revision;
   if(action==='load'){backup();setDocument(p.document);toast('已下载本机备份并载入共享记录')}
   status(`已连接 · 共享版本 ${revision}${p.updatedAt?' · 更新 '+new Date(p.updatedAt).toLocaleString('zh-CN',{timeZone:'Asia/Hong_Kong'})+' HKT':''}${action==='connect'?' · 本机数据未改变':''}`);
  }catch(e){status(e.message);toast(e.message)}finally{busy=false}
 }
 $('#workspaceConnect').onclick=()=>perform('connect');
 $('#workspaceLoad').onclick=()=>perform('load');
 $('#workspaceSave').onclick=()=>perform('save');
 $('#workspaceDisconnect').onclick=()=>{revision=null;$('#workspaceToken').value='';status('已断开，本机记录保留')};
 // Password remains only in the current input; do not persist it in browser storage.
 fetch('/api/workspace/status').then(r=>r.json()).then(s=>status(s.configured?'共享服务可用，请输入口令连接':'当前服务未配置共享存储，仍使用本机记录')).catch(()=>status('共享服务不可用，仍使用本机记录'));
}
