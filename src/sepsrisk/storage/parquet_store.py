from pathlib import Path
import hashlib, json, os, shutil, sqlite3
import pandas as pd
from ..config import load_yaml, project_root
from ..utils import utcnow, sha256_file
from ..ingestion.eeff import _normalize_chunk
from ..ingestion.parser import iter_table, estimate_rows
from .state import ingestion_manifest, save_ingestion_manifest, source_catalog, save_source_catalog, meta_get, meta_set


def _root(root=None): return Path(root) if root else project_root()

def parquet_root(root=None):
    r=_root(root);cfg=load_yaml('project.yaml',r);p=r/cfg['paths'].get('parquet','data/parquet');p.mkdir(parents=True,exist_ok=True);return p

def eeff_root(root=None):
    p=parquet_root(root)/'eeff';p.mkdir(parents=True,exist_ok=True);return p

def partition_path(year,month,root=None):
    return eeff_root(root)/f'year={int(year):04d}'/f'month={int(month):02d}'/'eeff.parquet'

def eeff_files(root=None):return sorted(eeff_root(root).glob('year=*/month=*/eeff.parquet'))

def has_eeff(root=None):return bool(eeff_files(root))


def _partition_fingerprint(df):
    if df.empty:return hashlib.sha256(b'').hexdigest()
    cols=['cutoff_date','ruc','account','record_sha256']
    d=df[cols].astype(str).sort_values(['cutoff_date','ruc','account'])
    h=hashlib.sha256()
    for row in d.itertuples(index=False,name=None):h.update(('|'.join(row)+'\n').encode())
    return h.hexdigest()


def _atomic_parquet(df,path,compression='zstd'):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.parquet.tmp')
    # pandas requires pyarrow or fastparquet; pyarrow is an explicit project dependency.
    df.to_parquet(tmp,index=False,engine='pyarrow',compression=compression)
    os.replace(tmp,path)


def _read_parquet(path):
    p=Path(path)
    return pd.read_parquet(p,engine='pyarrow') if p.exists() else pd.DataFrame()


def _month_key(date_value):
    x=pd.Timestamp(date_value);return int(x.year),int(x.month)


def _dedupe(df):
    if df.empty:return df
    return df.sort_values(['cutoff_date','ruc','account']).drop_duplicates(['cutoff_date','ruc','account'],keep='last').reset_index(drop=True)


def ingest_eeff_files(files,spec,segment,root=None,source=None,progress=None,chunksize=50000):
    """Parse one SEPS publication and atomically replace only changed month partitions.

    The publication is treated as authoritative for each month it contains. Existing
    month partitions are never rewritten when their record fingerprint is unchanged.
    """
    root=_root(root);groups={};rows_source=0;rows_segment_seen=0;accepted=0
    for f in files:
        f=Path(f)
        if f.suffix.lower() not in spec['accepted_extensions']:continue
        accepted+=1;total=estimate_rows(f);bar=progress.row_bar(total,f"{source.get('title','EEFF') if source else 'EEFF'} · leyendo {f.name}") if progress else None
        try:
            for raw in iter_table(f,chunksize=chunksize):
                rows_source+=len(raw);d=_normalize_chunk(raw,spec,segment)
                if not d.empty:
                    rows_segment_seen+=len(d)
                    for (yy,mm),g in d.groupby([pd.to_datetime(d.cutoff_date).dt.year,pd.to_datetime(d.cutoff_date).dt.month]):
                        groups.setdefault((int(yy),int(mm)),[]).append(g.copy())
                if bar is not None:
                    bar.update(len(raw));bar.set_postfix_str(f'S1={rows_segment_seen:,}',refresh=True)
        finally:
            if bar is not None:bar.close()
    if not groups:return {'files':accepted,'rows_source':rows_source,'rows_segment':0,'inserted':0,'updated':0,'unchanged':0,'partitions_written':0,'partitions_unchanged':0,'partition_results':[]}
    manifest=ingestion_manifest(root);part_meta=manifest.setdefault('partitions',{})
    inserted=updated=unchanged=0;written=psame=0;results=[];total_kept=0
    for (yy,mm),parts in sorted(groups.items()):
        new=_dedupe(pd.concat(parts,ignore_index=True));total_kept+=len(new)
        path=partition_path(yy,mm,root);old=_read_parquet(path)
        if not old.empty:
            old=_dedupe(old)
            old_idx=old.set_index(['cutoff_date','ruc','account'])['record_sha256']
            new_idx=new.set_index(['cutoff_date','ruc','account'])['record_sha256']
            common=old_idx.index.intersection(new_idx.index)
            unchanged_i=int((old_idx.loc[common].astype(str).values==new_idx.loc[common].astype(str).values).sum()) if len(common) else 0
            updated_i=int(len(common)-unchanged_i);inserted_i=int(len(new_idx.index.difference(old_idx.index)))
        else:
            inserted_i=len(new);updated_i=unchanged_i=0
        fp=_partition_fingerprint(new);key=f'{yy:04d}-{mm:02d}';prev=part_meta.get(key,{})
        if path.exists() and prev.get('sha256')==fp:
            psame+=1
        else:
            _atomic_parquet(new,path);written+=1
        part_meta[key]={'year':yy,'month':mm,'rows':int(len(new)),'sha256':fp,'path':str(path.relative_to(root)),'updated_at':utcnow(),'source_title':(source or {}).get('title'),'source_sha256':(source or {}).get('sha256')}
        inserted+=inserted_i;updated+=updated_i;unchanged+=unchanged_i
        results.append({'period':key,'rows':len(new),'inserted':inserted_i,'updated':updated_i,'unchanged':unchanged_i,'written':not(path.exists() and prev.get('sha256')==fp),'sha256':fp})
    save_ingestion_manifest(manifest,root)
    return {'files':accepted,'rows_source':rows_source,'rows_segment':total_kept,'rows_segment_seen':rows_segment_seen,'inserted':inserted,'updated':updated,'unchanged':unchanged,'partitions_written':written,'partitions_unchanged':psame,'partition_results':results}


def mark_source(source_key,item,sha,byte_size,result,root=None,status='ok'):
    m=ingestion_manifest(root);sources=m.setdefault('sources',{})
    key=f'{source_key}|{item["title"]}'
    sources[key]={'source_key':source_key,'title':item['title'],'url':item['url'],'page_url':item.get('page_url'),'source_sha256':sha,'byte_size':int(byte_size),'qa_status':status,'rows_source':int(result.get('rows_source',0)),'rows_segment':int(result.get('rows_segment',0)),'inserted':int(result.get('inserted',0)),'updated':int(result.get('updated',0)),'unchanged':int(result.get('unchanged',0)),'processed_at':utcnow()}
    save_ingestion_manifest(m,root);return sources[key]


def source_record(source_key,title,root=None):return ingestion_manifest(root).get('sources',{}).get(f'{source_key}|{title}')

def source_sha_seen(sha,root=None):return any(v.get('qa_status')=='ok' and v.get('source_sha256')==sha for v in ingestion_manifest(root).get('sources',{}).values())


def storage_summary(root=None):
    files=eeff_files(root);m=ingestion_manifest(root)
    rows=sum(int(x.get('rows',0)) for x in m.get('partitions',{}).values())
    periods=sorted(m.get('partitions',{}))
    return {'backend':'parquet+duckdb','partitions':len(files),'rows_manifest':rows,'first_period':periods[0] if periods else None,'last_period':periods[-1] if periods else None,'sources':len(m.get('sources',{})),'path':str(eeff_root(root))}


def legacy_sqlite_path(root=None):
    r=_root(root);cfg=load_yaml('project.yaml',r)
    legacy=cfg.get('migration',{}).get('legacy_sqlite_path') or cfg.get('paths',{}).get('database','data/operational/seps_segmento1.sqlite')
    return r/legacy


def migrate_legacy_sqlite(root=None,progress=None):
    """One-time verified migration from the <=008 SQLite to monthly Parquet.

    Migration is built first under /content, verified by row count and primary-key
    count, then copied into Drive. Only after successful verification may the legacy
    Drive SQLite be deleted (configurable, default true in 009).
    """
    root=_root(root);cfg=load_yaml('project.yaml',root);mcfg=cfg.get('migration',{})
    drive_src=legacy_sqlite_path(root)
    runtime_candidate=Path(mcfg.get('runtime_legacy_sqlite','/content/seps-segmento1-risk/seps_segmento1.sqlite'))
    if has_eeff(root):return {'needed':False,'reason':'parquet_exists'}
    candidates=[p for p in [runtime_candidate,drive_src] if p.exists() and p.stat().st_size>0]
    if not candidates:return {'needed':False,'reason':'legacy_sqlite_missing'}
    def _rows(p):
        try:
            c=sqlite3.connect(p);n=c.execute('SELECT count(*) FROM fact_eeff').fetchone()[0];c.close();return int(n)
        except Exception:return -1
    src=max(candidates,key=_rows)
    runtime=Path(mcfg.get('runtime_migration_dir','/content/seps-segmento1-risk/migration_009'))
    shutil.rmtree(runtime,ignore_errors=True);runtime.mkdir(parents=True,exist_ok=True)
    local_db=runtime/'legacy.sqlite';shutil.copy2(src,local_db)
    local_root=runtime/'project';(local_root/'data/parquet/eeff').mkdir(parents=True,exist_ok=True)
    # Copy project config so helper paths work through explicit root only where needed.
    con=sqlite3.connect(local_db);con.row_factory=sqlite3.Row
    expected=con.execute('SELECT count(*) FROM fact_eeff').fetchone()[0]
    expected_keys=con.execute("SELECT count(*) FROM (SELECT cutoff_date,ruc,account FROM fact_eeff GROUP BY cutoff_date,ruc,account)").fetchone()[0]
    q='''SELECT f.cutoff_date,f.ruc,f.segment,f.account,f.balance,f.record_sha256,
                e.entity_name,e.entity_name_norm,a.account_description
         FROM fact_eeff f
         LEFT JOIN dim_entity e USING(ruc)
         LEFT JOIN dim_account a USING(account)
         ORDER BY f.cutoff_date,f.ruc,f.account'''
    buckets={};bar=progress.row_bar(expected,'Migración SQLite → Parquet') if progress else None
    try:
        for chunk in pd.read_sql_query(q,con,chunksize=int(mcfg.get('migration_chunk_rows',100000))):
            chunk['cutoff_date']=chunk['cutoff_date'].astype(str)
            dt=pd.to_datetime(chunk.cutoff_date,errors='coerce')
            for (yy,mm),g in chunk.groupby([dt.dt.year,dt.dt.month]):
                if pd.isna(yy) or pd.isna(mm):continue
                buckets.setdefault((int(yy),int(mm)),[]).append(g.copy())
            if bar is not None:bar.update(len(chunk))
    finally:
        if bar is not None:bar.close()
    # write locally with direct paths, not persistent project paths
    local_files=[];rows=0
    for (yy,mm),parts in sorted(buckets.items()):
        d=_dedupe(pd.concat(parts,ignore_index=True));rows+=len(d)
        p=local_root/'data/parquet/eeff'/f'year={yy:04d}'/f'month={mm:02d}'/'eeff.parquet';_atomic_parquet(d,p);local_files.append(p)
    # verify using DuckDB over local Parquet. Imported lazily so normal install tells us clearly if dependency is missing.
    import duckdb
    glob=(local_root/'data/parquet/eeff/year=*/month=*/eeff.parquet').as_posix()
    dc=duckdb.connect(':memory:');actual=dc.execute(f"SELECT count(*) FROM read_parquet('{glob}', hive_partitioning=true)").fetchone()[0]
    actual_keys=dc.execute(f"SELECT count(*) FROM (SELECT cutoff_date,ruc,account FROM read_parquet('{glob}', hive_partitioning=true) GROUP BY 1,2,3)").fetchone()[0];dc.close()
    verified=(expected==actual==expected_keys==actual_keys)
    if not verified:
        con.close();raise RuntimeError(f'Migración no verificada: SQLite rows={expected}, keys={expected_keys}; Parquet rows={actual}, keys={actual_keys}')
    # Prepare state from SQLite before deleting it.
    try:
        cat=[dict(r) for r in con.execute('SELECT source_key,title,page_url,url,period_year,first_discovered_at,last_seen_at FROM source_catalog').fetchall()]
    except Exception:cat=[]
    try:
        srcrows=[dict(r) for r in con.execute("SELECT source_key,title,url,source_sha256,byte_size,rows_source,rows_segment,rows_inserted,rows_updated,qa_status,downloaded_at FROM dim_source WHERE qa_status='ok'").fetchall()]
    except Exception:srcrows=[]
    try:
        events=pd.read_sql_query('SELECT * FROM entity_event',con)
    except Exception:events=pd.DataFrame()
    try:
        meta_rows=con.execute('SELECT key,value FROM app_meta').fetchall();old_meta={r[0]:r[1] for r in meta_rows}
    except Exception:old_meta={}
    con.close()
    # Free legacy storage before copying verified parquet if requested.
    deleted=False
    if bool(mcfg.get('delete_legacy_sqlite_after_verified_migration',True)):
        for base in {drive_src, src}:
            for suffix in ('','-wal','-shm'):
                p=Path(str(base)+suffix)
                if p.exists():p.unlink()
        deleted=True
    # Copy partitions one by one to Drive.
    for p in local_files:
        rel=p.relative_to(local_root);dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_suffix('.parquet.tmp');shutil.copy2(p,tmp);os.replace(tmp,dest)
    # reconstruct partition manifest and source state
    man={'updated_at':utcnow(),'sources':{},'partitions':{}}
    for p in eeff_files(root):
        d=pd.read_parquet(p,engine='pyarrow');yy=int(p.parent.parent.name.split('=')[1]);mm=int(p.parent.name.split('=')[1]);key=f'{yy:04d}-{mm:02d}'
        man['partitions'][key]={'year':yy,'month':mm,'rows':len(d),'sha256':_partition_fingerprint(d),'path':str(p.relative_to(root)),'updated_at':utcnow(),'source_title':'migrated_sqlite'}
    for r in srcrows:
        key=f"{r.get('source_key')}|{r.get('title')}";man['sources'][key]={'source_key':r.get('source_key'),'title':r.get('title'),'url':r.get('url'),'source_sha256':r.get('source_sha256'),'byte_size':r.get('byte_size'),'qa_status':'ok','rows_source':r.get('rows_source'),'rows_segment':r.get('rows_segment'),'inserted':r.get('rows_inserted') or 0,'updated':r.get('rows_updated') or 0,'unchanged':0,'processed_at':r.get('downloaded_at')}
    save_ingestion_manifest(man,root)
    if cat:save_source_catalog(cat,root)
    if old_meta:
        from .state import save_json
        save_json('app_meta.json',old_meta,root)
    if not events.empty:
        ep=parquet_root(root)/'events'/'events.parquet';_atomic_parquet(events,ep)
    report={'needed':True,'verified':True,'legacy_rows':expected,'parquet_rows':actual,'partitions':len(local_files),'legacy_deleted':deleted,'legacy_source':str(src),'legacy_sha256':sha256_file(local_db),'finished_at':utcnow()}
    from .state import save_json
    save_json('migration_009.json',report,root);shutil.rmtree(runtime,ignore_errors=True);return report
