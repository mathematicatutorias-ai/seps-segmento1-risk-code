import re
import requests
from sepsrisk.config import load_yaml
from sepsrisk.sources import discovery


class _Resp:
    def __init__(self, text='', status=200, content_type='text/html'):
        self.text = text
        self.status_code = status
        self.headers = {'content-type': content_type}
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}')


class _Session:
    def __init__(self):
        self.headers = {}
        self.calls = []
    def get(self, url, timeout=None):
        self.calls.append(url)
        if url.endswith('/bases-financiero/'):
            return _Resp('<html><a href="/other/">OTRA-BASE</a></html>')
        if url.endswith('/bases-financiero/page/2/'):
            return _Resp('<html><a href="/index.php/sdm_downloads/eeff-men-base-2026/">EEFF-MEN-BASE-2026</a></html>')
        if url.endswith('/bases-financiero/page/3/'):
            return _Resp(status=404)
        if url.endswith('/index.php/sdm_downloads/eeff-men-base-2026/'):
            return _Resp('<html><a href="https://estadisticas.seps.gob.ec/?download_id=123&sdm_process_download=1">¡Descarga ahora!</a></html>')
        return _Resp(status=404)


def test_config_regex_matches_years_and_anteriores(project_root):
    cfg = load_yaml('sources.yaml', project_root)
    rx = re.compile(cfg['sources']['eeff_monthly']['title_regex'])
    assert rx.search('EEFF-MEN-BASE-2026')
    assert rx.search('EEFF-MEN-BASE-2018')
    assert rx.search('EEFF-MEN-BASE-ANTERIORES')


def test_discovery_does_not_stop_on_first_empty_page(monkeypatch, project_root):
    fake = _Session()
    monkeypatch.setattr(discovery.requests, 'Session', lambda: fake)
    items = discovery.discover_source_items('eeff_monthly', project_root)
    assert any(x['title'] == 'EEFF-MEN-BASE-2026' for x in items)
    assert any('/page/2/' in u for u in fake.calls)


def test_resolve_download_prefers_explicit_sdm_over_navigation(project_root):
    class S:
        def get(self, url, timeout=None):
            return _Resp(
                '<html>'
                '<a href="/index.php/sdm_downloads/">Descargas</a>'
                '<a href="https://estadisticas.seps.gob.ec/?download_id=2773&sdm_process_download=1">¡Descarga ahora!</a>'
                '</html>'
            )
    got = discovery.resolve_download(
        'https://estadisticas.seps.gob.ec/index.php/sdm_downloads/eeff-men-base-2025/',
        S(), 30, ['.zip','.txt','.csv','.xlsx','.xls']
    )
    assert got == 'https://estadisticas.seps.gob.ec/?download_id=2773&sdm_process_download=1'


def test_discovery_page_limit_is_respected(monkeypatch, project_root):
    fake = _Session()
    monkeypatch.setattr(discovery.requests, 'Session', lambda: fake)
    discovery.discover_source_items('eeff_monthly', project_root, page_limit=2, parallel_workers=1)
    assert any('/page/2/' in u for u in fake.calls)
    assert not any('/page/3/' in u for u in fake.calls)


def test_parallel_discovery_finds_same_item(monkeypatch, project_root):
    fake = _Session()
    monkeypatch.setattr(discovery.requests, 'Session', lambda: fake)
    items = discovery.discover_source_items('eeff_monthly', project_root, page_limit=3, parallel_workers=3)
    assert any(x['title'] == 'EEFF-MEN-BASE-2026' for x in items)
