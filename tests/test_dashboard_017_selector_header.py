from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]

def test_017_lists_full_entity_universe_without_slice_cap():
    js=(ROOT/'githubpage/assets/app.js').read_text(encoding='utf-8')
    block=js.split('function filterEntities(q){',1)[1].split('\n}',1)[0]
    assert 'return rows;' in block
    assert '.slice(' not in block

def test_017_header_and_caret_are_homogeneous():
    html=(ROOT/'src/sepsrisk/reporting/index_template.html').read_text(encoding='utf-8')
    css=(ROOT/'githubpage/assets/app.css').read_text(encoding='utf-8')
    js=(ROOT/'githubpage/assets/app.js').read_text(encoding='utf-8')
    assert '<h1 id="title">MONITOR DE RIESGO FINANCIERO</h1>' in html
    assert 'id="entityToggle"' in html and '>⌄<' not in html
    assert '--control-caret' in css
    assert 'background-image:var(--control-caret)' in css
    assert "$('title').textContent='MONITOR DE RIESGO FINANCIERO'" in js

def test_017_release_config():
    cfg=yaml.safe_load((ROOT/'config/project.yaml').read_text(encoding='utf-8'))
    assert cfg['project']['version']=='0.17.0'
    assert int(cfg['release']['update'])==17
    assert int(cfg['dashboard']['entity_selector']['max_results'])==0
