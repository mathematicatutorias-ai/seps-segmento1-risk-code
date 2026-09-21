from pathlib import Path
from sepsrisk.pipeline import _needs_full_discovery,_discover_cached_items
from sepsrisk.storage.state import meta_set

def test_cache_full_once_then_incremental(monkeypatch,tmp_path):
    # Minimal project config/state tree.
    root=tmp_path
    (root/'config').mkdir();(root/'data/state').mkdir(parents=True)
    (root/'config/project.yaml').write_text('paths:\n  state: data/state\nprogress:\n  discovery_cache_enabled: true\n  discovery_incremental_pages: 3\n  discovery_parallel_workers: 6\n  discovery_full_refresh_days: 30\n  discovery_force_full_scan: false\n',encoding='utf-8')
    (root/'config/sources.yaml').write_text('http:\n  user_agent: test\n  timeout_seconds: 1\nsources:\n  eeff_monthly:\n    discovery_pages: []\n    max_pages: 15\n    title_regex: EEFF\n    accepted_extensions: [".zip"]\n',encoding='utf-8')
    cfg={'progress':{'discovery_cache_enabled':True,'discovery_incremental_pages':3,'discovery_parallel_workers':6,'discovery_full_refresh_days':30,'discovery_force_full_scan':False}}
    spec={'max_pages':15};calls=[]
    def fake(source_key,root,on_page=None,diagnostics=None,page_limit=None,parallel_workers=1):
        calls.append((page_limit,parallel_workers));return [{'source_key':source_key,'title':'EEFF-MEN-BASE-2026','page_url':'p','url':'u'}]
    monkeypatch.setattr('sepsrisk.pipeline.discover_source_items',fake)
    assert _needs_full_discovery(cfg,'eeff_monthly',root) is True
    _discover_cached_items(root,'eeff_monthly',spec,cfg)
    meta_set('discovery_full_scan:eeff_monthly','2099-01-01T00:00:00+00:00',root)
    assert _needs_full_discovery(cfg,'eeff_monthly',root) is False
    _discover_cached_items(root,'eeff_monthly',spec,cfg)
    assert calls[0]==(15,6) and calls[1]==(3,6)
