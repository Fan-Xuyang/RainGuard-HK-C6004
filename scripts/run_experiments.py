"""Fixed-protocol station experiments on the frozen dataset; never tune on test data."""
from pathlib import Path
import csv,datetime,hashlib,json,platform
import numpy as np
import sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss,precision_score,recall_score,f1_score,confusion_matrix

ROOT=Path(__file__).resolve().parents[1]
FEATURES=['log1p_lag1','log1p_lag2','log1p_lag3','log1p_past7_total','past7_wetdays','sin_dayofyear','cos_dayofyear']
out={'generated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'target':'Next-day daily rainfall >=25 mm (course label, not flood or warning probability)',
     'splits':{'train':'2000-2019','validation':'2020-2022','test':'2023-2025','excluded':'2026 onward'},
     'versions':{'python':platform.python_version(),'numpy':np.__version__,'scikit_learn':sklearn.__version__},
     'features':FEATURES,'source_hashes':{},'results':[],
     'protocol':'Models fixed before test. Validation F1 chooses threshold from [.1,.15,.2,.25,.3,.4,.5]. No parameter search. AP is average_precision_score, not trapezoidal PR area.',
     'rf_parameters':{'n_estimators':120,'max_depth':8,'min_samples_leaf':10,'random_state':42}}

def metrics(y,p,t):
 predicted=p>=t
 return {'roc_auc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p)),
    'brier':float(brier_score_loss(y,p)),'precision':float(precision_score(y,predicted,zero_division=0)),
    'recall':float(recall_score(y,predicted,zero_division=0)),'f1':float(f1_score(y,predicted,zero_division=0)),
    'confusion_tn_fp_fn_tp':confusion_matrix(y,predicted,labels=[0,1]).ravel().tolist()}

for policy in ['exclude','zero']:
 path=ROOT/f'datasets/RainGuard_HK_Dataset/training/core_features_trace_{policy}.csv'
 if not path.exists():raise SystemExit('Download the full dataset first: python scripts/download_dataset.py')
 out['source_hashes'][path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
 with path.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
 for station in ['HKO','LFS','SHA']:
  groups={s:[r for r in rows if r['station']==station and r['split']==s] for s in ['train','validation','test']}
  X={s:np.array([[float(r[f]) for f in FEATURES] for r in g]) for s,g in groups.items()}
  y={s:np.array([int(r['target_ge25mm']) for r in g]) for s,g in groups.items()}
  assert all(len(np.unique(labels))==2 for labels in y.values())
  for s,group in groups.items():
   assert all(r['feature_asof_date']<r['target_date'] for r in group)
   assert all(r['target_date']<'2026-01-01' for r in group)
  prevalence=y['train'].mean()
  months={m:np.mean([int(r['target_ge25mm']) for r in groups['train'] if int(r['target_date'][5:7])==m]) for m in range(1,13)}
  probabilities={
   'train_prevalence':{s:np.full(len(groups[s]),prevalence) for s in ['validation','test']},
   'seasonal_prevalence':{s:np.array([months[int(r['target_date'][5:7])] for r in groups[s]]) for s in ['validation','test']},
   'persistence':{s:np.array([int(float(r['lag1_rainfall_mm'])>=25) for r in groups[s]],dtype=float) for s in ['validation','test']}}
  classifiers={'logistic_regression':make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=2000,random_state=42)),
     'random_forest':RandomForestClassifier(**out['rf_parameters'],n_jobs=2)}
  for name,model in classifiers.items():
   model.fit(X['train'],y['train'])
   probabilities[name]={s:model.predict_proba(X[s])[:,1] for s in ['validation','test']}
  for name,p in probabilities.items():
   threshold=.5 if name=='persistence' else max([.1,.15,.2,.25,.3,.4,.5],key=lambda t:f1_score(y['validation'],p['validation']>=t,zero_division=0))
   result={'station':station,'trace_policy':policy,'model':name,'threshold':threshold,'counts':{s:len(g) for s,g in groups.items()},
       'test_positives':int(y['test'].sum()),'validation':metrics(y['validation'],p['validation'],threshold),'test':metrics(y['test'],p['test'],threshold)}
   out['results'].append(result)
  print(station,policy,'completed fixed train/validation/test comparison',flush=True)

dest=ROOT/'hk-web/data/experiments.json';dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
report=['# RainGuard HK 固定时间划分实验结果','',
 '数据来源：2026-10-12 官方数据包，三站日雨量；目标为次日总雨量≥25 mm。模型使用七维历史/日历特征，训练2000–2019、验证2020–2022、测试2023–2025。2026年不参与模型选择。',
 '', '随机森林参数和逻辑回归配置在查看测试结果前固定，未做测试集参数搜索。阈值依据验证集F1选择；完整参数、版本、输入CSV哈希、计数和混淆矩阵见 hk-web/data/experiments.json。AP 使用 sklearn average_precision_score。',
 '', '| 微量雨策略 | 站点 | 方法 | 测试 AP | ROC-AUC | Brier | F1 | 召回 |', '|---|---|---|---:|---:|---:|---:|---:|']
for r in out['results']:
 m=r['test'];report.append(f'| {r["trace_policy"]} | {r["station"]} | {r["model"]} | {m["average_precision"]:.3f} | {m["roc_auc"]:.3f} | {m["brier"]:.3f} | {m["f1"]:.3f} | {m["recall"]:.3f} |')
report+=['','该结果是一次预先固定协议的离线实验，未报告统计显著性。两个微量雨策略的可用目标日期集合不同，不能把指标变化直接解释为微量雨处理的因果效果。随机森林不一定优于简单模型，请比较实际结果。','',
 '本实验没有真实水浸/损失标签，不能给出物业水浸概率或现场安全结论；也没有完成助手人工问答准确率评价。历史数据有月度发布滞后，不能将离线模型输出冒充今天实时预测。']
(ROOT/'docs/EXPERIMENTS.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print('Saved 30 measured model/station/policy results with source hashes and limitations.')
