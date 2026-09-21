import hashlib,re,unicodedata,shutil
from pathlib import Path
from datetime import datetime,timezone
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def sha256_text(s): return hashlib.sha256(str(s).encode()).hexdigest()
def utcnow(): return datetime.now(timezone.utc).isoformat()
def norm_text(s):
    s=''.join(c for c in unicodedata.normalize('NFKD',str(s or '')) if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',re.sub(r'[^A-Za-z0-9]+',' ',s)).strip().upper()
def ensure_clean_dir(path):
    p=Path(path);p.mkdir(parents=True,exist_ok=True)
    for x in p.iterdir():
        if x.name=='.gitkeep': continue
        shutil.rmtree(x,ignore_errors=True) if x.is_dir() else x.unlink(missing_ok=True)
