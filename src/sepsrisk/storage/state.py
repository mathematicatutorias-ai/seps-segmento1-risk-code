from pathlib import Path
import json, os
from ..config import load_yaml, project_root
from ..utils import utcnow


def _root(root=None):
    return Path(root) if root else project_root()


def state_dir(root=None):
    r=_root(root); cfg=load_yaml('project.yaml',r)
    p=r/cfg['paths'].get('state','data/state'); p.mkdir(parents=True,exist_ok=True); return p


def _atomic_json(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,path)


def load_json(name,root=None,default=None):
    p=state_dir(root)/name
    if not p.exists(): return {} if default is None else default
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {} if default is None else default


def save_json(name,obj,root=None):
    p=state_dir(root)/name; _atomic_json(p,obj); return p


def source_catalog(root=None):
    return load_json('source_catalog.json',root,default={'updated_at':None,'items':[]})


def save_source_catalog(items,root=None):
    # title+source_key are stable logical identifiers.
    uniq={f"{x.get('source_key')}|{x.get('title')}":x for x in items}
    return save_json('source_catalog.json',{'updated_at':utcnow(),'items':list(uniq.values())},root)


def ingestion_manifest(root=None):
    return load_json('ingestion_manifest.json',root,default={'updated_at':None,'sources':{},'partitions':{}})


def save_ingestion_manifest(m,root=None):
    m=dict(m);m['updated_at']=utcnow();return save_json('ingestion_manifest.json',m,root)


def app_meta(root=None):
    return load_json('app_meta.json',root,default={})


def meta_get(key,root=None,default=None):
    return app_meta(root).get(key,default)


def meta_set(key,value,root=None):
    m=app_meta(root);m[key]=value;save_json('app_meta.json',m,root);return value
