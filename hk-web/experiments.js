export async function bootExperiments(){
 const $=s=>document.querySelector(s);
 if(!$('#experimentResults'))return;
 try{
  const response=await fetch('data/experiments.json');if(!response.ok)throw Error('无法读取实验结果');
  const experiment=await response.json();
  const labels={train_prevalence:'训练集发生率基线',seasonal_prevalence:'月度发生率基线',persistence:'持续性基线',logistic_regression:'逻辑回归',random_forest:'随机森林'};
  const render=()=>{
   const rows=experiment.results.filter(r=>r.station===$('#experimentStation').value&&r.trace_policy===$('#experimentPolicy').value);
   if(!rows.length)throw Error('该组合没有已完成的实验');
   const c=rows[0].counts;
   $('#experimentCounts').textContent=`训练 ${c.train.toLocaleString()} · 验证 ${c.validation.toLocaleString()} · 测试 ${c.test.toLocaleString()}（正样本 ${rows[0].test_positives}）`;
   $('#experimentResults').innerHTML='<table><thead><tr><th>方法</th><th>测试 AP ↑</th><th>ROC-AUC ↑</th><th>F1 ↑</th><th>召回 ↑</th><th>Brier ↓</th><th>验证阈值</th></tr></thead><tbody>'+rows.map(r=>'<tr><td>'+labels[r.model]+'</td>'+['average_precision','roc_auc','f1','recall','brier'].map(k=>'<td>'+Number(r.test[k]).toFixed(3)+'</td>').join('')+'<td>'+Number(r.threshold).toFixed(2)+'</td></tr>').join('')+'</tbody></table>';
   $('#experimentProvenance').textContent='输入文件 SHA-256：'+experiment.source_hashes['datasets/RainGuard_HK_Dataset/training/core_features_trace_'+$('#experimentPolicy').value+'.csv'];
  };
  $('#experimentStation').onchange=render;$('#experimentPolicy').onchange=render;
  $('#experimentDownload').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(experiment,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='RainGuard-fixed-protocol-experiments.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
  render();
 }catch(e){$('#experimentResults').textContent=e.message+'；没有填入示意结果。'}
}
