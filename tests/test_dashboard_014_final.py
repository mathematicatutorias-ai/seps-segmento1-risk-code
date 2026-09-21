from pathlib import Path
import yaml

def test_014_mathjax_and_methodology_modal():
    root=Path(__file__).resolve().parents[1]
    template=(root/'src/sepsrisk/reporting/index_template.html').read_text(encoding='utf-8')
    app=(root/'githubpage/assets/app.js').read_text(encoding='utf-8')
    assert 'mathjax@3' in template.lower()
    assert 'methodologyModal' in template
    assert 'methodologyHTML' in app
    assert 'P_{i,t}(H)' in app
    assert 'R_{i,t}' in app

def test_014_static_and_risk_client_fallback():
    root=Path(__file__).resolve().parents[1]
    app=(root/'githubpage/assets/app.js').read_text(encoding='utf-8')
    cfg=yaml.safe_load((root/'config/project.yaml').read_text(encoding='utf-8'))
    assert int(cfg['release']['update']) >= 14
    assert 'computeRiskSnapshot' in app
    assert 'clientRiskSeries' in app
    assert 'riskPeerPercentile' in app
    assert 'setInterval(' not in app and 'location.reload(' not in app
    assert 'Actualizar datos' not in app

def test_014_main_metric_title_is_dynamic():
    root=Path(__file__).resolve().parents[1]
    app=(root/'githubpage/assets/app.js').read_text(encoding='utf-8')
    assert "$('mainTitle').textContent" in app
    assert "$('mainSubtitle').textContent" in app
