from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]

def test_github_config_and_gitignore():
    g=yaml.safe_load((ROOT/'config/github.yaml').read_text(encoding='utf-8'))['github']
    assert g['owner']=='mathematicatutorias-ai'
    assert g['repository']=='seps-segmento1-risk-code'
    assert g['branch']=='main'
    assert g['visibility']=='public'
    assert g['secret_name']=='GITHUB_TOKEN'
    gi=(ROOT/'.gitignore').read_text(encoding='utf-8')
    for x in ['data/','*.parquet','*.sqlite','*.duckdb']:
        assert x in gi

def test_preflight_excludes_operational_data(tmp_path,monkeypatch):
    import sys
    sys.path.insert(0,str(ROOT/'src'))
    from sepsrisk.publication.github import collect_publish_files,preflight
    # Use real project: there must be no operational data in the publication snapshot.
    rels=[r for _,r in collect_publish_files(ROOT)]
    assert not any(r.startswith('data/') for r in rels)
    assert not any(r.endswith('.parquet') for r in rels)
    assert not any(r.endswith('.sqlite') for r in rels)
    pf=preflight(ROOT)
    assert pf['files']>10
    assert not pf['issues']
