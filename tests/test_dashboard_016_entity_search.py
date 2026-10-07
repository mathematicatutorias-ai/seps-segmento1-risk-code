\
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]

def test_016_autocomplete_markup_and_no_legacy_select():
    html=(ROOT/'src/sepsrisk/reporting/index_template.html').read_text(encoding='utf-8')
    assert 'id="entitySearch"' in html
    assert 'id="entityResults"' in html
    assert 'role="combobox"' in html
    assert 'placeholder="Buscar por nombre, sigla o RUC"' in html
    assert '<select id="entitySelect"' not in html

def test_016_client_search_supports_ruc_short_name_and_acronym():
    js=(ROOT/'githubpage/assets/app.js').read_text(encoding='utf-8')
    for fn in ['normalizeEntitySearch','shortEntityName','entityAcronyms','filterEntities','bindEntitySearch','selectEntity']:
        assert f'function {fn}' in js
    assert "e.ruc,e.entity_name,display,...aliases" in js
    assert "COAC " in js
    assert "MUTUALISTA " in js
    assert "ArrowDown" in js and "ArrowUp" in js and "Escape" in js

def test_016_alias_config_and_release():
    cfg=yaml.safe_load((ROOT/'config/project.yaml').read_text(encoding='utf-8'))
    aliases=yaml.safe_load((ROOT/'config/entity_aliases.yaml').read_text(encoding='utf-8'))
    assert int(cfg['release']['update']) == 16
    assert cfg['project']['version'] == '0.16.0'
    assert cfg['dashboard']['entity_selector']['search_ruc'] is True
    assert '0190115798001' in aliases['aliases']
    assert 'JEP' in aliases['aliases']['0190115798001']
    assert 'CPN' in aliases['aliases']['1790866084001']

def test_016_exporter_preserves_legal_name_and_adds_display_fields():
    py=(ROOT/'src/sepsrisk/reporting/export_dashboard.py').read_text(encoding='utf-8')
    assert "e['display_name']=_entity_display_name" in py
    assert "e['aliases']=aliases.get" in py
    assert "'entity_aliases':aliases" in py
