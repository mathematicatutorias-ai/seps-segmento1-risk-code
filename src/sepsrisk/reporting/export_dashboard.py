from pathlib import Path
import json,math,os,re
import numpy as np
import pandas as pd
from ..storage.analytics import query_df
from ..config import load_yaml,project_root
from ..utils import utcnow
from ..inference.signals import resolve_focus_entity
from ..inference.survival import readiness


def safe(v):
    if v is None:return None
    if isinstance(v,(float,np.floating)) and (math.isnan(float(v)) or math.isinf(float(v))):return None
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,)):return float(v)
    return v


def _records(df,cols=None):
    if cols is not None:df=df[cols]
    return [{k:safe(v) for k,v in x.items()} for x in df.to_dict('records')]


def _atomic_write(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(text,encoding='utf-8')
    os.replace(tmp,path)


DIRECTIONS={
    'delinquency_ratio':'lower',
    'coverage_ratio':'higher',
    'liquidity_ratio':'higher',
    'deposit_growth_3m':'higher',
    'equity_assets_ratio':'higher',
    'roa_proxy':'higher',
}


def _percentiles(features,ruc):
    if features.empty:return {}
    target=features[features.ruc==ruc].sort_values('cutoff_date').groupby('feature').tail(1)
    out={}
    for row in target.itertuples(index=False):
        pool=features[(features.feature==row.feature)&(features.cutoff_date==row.cutoff_date)].value.dropna().astype(float)
        if pool.empty:continue
        raw=float((pool<=float(row.value)).mean()*100)
        favorable=100-raw if DIRECTIONS.get(row.feature)=='lower' else raw
        out[row.feature]={'raw_percentile':raw,'favorable_percentile':favorable,'risk_percentile':100-favorable,'n':int(len(pool)),'cutoff_date':row.cutoff_date}
    return out


def _risk_benchmarks(risk):
    if risk.empty:return []
    rows=[]
    for (date,h),g in risk.groupby(['cutoff_date','horizon_months']):
        v=g.probability.dropna().astype(float)
        if len(v):rows.append({'cutoff_date':date,'horizon_months':int(h),'q25':float(v.quantile(.25)),'median':float(v.median()),'q75':float(v.quantile(.75)),'n':int(len(v))})
    return rows


def _risk_index_frame(features,cfg):
    """Relative 0–100 index from contemporaneous Segmento 1 percentiles.

    This is intentionally *not* a probability.  It is used only when the supervised
    event model has not been calibrated.  Each configured feature is converted to an
    adverse percentile within the same cutoff date; available weights are renormalised.
    """
    rcfg=cfg.get('dashboard',{}).get('risk_index',{})
    weights={str(k):float(v) for k,v in (rcfg.get('weights') or {}).items() if float(v)>0}
    if features.empty or not weights:return pd.DataFrame(columns=['cutoff_date','ruc','risk_index'])
    d=features[features.feature.astype(str).isin(weights)].copy()
    if d.empty:return pd.DataFrame(columns=['cutoff_date','ruc','risk_index'])
    d['cutoff_date']=d['cutoff_date'].astype(str)
    d['ruc']=d['ruc'].astype(str)
    d['feature']=d['feature'].astype(str)
    d['value']=pd.to_numeric(d.value,errors='coerce')
    d=d.dropna(subset=['value'])
    if d.empty:return pd.DataFrame(columns=['cutoff_date','ruc','risk_index'])
    # Defensive collapse in case an upstream source contains duplicates for a feature.
    d=d.groupby(['cutoff_date','ruc','feature'],as_index=False).value.mean()
    # percentile rank inside each date+feature; average ranks are deterministic on ties.
    d['raw_pct']=d.groupby(['cutoff_date','feature'])['value'].rank(pct=True,method='average')*100.0
    d['risk_pct']=d.apply(lambda x:100.0-x.raw_pct if DIRECTIONS.get(x.feature)=='higher' else x.raw_pct,axis=1)
    d['weight']=d.feature.map(weights).astype(float)
    d['weighted']=d.risk_pct*d.weight
    agg=d.groupby(['cutoff_date','ruc'],as_index=False).agg(weighted=('weighted','sum'),weight=('weight','sum'))
    agg['risk_index']=(agg.weighted/agg.weight).clip(0,100)
    return agg[['cutoff_date','ruc','risk_index']]


def _risk_payload_for_entity(risk_frame,features,ruc,cfg):
    rows=risk_frame[risk_frame.ruc==ruc].sort_values('cutoff_date') if not risk_frame.empty else pd.DataFrame()
    rcfg=cfg.get('dashboard',{}).get('risk_index',{})
    weights={str(k):float(v) for k,v in (rcfg.get('weights') or {}).items() if float(v)>0}
    current=None;contributors=[]
    if not rows.empty:
        current=float(rows.iloc[-1].risk_index);date=rows.iloc[-1].cutoff_date
        for feat,w in weights.items():
            one=features[(features.ruc==ruc)&(features.cutoff_date==date)&(features.feature==feat)]
            if one.empty:continue
            value=float(one.iloc[-1].value)
            pool=features[(features.cutoff_date==date)&(features.feature==feat)].value.dropna().astype(float)
            if pool.empty:continue
            raw=float((pool<=value).mean()*100)
            favorable=100-raw if DIRECTIONS.get(feat)=='lower' else raw
            riskp=100-favorable
            contributors.append({'feature':feat,'value':value,'weight':w,'risk_percentile':riskp,'weighted_points':w*riskp})
        totalw=sum(x['weight'] for x in contributors) or 1
        for x in contributors:x['contribution_points']=x['weighted_points']/totalw
        contributors=sorted(contributors,key=lambda x:x['contribution_points'],reverse=True)
    bands=rcfg.get('bands',{'low_max':33,'medium_max':66});labels=rcfg.get('labels',{'low':'Bajo','medium':'Medio','high':'Alto'})
    if current is None:label=None
    elif current<=float(bands.get('low_max',33)):label=labels.get('low','Bajo')
    elif current<=float(bands.get('medium_max',66)):label=labels.get('medium','Medio')
    else:label=labels.get('high','Alto')
    return {
        'current':current,
        'label':label,
        'bands':bands,
        'series':_records(rows,['cutoff_date','risk_index']) if not rows.empty else [],
        'contributors':contributors,
        'method':'Índice relativo 0–100 construido con percentiles contemporáneos del Segmento 1; no es una probabilidad de default.'
    }


def _latest_distributions(features,feature_names):
    out={}
    if features.empty:return out
    for f in feature_names:
        g=features[features.feature==f]
        if g.empty:continue
        last=str(g.cutoff_date.max())
        q=g[g.cutoff_date==last][['ruc','value']].copy()
        q['value']=pd.to_numeric(q.value,errors='coerce');q=q.dropna(subset=['value'])
        out[f]={'cutoff_date':last,'values':_records(q)}
    return out


def _read_load_status(base):
    fp=Path(base)/'data'/'load_status.json'
    try:return json.loads(fp.read_text(encoding='utf-8'))
    except Exception:return {}


def rebuild_index(root=None, build_info=None):
    root=Path(root) if root else project_root();cfg=load_yaml('project.yaml',root)
    base=root/cfg['paths']['githubpage']
    template=root/'src'/'sepsrisk'/'reporting'/'index_template.html'
    if not template.exists():return None
    info=dict(build_info or {});info.setdefault('generated_at',utcnow())
    bid=re.sub(r'[^0-9A-Za-z]+','',str(info['generated_at']))[-24:] or 'build';info['build_id']=bid
    # 014 is intentionally static: no polling/autoreload.
    info['auto_reload_seconds']=0
    html=template.read_text(encoding='utf-8')
    html=html.replace('__BUILD_ID__',bid)
    html=html.replace('__SEPS_BUILD_INFO__',json.dumps(info,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    _atomic_write(base/'index.html',html)
    return {'build_id':bid,'index':str(base/'index.html')}


def export_dashboard(con,root=None):
    root=Path(root) if root else project_root();cfg=load_yaml('project.yaml',root)
    base=root/cfg['paths']['githubpage'];out=base/'data';entdir=out/'entities';entdir.mkdir(parents=True,exist_ok=True)
    for old in entdir.glob('*.json'):old.unlink()
    entities=query_df(con,'SELECT ruc,entity_name,first_seen,last_seen FROM dim_entity ORDER BY entity_name')
    default=resolve_focus_entity(con,root);inf=readiness(con,root);pub=cfg.get('publication',{});generated=utcnow()
    risk_cfg=cfg.get('dashboard',{}).get('risk_index',{})
    meta={
      'mode':'live' if not entities.empty else 'empty','generated_at':generated,
      'title':cfg['dashboard']['title'],'subtitle':cfg['dashboard']['subtitle'],
      'default_ruc':default['ruc'] if default else None,'default_entity_name':default['entity_name'] if default else None,
      'segment':cfg['universe']['segment'],'inference':inf,'publication':pub,
      'focus_display_name':cfg.get('focus_entity',{}).get('display_name'),
      'risk_index':risk_cfg,
      'dashboard_defaults':{k:cfg['dashboard'].get(k) for k in ['default_period','default_aggregation','default_visualization']}
    }
    _atomic_write(out/'metadata.json',json.dumps(meta,ensure_ascii=False,indent=2))
    entity_rows=_records(entities);_atomic_write(out/'entities.json',json.dumps(entity_rows,ensure_ascii=False,indent=2))
    p=query_df(con,'SELECT * FROM fact_peer_stat ORDER BY cutoff_date,feature')
    peers={}
    if not p.empty:
        for feat,g in p.groupby('feature'):peers[feat]=_records(g,['cutoff_date','q25','median','q75','n'])
    riskall=query_df(con,'SELECT * FROM fact_risk_estimate ORDER BY cutoff_date,horizon_months,ruc')
    allf=query_df(con,'SELECT cutoff_date,ruc,feature,value FROM fact_feature ORDER BY ruc,cutoff_date')
    risk_index=_risk_index_frame(allf,cfg)
    core=list((risk_cfg.get('weights') or {}).keys()) or list(DIRECTIONS)
    peer_payload={
        'feature_stats':peers,
        'risk_stats':_risk_benchmarks(riskall),
        'latest_distributions':_latest_distributions(allf,core),
        'risk_index_distribution':_records(risk_index[risk_index.cutoff_date==risk_index.cutoff_date.max()]) if not risk_index.empty else []
    }
    _atomic_write(out/'peers.json',json.dumps(peer_payload,ensure_ascii=False,indent=2))
    alls=query_df(con,'SELECT * FROM fact_signal ORDER BY ruc,cutoff_date,signal')
    written=0;bundle_entities={}
    for e in entity_rows:
        ruc=e['ruc'];f=allf[allf.ruc==ruc]
        w=f.pivot(index='cutoff_date',columns='feature',values='value').reset_index() if not f.empty else pd.DataFrame()
        s=alls[alls.ruc==ruc];r=riskall[riskall.ruc==ruc]
        payload={
            'entity':e,'series':_records(w),'signals':_records(s),'risk_estimates':_records(r),
            'percentiles':_percentiles(allf,ruc),'risk_index':_risk_payload_for_entity(risk_index,allf,ruc,cfg)
        }
        _atomic_write(entdir/f'{ruc}.json',json.dumps(payload,ensure_ascii=False,indent=2));bundle_entities[str(ruc)]=payload;written+=1
    legacy={'metadata':meta,'series':[],'peers':peers,'signals':[],'risk_estimates':[]}
    if default:
        fp=entdir/f"{default['ruc']}.json"
        if fp.exists():
            d=json.loads(fp.read_text(encoding='utf-8'));legacy.update({k:d.get(k,[]) for k in ['series','signals','risk_estimates']});legacy['metadata']['entity_name']=default['entity_name'];legacy['metadata']['ruc']=default['ruc']
    _atomic_write(out/'dashboard.json',json.dumps(legacy,ensure_ascii=False,indent=2))
    bundle={'metadata':meta,'entities':entity_rows,'peers':peer_payload,'entity_data':bundle_entities}
    _atomic_write(out/'live_bundle.js','window.SEPS_LIVE_DATA = '+json.dumps(bundle,ensure_ascii=False,separators=(',',':'))+';\n')
    status=_read_load_status(base);build_info={**status,'generated_at':generated,'dashboard_mode':meta['mode'],'entity_count':written,'default_ruc':meta['default_ruc']}
    stamp=rebuild_index(root,build_info)
    return {'mode':meta['mode'],'entities':written,'default_ruc':meta['default_ruc'],'generated_at':generated,'bundle_bytes':(out/'live_bundle.js').stat().st_size,**(stamp or {})}
