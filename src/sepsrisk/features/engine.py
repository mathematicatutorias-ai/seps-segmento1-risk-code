import numpy as np
import pandas as pd
from ..config import load_yaml
from ..utils import utcnow
from ..storage.analytics import query_df


class FeatureEvaluationError(RuntimeError):
    """Raised when a configured derived feature cannot be evaluated."""


def comp(eeff,spec):
    m=pd.Series(True,index=eeff.index)
    if spec.get('accounts'):
        m &= eeff.account.astype(str).isin(set(map(str,spec['accounts'])))
    if spec.get('description_regex'):
        # non-capturing groups avoid pandas' regex warning while preserving semantics
        rx=str(spec['description_regex']).replace('(','(?:') if '(' in str(spec['description_regex']) and '(?' not in str(spec['description_regex']) else str(spec['description_regex'])
        m &= eeff.account_description.fillna('').str.contains(rx,regex=True,na=False)
    return eeff[m].groupby(['cutoff_date','ruc']).balance.sum()


def _replace_table(con,name,df):
    con.execute(f'DELETE FROM {name}')
    if df is None or df.empty:
        return
    temp=f'_df_{name}'
    con.register(temp,df)
    con.execute(f'INSERT INTO {name} SELECT * FROM {temp}')
    con.unregister(temp)


def _evaluate_features(wide,components,feature_cfg):
    """Evaluate configured features in declaration order.

    Crucially, every successfully calculated feature is inserted back into ``env``.
    This allows later features to depend on earlier derived features, e.g.:

      loan_portfolio_gross -> delinquency_ratio

    Previous releases stored the first value in ``fs`` but not ``env``; therefore
    dependent expressions failed with NameError and were silently skipped.
    """
    env={c:wide[c] for c in wide}
    env['abs']=np.abs
    fs={}

    for name,spec in feature_cfg.items():
        try:
            if 'pieces' in spec:
                x=pd.Series(np.nan,index=wide.index,dtype=float)
                dates=pd.to_datetime(x.index.get_level_values('cutoff_date'))
                for piece in spec['pieces']:
                    expression=piece['expression']
                    xp=eval(expression,{'__builtins__':{}},env)
                    mask=pd.Series(True,index=x.index)
                    if piece.get('from'):
                        mask &= dates>=pd.Timestamp(piece['from'])
                    if piece.get('until'):
                        mask &= dates<=pd.Timestamp(piece['until'])
                    x=x.where(~mask,xp)
            elif 'expression' in spec:
                expression=spec['expression']
                x=eval(expression,{'__builtins__':{}},env)
            else:
                source=spec['source']
                if source not in components and source not in env:
                    raise KeyError(f"source '{source}' is not available")
                source_series=components.get(source,env.get(source))
                x=source_series.groupby(level='ruc').pct_change(int(spec['periods']))
        except Exception as exc:
            expr=spec.get('expression') or '; '.join(p.get('expression','') for p in spec.get('pieces',[])) or f"transform from {spec.get('source')}"
            raise FeatureEvaluationError(
                f"Feature '{name}' failed. Formula: {expr}. Cause: {type(exc).__name__}: {exc}"
            ) from exc

        if not isinstance(x,pd.Series):
            x=pd.Series(x,index=wide.index,dtype=float)
        if spec.get('valid_from'):
            x=x.where(pd.to_datetime(x.index.get_level_values('cutoff_date'))>=pd.Timestamp(spec['valid_from']))
        x=x.replace([np.inf,-np.inf],np.nan)
        fs[name]=x
        env[name]=x  # critical: derived features become dependencies for later features

    return fs


def build_features(con,root=None):
    cfg=load_yaml('features.yaml',root)
    e=query_df(con,'SELECT cutoff_date,ruc,account,balance,account_description FROM fact_eeff')
    if e.empty:
        con.execute('DELETE FROM fact_feature')
        con.execute('DELETE FROM fact_peer_stat')
        return {'rows':0}

    cs={n:comp(e,s) for n,s in cfg['components'].items()}
    wide=pd.concat(cs,axis=1).sort_index()
    fs=_evaluate_features(wide,cs,cfg['features'])

    now=utcnow();rows=[]
    for n,x in {**cs,**fs}.items():
        unit=cfg['features'].get(n,{}).get('unit','usd')
        rows.extend((str(d),str(r),n,float(v),unit,'features.yaml:0.11',now) for (d,r),v in x.dropna().items())
    d=pd.DataFrame(rows,columns=['cutoff_date','ruc','feature','value','unit','method_version','calculated_at'])
    _replace_table(con,'fact_feature',d)

    peers=[]
    if not d.empty:
        for (date,f),g in d.groupby(['cutoff_date','feature']):
            v=g.value.astype(float)
            peers.append((date,f,float(v.quantile(.25)),float(v.median()),float(v.quantile(.75)),float(v.mean()),float(v.std()) if len(v)>1 else None,int(len(v)),now))
    p=pd.DataFrame(peers,columns=['cutoff_date','feature','q25','median','q75','mean','std','n','calculated_at'])
    _replace_table(con,'fact_peer_stat',p)
    return {'rows':len(d),'peer_rows':len(p),'features':len(fs),'components':len(cs)}
