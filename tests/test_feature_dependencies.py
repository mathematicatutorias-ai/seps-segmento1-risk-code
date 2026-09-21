import pandas as pd
import pytest
from sepsrisk.features.engine import _evaluate_features, FeatureEvaluationError


def _base():
    idx=pd.MultiIndex.from_tuples([('2026-08-31','r1')],names=['cutoff_date','ruc'])
    wide=pd.DataFrame({
        'loan_portfolio_net':[100.0],
        'loan_provisions':[-5.0],
        'nonperforming_loans_post_2021_05':[10.0],
    },index=idx)
    components={c:wide[c] for c in wide.columns}
    return wide,components


def test_derived_feature_can_feed_later_feature():
    wide,components=_base()
    cfg={
        'loan_portfolio_gross':{'expression':'loan_portfolio_net - loan_provisions'},
        'delinquency_ratio':{'expression':'nonperforming_loans_post_2021_05 / loan_portfolio_gross'},
    }
    fs=_evaluate_features(wide,components,cfg)
    assert fs['loan_portfolio_gross'].iloc[0] == pytest.approx(105.0)
    assert fs['delinquency_ratio'].iloc[0] == pytest.approx(10.0/105.0)


def test_broken_feature_is_not_silently_skipped():
    wide,components=_base()
    cfg={'broken':{'expression':'missing_dependency / loan_portfolio_net'}}
    with pytest.raises(FeatureEvaluationError,match="Feature 'broken' failed"):
        _evaluate_features(wide,components,cfg)
