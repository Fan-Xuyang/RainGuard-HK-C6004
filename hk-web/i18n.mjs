import {toSimple} from './simplify.mjs';
export const LANGUAGES = {'zh-CN':'简体中文','yue-HK':'粵語','en':'English'};
let language='zh-CN', catalog={}, started=false, observer, readyPromise, phrases;
const originals=new WeakMap(), attrs=new WeakMap();
const excluded='script,style,textarea,pre,code,[data-original],[data-i18n-skip],.chat-bubble,.knowledge-hit p,.source-card p,.bodytext,.leaflet-container';
export const locale=()=>language;
export function canonicalText(text){return toSimple(String(text)).replace(/\s+/g,' ').trim();}
export function templateText(text){let values=[];const key=canonicalText(text).replace(/\d+(?:[.,:/–-]\d+)*/g,v=>{values.push(v);return '{{'+(values.length-1)+'}}'});return {key,values};}
export function translate(text, target=language){
  const raw=String(text??''), normalized=canonicalText(raw);
  if(!normalized || target==='zh-CN')return toSimple(raw);
  const exact=catalog[normalized]?.[target];
  if(exact)return raw.replace(raw.trim(),exact);
  const {key,values}=templateText(raw), pattern=catalog[key]?.[target];
  if(pattern)return pattern.replace(/\{\{(\d+)\}\}/g,(_,n)=>values[n]??'');
  if(!phrases){const keys=Object.keys(catalog).filter(k=>/[\u3400-\u9fff]/.test(k)&&!k.includes('{{')&&k.length>=2).sort((a,b)=>b.length-a.length);phrases=keys.length?new RegExp(keys.map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|'),'g'):null;}
  return phrases?toSimple(raw).replace(phrases,key=>catalog[key]?.[target]||key):raw;
}
function textNode(node){
  if(node.parentElement?.closest(excluded))return;
  const previous=originals.get(node), current=node.nodeValue;
  if(previous?.language===language&&current===previous.rendered)return;
  const original=previous && current===previous.rendered?previous.original:current;
  const rendered=translate(original);
  originals.set(node,{original,rendered,language});
  if(current!==rendered)node.nodeValue=rendered;
}
function visit(root){
  if(root.nodeType===3){textNode(root);return}
  if(root.nodeType!==1||(root.matches(excluded)&&root.tagName!=='TEXTAREA'))return;
  if(root.tagName==='OPTION'&&!root.hasAttribute('value'))root.setAttribute('value',root.textContent);
  let saved=attrs.get(root)||{};
  for(const name of ['placeholder','title','aria-label']){
    if(!root.hasAttribute(name))continue;
    const now=root.getAttribute(name), old=saved[name];
    const original=old&&now===old.rendered?old.original:now, rendered=translate(original);
    saved[name]={original,rendered};if(now!==rendered)root.setAttribute(name,rendered);
  }
  attrs.set(root,saved);
  if(root.tagName!=='TEXTAREA')for(const child of [...root.childNodes])visit(child);
}
function apply(){
  observer?.disconnect();visit(document.body);document.documentElement.lang=language;
  for(const select of document.querySelectorAll('[data-language-picker]'))select.value=language;
  observer?.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','title','aria-label']});
}
export function setLocale(value){
  language=Object.hasOwn(LANGUAGES,value)?value:'zh-CN';
  try{localStorage.setItem('rainguard-language',language)}catch{}
  apply();window.dispatchEvent(new CustomEvent('rainguard:language',{detail:{locale:language}}));
}
export function bootI18n({catalogUrl='data/locales.json'}={}){
  if(started)return readyPromise;
  started=true;
  try{language=localStorage.getItem('rainguard-language')||'zh-CN'}catch{}
  if(!Object.hasOwn(LANGUAGES,language))language='zh-CN';
  readyPromise=(async()=>{
    try{const r=await fetch(catalogUrl);if(!r.ok)throw Error('catalog');catalog=(await r.json()).messages||{}}catch{language='zh-CN'}
    for(const host of document.querySelectorAll('[data-language-host]')){
      const label=document.createElement('label');label.className='language-control';label.setAttribute('data-i18n-skip','');
      label.innerHTML='<span aria-hidden="true">◎</span><select data-language-picker aria-label="Language / 语言 / 語言">'+Object.entries(LANGUAGES).map(([value,name])=>`<option value="${value}">${name}</option>`).join('')+'</select>';
      host.append(label);label.querySelector('select').onchange=e=>setLocale(e.target.value);
    }
    let queued=false;
    observer=new MutationObserver(()=>{if(queued)return;queued=true;queueMicrotask(()=>{queued=false;apply()})});
    apply();return language;
  })();
  return readyPromise;
}
