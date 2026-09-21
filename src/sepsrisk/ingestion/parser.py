from pathlib import Path
import csv
import io
import zipfile
import pandas as pd
from ..utils import norm_text


def extract_or_list(path,temp):
    path=Path(path);temp=Path(temp)
    if zipfile.is_zipfile(path):
        temp.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(path) as z:z.extractall(temp)
        return [p for p in temp.rglob('*') if p.is_file()]
    return [path]


def _detect_text(path):
    path=Path(path)
    raw=path.read_bytes()[:131072]
    enc=None;text=None
    for e in ('utf-8-sig','utf-8','cp1252','latin-1'):
        try:
            text=raw.decode(e);enc=e;break
        except UnicodeDecodeError:
            pass
    if text is None: raise UnicodeError(path)
    try: sep=csv.Sniffer().sniff(text[:20000],delimiters='\t;,|').delimiter
    except Exception: sep='\t' if '\t' in text[:20000] else ','
    return enc,sep


def estimate_rows(path):
    path=Path(path)
    if path.suffix.lower() in ('.xlsx','.xls'): return None
    n=0
    with open(path,'rb') as f:
        while True:
            b=f.read(8*1024*1024)
            if not b: break
            n += b.count(b'\n')
    return max(0,n-1)


def iter_table(path,chunksize=50000):
    path=Path(path)
    if path.suffix.lower() in ('.xlsx','.xls'):
        yield pd.read_excel(path,dtype=str)
        return
    enc,sep=_detect_text(path)
    for chunk in pd.read_csv(path,sep=sep,dtype=str,encoding=enc,chunksize=chunksize,low_memory=False):
        yield chunk


def read_table(path):
    path=Path(path)
    if path.suffix.lower() in ('.xlsx','.xls'): return pd.read_excel(path,dtype=str)
    enc,sep=_detect_text(path)
    return pd.read_csv(path,sep=sep,dtype=str,encoding=enc,low_memory=False)


def match_columns(df,aliases):
    n={norm_text(c):c for c in df.columns};m={}
    for canon,opts in aliases.items():
        for o in opts:
            if norm_text(o) in n:m[n[norm_text(o)]]=canon;break
    out=df.rename(columns=m);missing=[k for k in aliases if k not in out]
    if missing:raise ValueError(f'Faltan {missing}; columnas={list(df.columns)}')
    return out[list(aliases)]


def parse_balance(s):
    if pd.isna(s):return None
    x=str(s).strip().replace('$','').replace(' ','')
    if ',' in x and '.' in x:x=x.replace('.','').replace(',','.') if x.rfind(',')>x.rfind('.') else x.replace(',','')
    elif ',' in x:x=x.replace(',','.') if len(x.rsplit(',',1)[-1])<=2 else x.replace(',','')
    try:return float(x)
    except:return None
