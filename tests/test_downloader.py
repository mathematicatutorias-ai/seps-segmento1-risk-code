
import pytest
from sepsrisk.ingestion import downloader

class R:
    def __init__(self, content_type='text/html', body=b'<html>oops</html>', url='https://example/x'):
        self.headers={'content-type':content_type,'content-length':str(len(body))}
        self.body=body
        self.url=url
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def raise_for_status(self): return None
    def iter_content(self,n): yield self.body

def test_downloader_rejects_html(monkeypatch, project_root, tmp_path):
    monkeypatch.setattr(downloader.requests,'get',lambda *a,**k:R())
    with pytest.raises(RuntimeError, match='HTML'):
        downloader.download('https://example/download', tmp_path/'x.bin', project_root)

def test_downloader_accepts_zip_payload(monkeypatch, project_root, tmp_path):
    import io, zipfile
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:z.writestr('x.txt','ok')
    body=b.getvalue()
    monkeypatch.setattr(downloader.requests,'get',lambda *a,**k:R('application/zip',body,'https://example/file.zip'))
    p=downloader.download('https://example/download', tmp_path/'x.bin', project_root)
    assert p.suffix=='.zip'
    assert p.read_bytes()==body
