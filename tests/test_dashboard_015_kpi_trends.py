from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_kpi_trend_slots_and_logic_exist():
    html=(ROOT/'src/sepsrisk/reporting/index_template.html').read_text(encoding='utf-8')
    js=(ROOT/'githubpage/assets/app.js').read_text(encoding='utf-8')
    css=(ROOT/'githubpage/assets/app.css').read_text(encoding='utf-8')
    for x in ['trendMora','trendCoverage','trendLiquidity','trendDeposits','trendEquity','trendRisk']:
        assert f'id="{x}"' in html
    for x in ['previousPeriodRow','setTrend','renderKpiTrends','riskScoreForRow']:
        assert f'function {x}' in js
    assert 'kpi-trend good' in css or '.kpi-trend.good' in css
    assert '.kpi-trend.bad' in css

def test_semantic_directions_are_encoded():
    js=(ROOT/'githubpage/assets/app.js').read_text(encoding='utf-8')
    assert "'trendMora',z.delinquency_ratio,prev?.delinquency_ratio,'lower'" in js
    assert "'trendCoverage',z.coverage_ratio,prev?.coverage_ratio,'higher'" in js
    assert "'trendRisk',R?.score,riskScoreForRow(prev),'lower','score'" in js
