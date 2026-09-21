import re
from pathlib import Path
from urllib.parse import urlparse
import requests
from ..config import load_yaml

EXT_BY_TYPE = {
    'application/zip': '.zip',
    'application/x-zip-compressed': '.zip',
    'application/octet-stream': '.bin',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.ms-excel': '.xls',
    'text/csv': '.csv',
    'text/plain': '.txt',
}
HTML_TYPES = {'text/html', 'application/xhtml+xml'}


def _content_type(headers):
    return headers.get('content-type', '').split(';')[0].strip().lower()


def _suffix(headers, url):
    cd = headers.get('content-disposition', '')
    m = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)', cd, re.I)
    if m:
        s = Path(m.group(1)).suffix.lower()
        if s:
            return s
    s = Path(urlparse(url).path).suffix.lower()
    if s in {'.zip', '.csv', '.txt', '.xlsx', '.xls'}:
        return s
    return EXT_BY_TYPE.get(_content_type(headers), '.bin')


def _looks_like_html(path):
    head = Path(path).read_bytes()[:4096].lstrip().lower()
    return head.startswith(b'<!doctype html') or head.startswith(b'<html') or b'<html' in head[:1000]


def download(url, dest, root=None, progress=None, label=None):
    cfg = load_yaml('sources.yaml', root)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(
        url,
        stream=True,
        timeout=cfg['http']['timeout_seconds'],
        headers={'User-Agent': cfg['http']['user_agent']},
        allow_redirects=True,
    ) as r:
        r.raise_for_status()
        ctype = _content_type(r.headers)
        if ctype in HTML_TYPES:
            raise RuntimeError(
                f'SEPS devolvió HTML en lugar del archivo de datos: {r.url} '
                f'(content-type={ctype}).'
            )
        final = dest.with_suffix(_suffix(r.headers, r.url or url))
        total = int(r.headers.get('content-length') or 0)
        bar = progress.byte_bar(total, label or final.name) if progress is not None else None
        try:
            with open(final, 'wb') as f:
                for c in r.iter_content(1024 * 1024):
                    if c:
                        f.write(c)
                        if bar is not None:
                            bar.update(len(c))
        finally:
            if bar is not None:
                bar.close()

    if final.stat().st_size == 0:
        final.unlink(missing_ok=True)
        raise RuntimeError('SEPS devolvió un archivo vacío.')
    if _looks_like_html(final):
        final.unlink(missing_ok=True)
        raise RuntimeError('La descarga contiene HTML, no datos SEPS.')
    return final
