import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from ..config import load_yaml


def _page_url(base, n):
    return base if n == 1 else base.rstrip('/') + f'/page/{n}/'


def _is_direct_download_url(url):
    low = (url or '').lower()
    return 'sdm_process_download=1' in low or 'download_id=' in low


def _fetch_catalog_page(session, source_key, url, n, timeout, rx):
    status = {'source_key': source_key, 'page': n, 'url': url, 'ok': False, 'matches': 0}
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        status['ok'] = True
    except Exception as e:
        status['error'] = repr(e)
        return status, []

    soup = BeautifulSoup(r.text, 'html.parser')
    found = []
    for a in soup.find_all('a', href=True):
        title = ' '.join(a.stripped_strings).strip()
        if title and rx.search(title):
            found.append({'title': title, 'page_url': urljoin(url, a['href'])})
    status['matches'] = len(found)
    return status, found


def discover_source_items(source_key, root=None, on_page=None, diagnostics=None, session=None,
                          page_limit=None, parallel_workers=1):
    """Discover downloadable SEPS publications from configured catalogue pages.

    ``page_limit`` allows an incremental refresh to inspect only the newest catalogue
    pages. ``parallel_workers`` parallelizes catalogue-page requests and publication
    URL resolution. Defaults preserve the original sequential behavior for tests and
    callers that do not request parallelism.
    """
    cfg = load_yaml('sources.yaml', root)
    spec = cfg['sources'][source_key]
    rx = re.compile(spec['title_regex'])
    s = session or requests.Session()
    s.headers['User-Agent'] = cfg['http']['user_agent']
    diagnostics = diagnostics if diagnostics is not None else []
    timeout = cfg['http']['timeout_seconds']
    limit = int(page_limit or spec.get('max_pages', 10))
    workers = max(1, int(parallel_workers or 1))

    found_meta = []
    jobs = []
    for base in spec['discovery_pages']:
        for n in range(1, limit + 1):
            jobs.append((n, _page_url(base, n)))

    if workers == 1:
        results = [_fetch_catalog_page(s, source_key, url, n, timeout, rx) for n, url in jobs]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs) or 1)) as ex:
            futs = {ex.submit(_fetch_catalog_page, s, source_key, url, n, timeout, rx): (n, url)
                    for n, url in jobs}
            for fut in as_completed(futs):
                results.append(fut.result())

    for status, rows in results:
        diagnostics.append(status.copy())
        if on_page:
            on_page(status)
        found_meta.extend(rows)

    # Deduplicate publication pages by title before resolving the binary URL.
    by_title = {}
    for meta in found_meta:
        by_title.setdefault(meta['title'], meta)

    def _resolve(meta):
        direct = resolve_download(meta['page_url'], s, timeout, spec['accepted_extensions'])
        return meta, direct

    resolved = []
    metas = list(by_title.values())
    if workers == 1:
        pairs = [_resolve(m) for m in metas]
    else:
        pairs = []
        with ThreadPoolExecutor(max_workers=min(workers, len(metas) or 1)) as ex:
            futs = [ex.submit(_resolve, m) for m in metas]
            for fut in as_completed(futs):
                pairs.append(fut.result())

    for meta, direct in pairs:
        if direct:
            resolved.append({
                'source_key': source_key,
                'title': meta['title'],
                'page_url': meta['page_url'],
                'url': direct,
            })
        else:
            diagnostics.append({
                'source_key': source_key,
                'page_url': meta['page_url'],
                'title': meta['title'],
                'ok': False,
                'error': 'download_link_not_resolved',
            })
    return sorted(resolved, key=lambda x: x['title'], reverse=True)


def resolve_download(page, s, timeout, exts):
    """Resolve a SEPS publication page to the actual downloadable binary.

    Explicit Simple Download Monitor endpoints are authoritative. We intentionally
    do not guess from visible link text such as "Descargas", because navigation
    links can otherwise be mistaken for the binary.
    """
    low = page.lower()
    if _is_direct_download_url(page) or any(urlparse(low).path.endswith(e) for e in exts):
        return page
    try:
        r = s.get(page, timeout=timeout)
        r.raise_for_status()
    except Exception:
        return None
    if 'text/html' not in r.headers.get('content-type', '').lower():
        return page

    soup = BeautifulSoup(r.text, 'html.parser')
    hrefs = [urljoin(page, a['href']) for a in soup.find_all('a', href=True)]

    explicit = [u for u in hrefs if _is_direct_download_url(u)]
    if explicit:
        return explicit[0]

    for u in hrefs:
        path = urlparse(u.lower()).path
        if any(path.endswith(e) for e in exts):
            return u
    return None
