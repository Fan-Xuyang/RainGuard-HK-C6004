import {locale,translate} from './i18n.mjs';
import {retrieve} from './retrieval.mjs';
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const PLAYBOOKS=[
 {id:'property',title:'物业排水巡查',description:'核对暴雨、水浸与现场排水情况，保留负责人和事实记录。',sources:['rain-warning','flood-prevention'],checks:['核对官方警告及观测时间','由合适人员核对排水口和低洼入口','记录实际积水或堵塞，不以区域雨量替代现场测量','填写责任人并提交人工复核']},
 {id:'outdoor',title:'户外作业交接',description:'结合暴雨、雷暴和恶劣天气工作安排，形成待人工确认的检查清单。',sources:['thunder','work-arrangements-code'],checks:['查阅官方雷暴及暴雨信息','核对雇主既定工作安排与实际交通情况','由负责人评估实际工作环境','人工确认后记录安排，不自动发布停工指令']},
 {id:'coastal',title:'沿岸设施值守',description:'区分潮位、风暴潮和现场水浸，核对实际沿岸设施。',sources:['storm-surge','cyclone-precautions'],checks:['核对官方热带气旋与风暴潮资料','记录潮位站与设施之间的位置差异','由现场负责人记录实际情况','明确潮位不是设施积水深度']},
 {id:'heat',title:'高温作业复核',description:'查阅天文台酷热提示与劳工处指引，记录具体作业条件。',sources:['hot-advisory','heat-stress-guide'],checks:['查阅当前官方高温提示及原始时间','核对实际工种、作业强度和环境','按官方指引及机构制度确认所需措施','由获授权负责人复核，模板不作医学诊断']},
 {id:'slope',title:'斜坡周边巡查',description:'核对山泥倾泻警告与官方资料，不凭气象数据推断单一斜坡稳定性。',sources:['landslip','rain-warning'],checks:['核对官方山泥倾泻及暴雨警告','明确天气数据不能判断具体斜坡稳定性','按机构安排记录实际观察与异常','由合适人员跟进现场核对']},
 {id:'handover',title:'台风前后交班',description:'把气旋警告、工作安排与现场核验串成可追溯的人工流程。',sources:['cyclone-service','cyclone-precautions','work-arrangements'],checks:['核对当前官方气旋信号和更新时间','查阅机构既定恶劣天气安排','记录实际设施检查和人员责任','恢复或调整安排须人工确认']},
];
export function bootCapabilities({state,openTask,toast}){
 const planner=document.querySelector('#planner');if(!planner)return;
 const panel=document.createElement('article');panel.className='panel padded playbook-panel';
 panel.innerHTML='<div class="section-toolbar"><div><span class="kicker">SCENARIO PLAYBOOKS</span><h2>把官方资料，变成可核对的行动。</h2><p class="subtle">人工核对模板，引用真实官方资料；不自动判断安全或替你批准行动。</p></div><button id="exportPlaybook" class="secondary">导出核对包</button></div><div class="playbook-grid">'+PLAYBOOKS.map(p=>`<button data-playbook="${p.id}" class="playbook-choice"><strong>${escape(p.title)}</strong><span>${escape(p.description)}</span></button>`).join('')+'</div><div id="playbookDetail"></div>';
 planner.prepend(panel);let selected=PLAYBOOKS[0],kb=[];const checks=new Map();
 function render(){
  const values=checks.get(selected.id)||selected.checks.map(()=>false);
  document.querySelector('#playbookDetail').innerHTML=`<div class="playbook-detail"><div><span class="kicker">HUMAN REVIEW REQUIRED</span><h3>${escape(selected.title)}</h3><p class="subtle">${escape(selected.description)}</p>${selected.checks.map((text,i)=>`<label class="playbook-check"><input type="checkbox" data-check="${i}" ${values[i]?'checked':''}><span>${escape(text)}</span></label>`).join('')}<button id="playbookDraft" class="primary">建立人工复核草稿</button></div><div><h3>官方依据</h3>${selected.sources.map(id=>kb.find(d=>d.id===id)).filter(Boolean).map(d=>`<a class="playbook-source" href="${escape(d.url)}" target="_blank" rel="noopener">${escape(d.title)} ↗<small>${escape(d.publisher)} · SHA-256 ${d.sha256.slice(0,12)}…</small></a>`).join('')}<p class="subtle">勾选只表示你记录了核对进度，不代表工作已经获批。检查记录仅保存在本次页面。</p></div></div>`;
  document.querySelectorAll('[data-check]').forEach(input=>input.onchange=()=>{values[Number(input.dataset.check)]=input.checked;checks.set(selected.id,values)});
  document.querySelector('#playbookDraft').onclick=()=>{openTask();document.querySelector('#taskTitle').value=translate(selected.title)+' · '+translate('人工核对草稿');document.querySelector('#taskRegion').value=state().region};
  document.querySelectorAll('[data-playbook]').forEach(b=>b.classList.toggle('selected',b.dataset.playbook===selected.id));
 }
 document.querySelectorAll('[data-playbook]').forEach(b=>b.onclick=()=>{selected=PLAYBOOKS.find(p=>p.id===b.dataset.playbook);render()});
 document.querySelector('#exportPlaybook').onclick=()=>{
  const payload={generatedAt:new Date().toISOString(),language:locale(),region:state().region,template:selected,checks:checks.get(selected.id)||selected.checks.map(()=>false),sources:selected.sources.map(id=>kb.find(d=>d.id===id)).filter(Boolean).map(({chunks,...d})=>d),observations:Object.entries(state().packets).map(([id,p])=>({id,origin:p.origin,receivedAt:p.receivedAt,sha256:p.sha256,error:p.error||null})),status:'unapproved-human-review-template'};
  const u=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='RainGuard-'+selected.id+'-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);
 };
 fetch('data/knowledge.json').then(r=>r.json()).then(p=>{kb=p.documents;render();if(dialog.open)results()}).catch(()=>toast('场景资料加载失败，请重试'));render();
 // One search entry connects the existing pages and verified source library.
 const trigger=document.createElement('button');trigger.className='global-search-trigger';trigger.textContent='⌕ 快速查找';trigger.setAttribute('aria-label','查找功能或官方资料');
 document.querySelector('.header-right').prepend(trigger);
 const dialog=document.createElement('dialog');dialog.className='command-dialog';dialog.innerHTML='<div class="command-heading"><h2>查找功能与资料</h2><button id="closeCommand" class="iconbutton" aria-label="关闭">×</button></div><input id="commandQuery" placeholder="搜索功能、暴雨、rainstorm…" aria-label="查找功能或官方资料"><div id="commandResults"></div>';document.body.append(dialog);
 const results=()=>{const query=document.querySelector('#commandQuery').value.trim();const pages=[...document.querySelectorAll('nav button[data-page]')].filter(b=>!query||b.textContent.toLowerCase().includes(query.toLowerCase()));document.querySelector('#commandResults').innerHTML=pages.map(b=>`<button data-command-page="${b.dataset.page}">${escape(b.textContent)}</button>`).join('')+(query?retrieve(query,kb,6).map(h=>`<a href="${escape(h.url)}" target="_blank" rel="noopener">${escape(h.title)} ↗<small>${escape(h.publisher)}</small></a>`).join(''):'');document.querySelectorAll('[data-command-page]').forEach(b=>b.onclick=()=>{document.querySelector(`nav button[data-page="${b.dataset.commandPage}"]`).click();dialog.close()})};
 const show=()=>{results();dialog.showModal();document.querySelector('#commandQuery').focus()};trigger.onclick=show;document.querySelector('#closeCommand').onclick=()=>dialog.close();document.querySelector('#commandQuery').oninput=results;
 document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();show()}});
}
