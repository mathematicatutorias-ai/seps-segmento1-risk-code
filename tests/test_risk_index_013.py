import pandas as pd
from sepsrisk.reporting.export_dashboard import _risk_index_frame,_risk_payload_for_entity

def test_relative_risk_index_is_bounded_and_has_contributors():
    cfg={'dashboard':{'risk_index':{'weights':{'delinquency_ratio':.5,'liquidity_ratio':.5},'bands':{'low_max':33,'medium_max':66},'labels':{'low':'Bajo','medium':'Medio','high':'Alto'}}}}
    d=pd.DataFrame([
        ['2026-08-31','A','delinquency_ratio',.20],['2026-08-31','B','delinquency_ratio',.05],
        ['2026-08-31','A','liquidity_ratio',.10],['2026-08-31','B','liquidity_ratio',.30],
    ],columns=['cutoff_date','ruc','feature','value'])
    r=_risk_index_frame(d,cfg)
    a=float(r[r.ruc=='A'].iloc[0].risk_index);b=float(r[r.ruc=='B'].iloc[0].risk_index)
    assert 0 <= a <= 100 and 0 <= b <= 100
    assert a > b
    p=_risk_payload_for_entity(r,d,'A',cfg)
    assert p['current']==a
    assert len(p['contributors'])==2
    assert 'no es una probabilidad' in p['method'].lower()
