"""Reproducible next-day >=25mm classifier. Train/validation/test are time-separated."""
import pathlib,json,numpy as np,datetime
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss,f1_score,confusion_matrix,precision_score,recall_score
root=pathlib.Path(__file__).parent/'hk-web'/'data';history=json.loads((root/'history.json').read_text(encoding='utf8'));models={}
for code,station in history.items():
    records=station['records'];samples=[]
    for i in range(7,len(records)):
        group=records[i-7:i+1]
        if any(p['value'] is None or p['complete']!='C' for p in group):continue
        dates=[datetime.date.fromisoformat(p['date']) for p in group]
        if any((b-a).days!=1 for a,b in zip(dates,dates[1:])):continue
        v=[p['value'] for p in group[:-1]];d=dates[-1];angle=d.timetuple().tm_yday/365.25*2*np.pi
        x=[np.log1p(v[-1]),np.log1p(v[-2]),np.log1p(v[-3]),np.log1p(sum(v)),sum(n>=1 for n in v),np.sin(angle),np.cos(angle)]
        samples.append((group[-1]['date'],x,int(group[-1]['value']>=25),group[-1]['value']))
    train=[s for s in samples if s[0]<'2020-01-01'];val=[s for s in samples if '2020-01-01'<=s[0]<'2023-01-01'];test=[s for s in samples if '2023-01-01'<=s[0]<'2026-01-01']
    model=make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=2000,random_state=42));model.fit([s[1] for s in train],[s[2] for s in train])
    vp=model.predict_proba([s[1] for s in val])[:,1];threshold=max([.1,.15,.2,.25,.3,.4,.5],key=lambda t:f1_score([s[2] for s in val],vp>=t,zero_division=0))
    tp=model.predict_proba([s[1] for s in test])[:,1];truth=np.array([s[2] for s in test]);pred=tp>=threshold
    monthly={m:np.mean([s[2] for s in train if int(s[0][5:7])==m]) for m in range(1,13)};baseline=np.array([monthly[int(s[0][5:7])] for s in test])
    scaler=model[0];classifier=model[1]
    models[code]={'name':station['name'],'target':'次日站點日總雨量 ≥25 mm（課程自訂分類）','train_range':['2000-01-01','2019-12-31'],'validation_range':['2020-01-01','2022-12-31'],'test_range':['2023-01-01','2025-12-31'],'counts':{'train':len(train),'validation':len(val),'test':len(test),'test_positive':int(truth.sum())},'threshold':threshold,'metrics':{'roc_auc':roc_auc_score(truth,tp),'pr_auc':average_precision_score(truth,tp),'brier':brier_score_loss(truth,tp),'baseline_brier':brier_score_loss(truth,baseline),'precision':precision_score(truth,pred,zero_division=0),'recall':recall_score(truth,pred,zero_division=0),'f1':f1_score(truth,pred,zero_division=0)},'confusion':confusion_matrix(truth,pred).tolist(),'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),'coef':classifier.coef_[0].tolist(),'intercept':float(classifier.intercept_[0]),'features':['log1p lag1','log1p lag2','log1p lag3','log1p past7 total','past7 wetdays','sin dayofyear','cos dayofyear'],'predictions':[{'date':s[0],'actual_mm':s[3],'label':s[2],'probability':float(p),'predicted':bool(p>=threshold)} for s,p in zip(test,tp)]}
(root/'models.json').write_text(json.dumps(models,ensure_ascii=False),encoding='utf8')
print(json.dumps({k:{'counts':v['counts'],'metrics':v['metrics']} for k,v in models.items()}))
