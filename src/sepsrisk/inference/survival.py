import json
import numpy as np
import pandas as pd
from ..config import load_yaml
from ..utils import utcnow
from ..storage.analytics import query_df


def readiness(con,root=None):
    cfg=load_yaml('project.yaml',root)['inference'];ne=int(con.execute('SELECT count(*) FROM dim_entity').fetchone()[0]);np_=int(con.execute('SELECT count(distinct ruc) FROM entity_event WHERE adverse=1').fetchone()[0])
    return {'enabled':ne>=cfg['minimum_entities'] and np_>=cfg['minimum_positive_events'],'n_entities':ne,'n_positive_events':np_,'minimum_positive_events':cfg['minimum_positive_events'],'minimum_entities':cfg['minimum_entities']}

def _panel(con,features):
    quoted=','.join("'"+str(x).replace("'","''")+"'" for x in features);d=query_df(con,f'SELECT cutoff_date,ruc,feature,value FROM fact_feature WHERE feature IN ({quoted})')
    return d.pivot_table(index=['cutoff_date','ruc'],columns='feature',values='value').reset_index() if not d.empty else d

def fit_if_ready(con,root=None):
    gate=readiness(con,root);cfg=load_yaml('project.yaml',root)['inference'];now=utcnow();con.execute('DELETE FROM fact_risk_estimate')
    if not gate['enabled']:return {**gate,'fitted':False,'reason':'No supera gate mínimo'}
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.metrics import roc_auc_score,brier_score_loss
    features=cfg['model_features'];p=_panel(con,features);ev=query_df(con,'SELECT ruc,min(event_date) event_date FROM entity_event WHERE adverse=1 GROUP BY ruc')
    p['cutoff_date']=pd.to_datetime(p.cutoff_date);ev['event_date']=pd.to_datetime(ev.event_date);p=p.merge(ev,on='ruc',how='left');p=p[p.event_date.isna() | (p.cutoff_date<=p.event_date)].copy();p['next_month']=p.cutoff_date+pd.offsets.MonthEnd(1);p['y']=((p.event_date.notna())&(p.event_date>p.cutoff_date)&(p.event_date<=p.next_month)).astype(int);p=p.dropna(subset=features)
    if p.y.sum()<cfg['minimum_positive_events']:return {**gate,'fitted':False,'reason':'Filas evento insuficientes tras completar covariables'}
    X=p[features].astype(float).copy();med=X.median();iqr=(X.quantile(.75)-X.quantile(.25)).replace(0,1);X=(X-med)/iqr;y=p.y.values;groups=p.ruc.values
    splits=max(2,min(5,int(p[p.y==1].ruc.nunique())));cv=StratifiedGroupKFold(n_splits=splits,shuffle=True,random_state=42);oof=np.full(len(p),np.nan)
    for tr,te in cv.split(X,y,groups):
        m=LogisticRegression(max_iter=2000,class_weight='balanced',C=.5,solver='liblinear').fit(X.iloc[tr],y[tr]);oof[te]=m.decision_function(X.iloc[te])
    ok=np.isfinite(oof);cal=LogisticRegression(solver='liblinear').fit(oof[ok].reshape(-1,1),y[ok]);oof_p=cal.predict_proba(oof[ok].reshape(-1,1))[:,1];auc=roc_auc_score(y[ok],oof_p);brier=brier_score_loss(y[ok],oof_p)
    base=LogisticRegression(max_iter=2000,class_weight='balanced',C=.5,solver='liblinear').fit(X,y);latest=_panel(con,features);latest['cutoff_date']=pd.to_datetime(latest.cutoff_date);latest=latest.sort_values('cutoff_date').groupby('ruc').tail(1).dropna(subset=features);XL=(latest[features]-med)/iqr;haz=cal.predict_proba(base.decision_function(XL).reshape(-1,1))[:,1]
    version='hazard-logit-platt-v0.9';rows=[]
    for row,h in zip(latest.itertuples(index=False),haz):
        for horizon in cfg['horizons_months']:rows.append((row.cutoff_date.date().isoformat(),str(row.ruc),int(horizon),float(1-(1-float(h))**int(horizon)),None,None,version,now))
    out=pd.DataFrame(rows,columns=['cutoff_date','ruc','horizon_months','probability','lower_ci','upper_ci','model_version','calibrated_at'])
    if not out.empty:con.register('_risk',out);con.execute('INSERT INTO fact_risk_estimate SELECT * FROM _risk');con.unregister('_risk')
    metrics={'oof_auc':float(auc),'oof_brier':float(brier),'rows':len(p),'events':int(y.sum()),'features':features};return {**gate,'fitted':True,'metrics':metrics}

def record_readiness(con,root=None):return fit_if_ready(con,root)
