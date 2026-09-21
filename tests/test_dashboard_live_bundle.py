from pathlib import Path

def test_app_uses_live_bundle_and_is_static():
    root=Path(__file__).resolve().parents[1]
    s=(root/'githubpage/assets/app.js').read_text(encoding='utf-8')
    assert 'window.SEPS_LIVE_DATA' in s
    assert 'live?.entity_data' in s
    assert 'location.reload()' not in s
    assert 'setInterval(' not in s
    assert 'refreshLive' not in s
    template=(root/'src/sepsrisk/reporting/index_template.html').read_text(encoding='utf-8')
    assert 'Actualizar datos' not in template
