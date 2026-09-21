from pathlib import Path
import pandas as pd, os
from sepsrisk.config import load_yaml,project_root
from sepsrisk.storage.parquet_store import parquet_root
root=project_root();cfg=load_yaml('events.yaml',root)['events'];path=root/cfg['input_csv']
if not path.exists():
    path.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(columns=['ruc','event_date','event_type','adverse','source_url','notes']).to_csv(path,index=False);print('Plantilla creada:',path);raise SystemExit
D=pd.read_csv(path,dtype={'ruc':str});out=parquet_root(root)/'events'/'events.parquet';out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.parquet.tmp');D.to_parquet(tmp,index=False,engine='pyarrow',compression='zstd');os.replace(tmp,out);print('Eventos:',len(D),'→',out)
