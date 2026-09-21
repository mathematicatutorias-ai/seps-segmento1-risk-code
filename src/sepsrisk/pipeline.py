from pathlib import Path
from datetime import date, datetime, timezone
import json,re,shutil

from .config import load_yaml,project_root
from .sources.discovery import discover_source_items
from .ingestion.downloader import download
from .ingestion.parser import extract_or_list
from .utils import sha256_file,utcnow,ensure_clean_dir
from .features.engine import build_features
from .inference.signals import build_signals
from .inference.survival import record_readiness
from .reporting.export_dashboard import export_dashboard,rebuild_index
from .atlas.build import build_atlas
from .progress import PipelineProgress
from .storage.state import source_catalog,save_source_catalog,meta_get,meta_set
from .storage.parquet_store import (migrate_legacy_sqlite,ingest_eeff_files,mark_source,source_record,
    source_sha_seen,storage_summary,has_eeff)
from .storage.analytics import open_analytics


def _write_state(root,state):
    (root/'atlas').mkdir(exist_ok=True);(root/'atlas'/'latest_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')

def _source_year(title):
    m=re.search(r'(20\d{2})',str(title));return int(m.group(1)) if m else None

def _resume_skip_completed(source_key,item,cfg,root):
    p=cfg.get('progress',{})
    if p.get('force_recheck_all_sources',False) or not p.get('resume_skip_completed_closed_periods',True):return False
    rec=source_record(source_key,item['title'],root)
    if not rec or rec.get('qa_status')!='ok':return False
    yr=_source_year(item['title'])
    return not (yr==date.today().year and p.get('recheck_current_period',True))

def _needs_full_discovery(cfg,source_key,root):
    p=cfg.get('progress',{})
    if p.get('discovery_force_full_scan',False) or not p.get('discovery_cache_enabled',True):return True
    last=meta_get(f'discovery_full_scan:{source_key}',root)
    if not last:return True
    try:
        dt=datetime.fromisoformat(str(last).replace('Z','+00:00'));dt=dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/86400>=max(1,int(p.get('discovery_full_refresh_days',30)))
    except Exception:return True

def _discover_cached_items(root,source_key,spec,cfg,on_page=None,diagnostics=None):
    p=cfg.get('progress',{});full=_needs_full_discovery(cfg,source_key,root)
    limit=int(spec.get('max_pages',10)) if full else min(int(spec.get('max_pages',10)),max(1,int(p.get('discovery_incremental_pages',3))))
    workers=max(1,int(p.get('discovery_parallel_workers',6)))
    fresh=discover_source_items(source_key,root,on_page=on_page,diagnostics=diagnostics,page_limit=limit,parallel_workers=workers)
    cached=source_catalog(root).get('items',[]) if p.get('discovery_cache_enabled',True) else []
    # Seed cache from manifest so an upgrade from SQLite/cache-less releases still resumes.
    from .storage.state import ingestion_manifest
    for rec in ingestion_manifest(root).get('sources',{}).values():
        if rec.get('source_key')==source_key:
            cached.append({'source_key':source_key,'title':rec.get('title'),'page_url':rec.get('page_url') or rec.get('url'),'url':rec.get('url')})
    merged={}
    for x in cached+fresh:
        if x.get('source_key')==source_key and x.get('title'):merged[x['title']]=x
    save_source_catalog(list(merged.values()),root)
    if full and fresh:meta_set(f'discovery_full_scan:{source_key}',utcnow(),root)
    return list(merged.values()),{'mode':'full' if full else 'incremental','page_limit':limit,'workers':workers,'fresh':len(fresh),'cached':len(cached)}

def _write_load_status(root,cfg,state,total,completed,current=None,phase='running',con=None):
    out=root/cfg['paths']['githubpage']/'data';out.mkdir(parents=True,exist_ok=True);st=storage_summary(root)
    payload={'phase':phase,'updated_at':utcnow(),'sources_completed':int(completed),'sources_total':int(total),'current_source':current,
             'inserted':int(state.get('inserted',0)),'updated':int(state.get('updated',0)),'unchanged':int(state.get('unchanged',0)),
             'resume_skipped':int(state.get('resume_skipped',0)),'sha_skipped':int(state.get('source_sha_skipped',0)),**st}
    if con is not None:
        try:
            q=con.execute('SELECT min(cutoff_date),max(cutoff_date),count(*),count(distinct ruc) FROM fact_eeff').fetchone();payload.update({'first_cutoff':q[0],'last_cutoff':q[1],'fact_rows':int(q[2] or 0),'entities':int(q[3] or 0)})
        except Exception:pass
    raw=json.dumps(payload,ensure_ascii=False,indent=2);(out/'load_status.json').write_text(raw,encoding='utf-8');(out/'load_status.js').write_text('window.SEPS_LOAD_STATUS = '+json.dumps(payload,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    try:rebuild_index(root,{**payload,'generated_at':payload['updated_at']})
    except Exception:pass
    return payload

def _refresh_dashboard(root,ui,idx,total,title,state,cfg):
    con=open_analytics(root)
    ui.note('dashboard parcial',f'{idx}/{total} · {title} · DuckDB sobre Parquet')
    build_features(con,root);build_signals(con,root);record_readiness(con,root)
    _write_load_status(root,cfg,state,total,idx,title,'partial' if idx<total else 'loaded',con)
    dash=export_dashboard(con,root);con.close();ui.note('HTML actualizado',f"{idx}/{total} · {dash.get('entities',0)} entidades · build {dash.get('build_id','—')}");return dash

def run(root=None,ingest=True,show_progress=True):
    root=Path(root) if root else project_root();cfg=load_yaml('project.yaml',root);ui=PipelineProgress(cfg=cfg.get('progress',{}), enabled=show_progress)
    S={'started_at':utcnow(),'backend':'parquet+duckdb','sources_checked':0,'sources_discovered':0,'inserted':0,'updated':0,'unchanged':0,'resume_skipped':0,'source_sha_skipped':0,'errors':[],'warnings':[],'discovery':{'diagnostics':[]}}
    temp=root/cfg['paths']['temp'];ensure_clean_dir(temp)
    try:
        ui.set(2,'preparando storage','Parquet canónico + DuckDB efímero')
        mig=migrate_legacy_sqlite(root,progress=ui);S['migration']=mig
        if mig.get('needed'):
            ui.note('migración 009',f"SQLite → {mig.get('partitions')} Parquet · verificada · legacy_deleted={mig.get('legacy_deleted')}")
            _refresh_dashboard(root,ui,0,0,'migración SQLite',S,cfg)
        if ingest:
            enabled=[(k,v) for k,v in load_yaml('sources.yaml',root)['sources'].items() if v.get('enabled')]
            plans=[];total_pages=0
            for key,spec in enabled:
                full=_needs_full_discovery(cfg,key,root);limit=int(spec.get('max_pages',10)) if full else min(int(spec.get('max_pages',10)),max(1,int(cfg.get('progress',{}).get('discovery_incremental_pages',3))))
                plans.append((key,spec,limit));total_pages+=len(spec.get('discovery_pages',[]))*limit
            pages_done=0;discovered=[];modes=[]
            def on_page(status):
                nonlocal pages_done
                pages_done+=1;detail=f"{status.get('source_key')} · pág. {status.get('page')}";detail+=f" · {status.get('matches')} match" if status.get('matches') else ''
                ui.discovery(pages_done,max(1,total_pages),detail)
            for key,spec,limit in plans:
                diagnostics=[];items,info=_discover_cached_items(root,key,spec,cfg,on_page,diagnostics);S['discovery']['diagnostics'].extend(diagnostics);modes.append({key:info})
                for item in items:discovered.append((key,spec,item))
            uniq={(k,i['title']):(k,s,i) for k,s,i in discovered};discovered=sorted(uniq.values(),key=lambda z:(_source_year(z[2]['title']) or 0),reverse=True)
            S['sources_discovered']=len(discovered);S['discovery']['modes']=modes;ui.set(20,'fuentes descubiertas',f'{len(discovered)} publicación(es) · cache incremental')
            if not discovered and not has_eeff(root):raise RuntimeError('No se descubrió ninguna fuente EEFF y no existen Parquet previos.')
            total=len(discovered);_write_load_status(root,cfg,S,total,0,None,'starting')
            chunksize=int(cfg.get('progress',{}).get('chunk_rows',50000));live_every=max(1,int(cfg.get('progress',{}).get('live_dashboard_every_sources',1)))
            for idx,(key,spec,item) in enumerate(discovered,start=1):
                S['sources_checked']+=1
                if _resume_skip_completed(key,item,cfg,root):
                    S['resume_skipped']+=1;ui.ingestion(idx,total,f'{item["title"]} · Parquet ya consolidado · resume');_write_load_status(root,cfg,S,total,idx,item['title'],'resume_skip');continue
                work=temp/f'source_{idx}';work.mkdir(parents=True,exist_ok=True);ui.ingestion(idx-1,total,f'{idx}/{total} · {item["title"]} · descargando')
                try:
                    fp=download(item['url'],work/'download.bin',root,progress=ui,label=item['title']);sha=sha256_file(fp)
                    if source_sha_seen(sha,root):
                        S['source_sha_skipped']+=1;ui.ingestion(idx,total,f'{item["title"]} · SHA fuente sin cambios');_write_load_status(root,cfg,S,total,idx,item['title'],'sha_unchanged');continue
                    files=extract_or_list(fp,work/'extract');ui.note('Parquet incremental',f'{item["title"]} · comparando particiones mensuales')
                    result=ingest_eeff_files(files,spec,cfg['universe']['segment'],root,source={**item,'sha256':sha},progress=ui,chunksize=chunksize)
                    if result['rows_segment']==0:raise RuntimeError('La fuente produjo 0 filas del Segmento configurado.')
                    mark_source(key,item,sha,fp.stat().st_size,result,root,'ok')
                    for k in ('inserted','updated','unchanged'):S[k]+=int(result.get(k,0))
                    ui.ingestion(idx,total,f"{item['title']} · COMMIT Parquet · {result['partitions_written']} partición(es) escritas · +{result['inserted']:,} / Δ{result['updated']:,}")
                    _write_load_status(root,cfg,S,total,idx,item['title'],'committed')
                    if idx%live_every==0 or idx==total:_refresh_dashboard(root,ui,idx,total,item['title'],S,cfg)
                except Exception as e:
                    S['errors'].append({'source':item.get('title'),'error':repr(e)});ui.ingestion(idx,total,f'{item["title"]} · ERROR');_write_load_status(root,cfg,S,total,idx-1,item['title'],'error')
                finally:shutil.rmtree(work,ignore_errors=True)
        con=open_analytics(root)
        ui.set(72,'construyendo features','DuckDB lee Parquet directamente');S['features']=build_features(con,root)
        ui.set(82,'calculando señales','deterioro + anomalías');S['signals']=build_signals(con,root)
        ui.set(88,'evaluando inferencia','gate 6/12/18 meses');S['inference']=record_readiness(con,root)
        _write_load_status(root,cfg,S,S.get('sources_discovered',0),S.get('sources_discovered',0),None,'complete',con)
        ui.set(93,'exportando dashboard','githubpage/index.html');S['dashboard']=export_dashboard(con,root);con.close()
        S['storage']=storage_summary(root);S['finished_at']=utcnow();_write_state(root,S);ui.set(97,'reconstruyendo Atlas','lineage Parquet + DuckDB + handoff');S['atlas']=build_atlas(root,S);_write_state(root,S)
        ui.close(True,f"{S['sources_checked']} fuente(s) · {S['inserted']} nuevas · {S['updated']} actualizadas · {S['resume_skipped']} resume");return S
    finally:
        shutil.rmtree(temp,ignore_errors=True);temp.mkdir(parents=True,exist_ok=True)
