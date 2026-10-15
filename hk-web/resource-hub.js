export async function bootResourceHub(){
 let lastSeries=null;
 const exportButton=document.createElement('button');exportButton.className='secondary';exportButton.id='resourceCSV';exportButton.textContent='导出当前系列 CSV';exportButton.disabled=true;document.querySelector('#resourceSeries')?.before(exportButton);
 exportButton.onclick=()=>{if(!lastSeries)return;const rows=[['date','value','unit','quality_status','completeness','source_id'],...lastSeries.rows.map(r=>[r.date,r.value??'',r.unit,r.quality_status,r.completeness,r.source_id])];const csv='\ufeff'+rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');const u=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=u;a.download=lastSeries.station+'-'+lastSeries.variable+'-official.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
 const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 if(!$('#resourceMetrics'))return;
 try{
  const r=await fetch('data/extended-catalog.json');if(!r.ok)throw Error('扩展目录尚未生成');const catalog=await r.json(),summary=catalog.summary;
  $('#resourceMetrics').innerHTML=[['总气象日记录',summary.combined_climate_rows.toLocaleString()],['新增记录',summary.additional_climate_rows.toLocaleString()],['新增站点变量系列',summary.additional_station_variable_series],['官方知识资料',summary.combined_knowledge_documents]].map(([label,value])=>`<article class="resource-metric"><small>${label}</small><strong>${value}</strong></article>`).join('');
  const stations=[...new Set(catalog.coverage.map(c=>c.station))].sort();$('#resourceStation').innerHTML=stations.map(s=>`<option value="${s}">${s}</option>`).join('');
  const renderCoverage=()=>{const query=$('#resourceSearch').value.trim().toUpperCase(),rows=catalog.coverage.filter(c=>!query||c.station.includes(query)||c.variable.includes(query));$('#resourceCoverage').innerHTML='<table><thead><tr><th>站点</th><th>变量</th><th>记录数</th><th>最早日期</th><th>最新日期</th><th>缺测</th></tr></thead><tbody>'+rows.map(c=>`<tr><td>${esc(c.station)}</td><td>${esc(c.variable)}</td><td>${c.rows.toLocaleString()}</td><td>${esc(c.min_date)}</td><td>${esc(c.max_date)}</td><td>${c.missing}</td></tr>`).join('')+'</tbody></table>'};
  $('#resourceSearch').oninput=renderCoverage;renderCoverage();
  $('#resourceQuery').onclick=async()=>{
   $('#resourceSeries').textContent='正在读取官方历史系列…';lastSeries=null;exportButton.disabled=true;
   try{
    const station=$('#resourceStation').value,variable=$('#resourceVariable').value,year=Number($('#resourceYear').value);
    const r=await fetch('/api/climate/series?'+new URLSearchParams({station,variable,from:year,to:year}));const series=await r.json();if(!r.ok)throw Error(series.error);
    lastSeries=series;exportButton.disabled=false;const rows=series.rows,values=rows.filter(p=>p.value!==null&&p.completeness==='C').map(p=>p.value);
    if(!values.length)throw Error('该站点、变量及年份没有完整数值记录，请更换条件');
    const low=Math.min(...values),high=Math.max(...values),span=Math.max(high-low,1);let path='',active=false;
    for(let i=0;i<rows.length;i++){const p=rows[i];if(p.value===null||p.completeness!=='C'){active=false;continue}path+=(active?' L':' M')+(20+i*680/Math.max(rows.length-1,1)).toFixed(1)+' '+(190-(p.value-low)/span*155).toFixed(1);active=true}
    $('#resourceSeries').innerHTML=`<h3>${esc(station)} · ${esc(variable)} · ${year}</h3><p class="subtle">${rows.length}条 · 完整有效${values.length}条 · ${esc(rows[0].unit)} · 缺测不连线</p><svg viewBox="0 0 720 215" preserveAspectRatio="none" class="climate-chart" role="img" aria-label="官方历史日系列折线图"><line x1="20" y1="195" x2="700" y2="195" stroke="#d5e2e7"/><path d="${path}" fill="none" stroke="#2b7887" stroke-width="2"/><text x="24" y="23" fill="#647884">${high.toFixed(1)}</text><text x="24" y="210" fill="#647884">${low.toFixed(1)}</text></svg><p class="subtle">${esc(series.limitation)}</p><p class="subtle"><a href="${esc(catalog.coverage.find(c=>c.station===station&&c.variable===variable)?.source_url||'')}" target="_blank" rel="noopener">官方原始CSV ↗</a></p>`;
   }catch(e){$('#resourceSeries').textContent=e.message}
  };
 }catch(e){$('#resourceMetrics').textContent=e.message}
}
