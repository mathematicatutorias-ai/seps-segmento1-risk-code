from pathlib import Path
import yaml

def test_014_ux_contract():
    root=Path(__file__).resolve().parents[1]
    cfg=yaml.safe_load((root/'config/project.yaml').read_text(encoding='utf-8'))
    assert int(cfg['release']['update']) >= 14
    ri=cfg['dashboard']['risk_index']
    assert ri['enabled'] is True
    assert ri['bands']['low_max'] < ri['bands']['medium_max'] < 100
    assert abs(sum(ri['weights'].values())-1.0) < 1e-9
    template=(root/'src/sepsrisk/reporting/index_template.html').read_text(encoding='utf-8')
    for x in ['sidebarToggle','riskGauge','contributorsChart','radarChart','distributionChart','riskEvolutionChart','methodologyModal','methodologyModalContent','methodologyOpen']:
        assert f'id="{x}"' in template

def test_risk_index_export_is_not_called_probability_when_uncalibrated():
    root=Path(__file__).resolve().parents[1]
    app=(root/'githubpage/assets/app.js').read_text(encoding='utf-8')
    assert 'Índice de riesgo relativo' in app
    assert 'No es una probabilidad de default' in app
