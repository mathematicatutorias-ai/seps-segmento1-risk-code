from pathlib import Path
import ast, hashlib, json, re, sqlite3, zipfile, shutil
from ..config import load_yaml,project_root
from ..utils import utcnow

TEXT_EXT={'.py','.md','.yaml','.yml','.json','.sql','.html','.css','.js','.toml','.txt','.ipynb'}
EXCLUDE_PARTS={'.git','__pycache__','.pytest_cache','.ipynb_checkpoints'}
EXCLUDE_PREFIXES=('data/operational/','data/parquet/','data/state/','data/temp/','atlas/handoff/','atlas/snapshots/','githubpage/data/')
ATLAS_GENERATED={'atlas/atlas.json','atlas/atlas.sqlite','atlas/atlas.html','atlas/latest_state.json','atlas/CODE_ATLAS.json','atlas/DEPENDENCY_GRAPH.json','atlas/DATA_LINEAGE_GRAPH.json','atlas/STATE_MANIFEST.json','atlas/RELEASE_MANIFEST.json'}


def _sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def _rel(root,p):return p.relative_to(root).as_posix()

def _project_files(root):
    out=[]
    for p in root.rglob('*'):
        if not p.is_file():continue
        rel=_rel(root,p)
        if any(x in p.parts for x in EXCLUDE_PARTS):continue
        if rel.startswith(EXCLUDE_PREFIXES) or rel in ATLAS_GENERATED:continue
        if p.suffix.lower() not in TEXT_EXT:continue
        out.append(p)
    return sorted(out)

def _module_from_path(root,p):
    try:r=p.relative_to(root/'src').with_suffix('')
    except ValueError:return None
    return '.'.join(r.parts)

def _python_nodes_edges(root,files):
    nodes=[];edges=[];module_map={}
    for p in files:
        if p.suffix!='.py':continue
        mod=_module_from_path(root,p)
        if mod:module_map[mod]=_rel(root,p)
    for p in files:
        if p.suffix!='.py':continue
        rel=_rel(root,p);fid='file:'+rel
        try:tree=ast.parse(p.read_text(encoding='utf-8'))
        except Exception:continue
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                kind='class' if isinstance(node,ast.ClassDef) else 'function';nid=f'{kind}:{rel}:{node.name}'
                nodes.append({'id':nid,'kind':kind,'name':node.name,'path':rel,'lineno':getattr(node,'lineno',None)})
                edges.append({'from':fid,'to':nid,'type':'CONTAINS'})
        cur_mod=_module_from_path(root,p)
        for node in ast.walk(tree):
            targets=[]
            if isinstance(node,ast.Import):targets=[a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom):
                if node.module:
                    base=node.module
                    if node.level and cur_mod:
                        parts=cur_mod.split('.')[:-1]
                        base='.'.join(parts[:max(0,len(parts)-node.level+1)]+[node.module])
                    targets=[base]
            for t in targets:
                match=None
                for m,r in module_map.items():
                    if t==m or t.startswith(m+'.') or m.startswith(t+'.'):
                        match=r;break
                if match:edges.append({'from':fid,'to':'file:'+match,'type':'IMPORTS'})
    return nodes,edges

def _sql_tables(root):
    schema=root/'sql'/'schema.sql';out=[]
    if not schema.exists():return out
    txt=schema.read_text(encoding='utf-8')
    for m in re.finditer(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z0-9_]+)',txt,re.I):
        out.append(m.group(1))
    return out

def _lineage():
    nodes=[
      {'id':'source:SEPS_EEFF','kind':'source','label':'SEPS · EEFF mensuales'},
      {'id':'process:discovery','kind':'process','label':'Discovery cacheado + incremental'},
      {'id':'artifact:source_catalog','kind':'state','label':'data/state/source_catalog.json'},
      {'id':'process:ingestion','kind':'process','label':'Descarga + parseo + filtro Segmento 1'},
      {'id':'artifact:parquet_eeff','kind':'dataset','label':'Parquet EEFF year/month'},
      {'id':'process:duckdb','kind':'process','label':'DuckDB efímero sobre Parquet'},
      {'id':'process:features','kind':'process','label':'Features financieras'},
      {'id':'process:signals','kind':'process','label':'Señales robustas'},
      {'id':'process:survival','kind':'process','label':'Hazard / supervivencia'},
      {'id':'process:dashboard_export','kind':'process','label':'Export dashboard'},
      {'id':'artifact:githubpage','kind':'artifact','label':'githubpage/'},
      {'id':'process:github_publish','kind':'process','label':'Publicación segura de código a GitHub'},
      {'id':'artifact:github_code_repo','kind':'artifact','label':'github.com/mathematicatutorias-ai/seps-segmento1-risk-code'},
    ]
    edges=[
      {'from':'source:SEPS_EEFF','to':'process:discovery','type':'DISCOVERED_BY'},
      {'from':'process:discovery','to':'artifact:source_catalog','type':'WRITES'},
      {'from':'artifact:source_catalog','to':'process:ingestion','type':'FEEDS'},
      {'from':'process:ingestion','to':'artifact:parquet_eeff','type':'WRITES_PARTITIONS'},
      {'from':'artifact:parquet_eeff','to':'process:duckdb','type':'READS'},
      {'from':'process:duckdb','to':'process:features','type':'FEEDS'},
      {'from':'process:features','to':'process:signals','type':'FEEDS'},
      {'from':'process:features','to':'process:survival','type':'FEEDS'},
      {'from':'process:features','to':'process:dashboard_export','type':'FEEDS'},
      {'from':'process:signals','to':'process:dashboard_export','type':'FEEDS'},
      {'from':'process:survival','to':'process:dashboard_export','type':'FEEDS'},
      {'from':'process:dashboard_export','to':'artifact:githubpage','type':'GENERATES'},
      {'from':'artifact:githubpage','to':'process:github_publish','type':'INCLUDED_IN'},
      {'from':'process:github_publish','to':'artifact:github_code_repo','type':'PUBLISHES'},
    ]
    return {'nodes':nodes,'edges':edges}

def _db_state(root,cfg):
    try:
        from ..storage.parquet_store import storage_summary
        return storage_summary(root)
    except Exception as e:
        return {'backend':'parquet+duckdb','error':repr(e)}

def _write_atlas_db(path,nodes,edges,files):
    if path.exists():path.unlink()
    con=sqlite3.connect(path)
    con.executescript('''
    CREATE TABLE node(id TEXT PRIMARY KEY,kind TEXT,label TEXT,path TEXT,metadata_json TEXT);
    CREATE TABLE edge(src TEXT,dst TEXT,type TEXT,metadata_json TEXT,PRIMARY KEY(src,dst,type));
    CREATE TABLE file(path TEXT PRIMARY KEY,sha256 TEXT,size INTEGER,kind TEXT);
    ''')
    for n in nodes:con.execute('INSERT OR REPLACE INTO node VALUES(?,?,?,?,?)',(n['id'],n.get('kind'),n.get('label') or n.get('name'),n.get('path'),json.dumps(n,ensure_ascii=False)))
    for e in edges:con.execute('INSERT OR REPLACE INTO edge VALUES(?,?,?,?)',(e['from'],e['to'],e.get('type','DEPENDS_ON'),json.dumps(e,ensure_ascii=False)))
    for f in files:con.execute('INSERT OR REPLACE INTO file VALUES(?,?,?,?)',(f['path'],f['sha256'],f['size'],f['kind']))
    con.commit();con.close()

def _validate(root,nodes,edges):
    ids={n['id'] for n in nodes};unresolved=[]
    for e in edges:
        if e['from'] not in ids:unresolved.append({'type':'missing_from','edge':e})
        if e['to'] not in ids:unresolved.append({'type':'missing_to','edge':e})
    required=['MASTER_SEPS.ipynb','config/project.yaml','githubpage/index.html','src/sepsrisk/pipeline.py','src/sepsrisk/storage/parquet_store.py','src/sepsrisk/storage/analytics.py']
    for r in required:
        if not (root/r).exists():unresolved.append({'type':'missing_required_artifact','path':r})
    return unresolved

def _handoff_members(root,cfg):
    include_files=['MASTER_SEPS.ipynb','README.md','CHANGELOG.md','CONTRATO.md','pyproject.toml','PROJECT_TREE.txt']
    include_dirs=['config','contracts','src','scripts','sql','tests','notebooks']
    if cfg.get('atlas',{}).get('include_githubpage_shell',True):include_dirs+=['githubpage/assets'];include_files+=['githubpage/index.html']
    atlas_files=['atlas/CODE_ATLAS.json','atlas/DEPENDENCY_GRAPH.json','atlas/DATA_LINEAGE_GRAPH.json','atlas/STATE_MANIFEST.json','atlas/RELEASE_MANIFEST.json','atlas/latest_state.json','atlas/atlas.html','atlas/atlas.sqlite','atlas/README.md']
    members=[]
    for rel in include_files+atlas_files:
        p=root/rel
        if p.exists() and p.is_file():members.append(p)
    for rel in include_dirs:
        p=root/rel
        if p.exists():
            for f in p.rglob('*'):
                if f.is_file() and not any(x in f.parts for x in EXCLUDE_PARTS):members.append(f)
    # avoid generated entity payloads and binaries
    uniq=[];seen=set()
    for p in sorted(members):
        rel=_rel(root,p)
        if rel.startswith('githubpage/data/entities/') or rel.startswith('data/') or rel.startswith('atlas/handoff/'):continue
        if rel not in seen:seen.add(rel);uniq.append(p)
    return uniq

def _create_handoff(root,cfg):
    hand=root/'atlas'/'handoff';snap=hand/'snapshots';hand.mkdir(parents=True,exist_ok=True);snap.mkdir(parents=True,exist_ok=True)
    stamp=re.sub(r'\D','',utcnow())[:14]
    prefix=cfg.get('atlas',{}).get('snapshot_prefix','SEPS_STATE');latest=hand/cfg.get('atlas',{}).get('handoff_filename','LATEST_STATE.zip');dated=snap/f'{prefix}_{stamp}.zip'
    members=_handoff_members(root,cfg)
    for target in [latest,dated]:
        if target.exists():target.unlink()
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for p in members:z.write(p,_rel(root,p))
    keep=int(cfg.get('atlas',{}).get('keep_snapshots',5));old=sorted(snap.glob(f'{prefix}_*.zip'),key=lambda p:p.stat().st_mtime,reverse=True)
    for p in old[keep:]:p.unlink()
    return {'latest':_rel(root,latest),'snapshot':_rel(root,dated),'files':len(members),'sha256':_sha(latest)}

def build_atlas(root=None,run_state=None):
    root=Path(root) if root else project_root();cfg=load_yaml('project.yaml',root);adir=root/cfg['paths']['atlas'];adir.mkdir(parents=True,exist_ok=True)
    files=[];nodes=[];edges=[]
    for p in _project_files(root):
        rel=_rel(root,p);kind='code' if p.suffix in {'.py','.js','.html','.css','.sql'} else 'document'
        files.append({'path':rel,'sha256':_sha(p),'size':p.stat().st_size,'kind':kind})
        nodes.append({'id':'file:'+rel,'kind':'file','path':rel,'label':rel,'sha256':files[-1]['sha256']})
    pnodes,pedges=_python_nodes_edges(root,[root/f['path'] for f in files]);nodes+=pnodes;edges+=pedges
    for t in _sql_tables(root):
        nid='table:'+t
        if not any(n['id']==nid for n in nodes):nodes.append({'id':nid,'kind':'table','label':t})
        edges.append({'from':'file:sql/schema.sql','to':nid,'type':'DEFINES'})
    lin=_lineage()
    for n in lin['nodes']:
        if not any(x['id']==n['id'] for x in nodes):nodes.append(n)
    edges+=lin['edges']
    # Map key implementation files into lineage.
    mappings=[
      ('file:src/sepsrisk/sources/discovery.py','process:discovery','IMPLEMENTS'),
      ('file:src/sepsrisk/storage/parquet_store.py','process:ingestion','IMPLEMENTS'),
      ('file:src/sepsrisk/storage/analytics.py','process:duckdb','IMPLEMENTS'),
      ('file:src/sepsrisk/features/engine.py','process:features','IMPLEMENTS'),
      ('file:src/sepsrisk/inference/signals.py','process:signals','IMPLEMENTS'),
      ('file:src/sepsrisk/inference/survival.py','process:survival','IMPLEMENTS'),
      ('file:src/sepsrisk/reporting/export_dashboard.py','process:dashboard_export','IMPLEMENTS'),
      ('file:githubpage/index.html','artifact:githubpage','PART_OF'),
      ('file:src/sepsrisk/publication/github.py','process:github_publish','IMPLEMENTS'),
    ]
    edges += [{'from':a,'to':b,'type':t} for a,b,t in mappings if any(n['id']==a for n in nodes)]
    unresolved=_validate(root,nodes,edges)
    dep={'generated_at':utcnow(),'nodes':nodes,'edges':edges,'validation':{'unresolved':len(unresolved),'issues':unresolved}}
    code={'generated_at':dep['generated_at'],'files':files,'symbols':[n for n in nodes if n.get('kind') in {'function','class'}]}
    state={'generated_at':dep['generated_at'],'project':cfg['project'],'release':cfg.get('release',{}),'database':_db_state(root,cfg),'run_state':run_state or {},'validation':dep['validation']}
    release={'generated_at':dep['generated_at'],'project':cfg['project']['name'],'version':cfg['project']['version'],'update':cfg.get('release',{}).get('update'),'file_count':len(files),'project_sha256':hashlib.sha256('\n'.join(f"{f['path']}:{f['sha256']}" for f in files).encode()).hexdigest()}
    (adir/'CODE_ATLAS.json').write_text(json.dumps(code,ensure_ascii=False,indent=2),encoding='utf-8')
    (adir/'DEPENDENCY_GRAPH.json').write_text(json.dumps(dep,ensure_ascii=False,indent=2),encoding='utf-8')
    (adir/'DATA_LINEAGE_GRAPH.json').write_text(json.dumps({'generated_at':dep['generated_at'],**lin},ensure_ascii=False,indent=2),encoding='utf-8')
    (adir/'STATE_MANIFEST.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    (adir/'RELEASE_MANIFEST.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8')
    # Backward-compatible atlas.json.
    (adir/'atlas.json').write_text(json.dumps(dep,ensure_ascii=False,indent=2),encoding='utf-8')
    _write_atlas_db(adir/'atlas.sqlite',nodes,edges,files)
    html='''<!doctype html><meta charset="utf-8"><title>Atlas · SEPS S1 Risk</title><style>body{font-family:system-ui;margin:36px;color:#10233f}code{background:#eef3f8;padding:3px 5px;border-radius:4px}.ok{color:#12805c}.bad{color:#b42332}table{border-collapse:collapse;width:100%}td,th{padding:7px;border-bottom:1px solid #e5eaf1;text-align:left}</style><h1>Atlas · SEPS S1 Risk</h1><div id="s"></div><h2>Lineage</h2><div id="l"></div><script>Promise.all([fetch('STATE_MANIFEST.json').then(r=>r.json()),fetch('DATA_LINEAGE_GRAPH.json').then(r=>r.json())]).then(([s,l])=>{let u=s.validation?.unresolved||0;document.querySelector('#s').innerHTML=`<p>Versión <b>${s.project.version}</b> · Update <b>${s.release.update}</b> · unresolved: <b class="${u?'bad':'ok'}">${u}</b></p><p>Último corte: <b>${s.database.last_period||'—'}</b></p>`;document.querySelector('#l').innerHTML=l.edges.map(e=>`<p><code>${e.from}</code> —${e.type}→ <code>${e.to}</code></p>`).join('')})</script>'''
    (adir/'atlas.html').write_text(html,encoding='utf-8')
    handoff=_create_handoff(root,cfg)
    state['handoff']=handoff;(adir/'STATE_MANIFEST.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'nodes':len(nodes),'edges':len(edges),'files':len(files),'unresolved':len(unresolved),'handoff':handoff}
