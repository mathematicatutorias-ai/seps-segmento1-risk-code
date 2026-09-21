import json
import numpy as np
import pandas as pd
from ..config import load_yaml
from ..utils import utcnow
from ..storage.analytics import query_df

DIRECTIONS={'delinquency_ratio':'higher_bad','coverage_ratio':'lower_bad','liquidity_ratio':'lower_bad','deposit_growth_3m':'lower_bad','equity_assets_ratio':'lower_bad'}

def resolve_focus_entity(con,root=None):
    cfg=load_yaml('project.yaml',root)['focus_entity'];q=str(cfg.get('query','')).upper().strip();d=query_df(con,'SELECT * FROM dim_entity')
    if d.empty:return None
    h=d[d.entity_name_norm.fillna('').str.contains(q,regex=False,na=False)].copy()
    if h.empty:return None
    counts=query_df(con,'SELECT ruc,count(distinct cutoff_date) n FROM fact_eeff GROUP BY ruc');h=h.merge(counts,on='ruc',how='left');row=h.sort_values('n').iloc[-1]
    return {'ruc':str(row.ruc),'entity_name':str(row.entity_name),'entity_name_norm':str(row.entity_name_norm),'first_seen':str(row.first_seen),'last_seen':str(row.last_seen)}

def build_signals(con,root=None):
    d=query_df(con,'SELECT cutoff_date,ruc,feature,value FROM fact_feature ORDER BY ruc,cutoff_date')
    if d.empty:
        con.execute('DELETE FROM fact_signal');return {'entities':0,'signals':0}
    now=utcnow();rows=[];entities=0
    for ruc,g in d.groupby('ruc'):
        p=g.pivot(index='cutoff_date',columns='feature',values='value').sort_index();wrote=False
        for f,di in DIRECTIONS.items():
            if f not in p:continue
            s=p[f].dropna();hist=s.iloc[:-1].tail(24)
            if len(hist)<6:continue
            med=float(hist.median());mad=float(np.median(np.abs(hist-med))) or float(hist.std()) or 1.0
            z=(float(s.iloc[-1])-med)/(1.4826*mad);score=z if di=='higher_bad' else -z
            rows.append((str(s.index[-1]),str(ruc),f,float(s.iloc[-1]),float(score),di,json.dumps({'median_hist':med,'robust_z':z,'window_months':int(len(hist))}),now));wrote=True
        entities+=int(wrote)
    out=pd.DataFrame(rows,columns=['cutoff_date','ruc','signal','value','score','direction','detail','calculated_at'])
    con.execute('DELETE FROM fact_signal')
    if not out.empty:
        con.register('_signals',out);con.execute('INSERT INTO fact_signal SELECT * FROM _signals');con.unregister('_signals')
    return {'entities':entities,'signals':len(out)}
