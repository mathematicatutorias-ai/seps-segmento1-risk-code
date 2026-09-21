from __future__ import annotations
from pathlib import Path
import fnmatch, os, re, shutil, stat, subprocess, tempfile
from ..config import load_yaml

TEXT_SCAN_EXT={'.py','.md','.yaml','.yml','.json','.sql','.html','.css','.js','.toml','.txt','.ipynb','.gitignore'}
DEFAULT_EXCLUDED_DIRS={'.git','__pycache__','.pytest_cache','.ipynb_checkpoints'}
SECRET_PATTERNS=[
    re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'ghp_[A-Za-z0-9]{20,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
]

def _cfg(root:Path):
    p=root/'config'/'github.yaml'
    if not p.exists(): raise FileNotFoundError(f'No existe {p}')
    import yaml
    return yaml.safe_load(p.read_text(encoding='utf-8'))['github']

def _is_excluded(rel:str, patterns:list[str]):
    rel=rel.replace('\\','/')
    parts=rel.split('/')
    if any(p in DEFAULT_EXCLUDED_DIRS for p in parts): return True
    for pat in patterns:
        pat=pat.replace('\\','/')
        if pat.endswith('/') and (rel==pat[:-1] or rel.startswith(pat)): return True
        if fnmatch.fnmatch(rel,pat) or fnmatch.fnmatch(Path(rel).name,pat): return True
    return False

def collect_publish_files(root):
    root=Path(root); g=_cfg(root); patterns=list(g.get('exclude',[])); out=[]
    for p in root.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(root).as_posix()
        if _is_excluded(rel,patterns): continue
        out.append((p,rel))
    return sorted(out,key=lambda x:x[1])

def preflight(root, max_file_mb=50):
    root=Path(root); files=collect_publish_files(root); issues=[]; total=0
    for p,rel in files:
        size=p.stat().st_size; total+=size
        if size>max_file_mb*1024*1024: issues.append(f'Archivo demasiado grande para publicación: {rel} ({size/1024/1024:.1f} MB)')
        if p.suffix.lower() in TEXT_SCAN_EXT or p.name=='.gitignore':
            try: txt=p.read_text(encoding='utf-8',errors='ignore')
            except Exception: txt=''
            for rx in SECRET_PATTERNS:
                if rx.search(txt): issues.append(f'Posible secreto detectado en {rel}: patrón {rx.pattern}')
    return {'files':len(files),'bytes':total,'issues':issues,'paths':[r for _,r in files]}

def _run(cmd,cwd=None,env=None,check=True):
    return subprocess.run(cmd,cwd=cwd,env=env,check=check,text=True,capture_output=True)

def _token(secret_name):
    try:
        from google.colab import userdata
        token=userdata.get(secret_name)
    except Exception:
        token=os.environ.get(secret_name)
    if not token: raise RuntimeError(f'Falta el secreto {secret_name}. En Colab: icono de llave → Secrets → {secret_name}.')
    return token

def _askpass(token, username='git'):
    d=Path(tempfile.mkdtemp(prefix='seps_git_askpass_')); p=d/'askpass.sh'
    p.write_text('#!/bin/sh\ncase "$1" in\n  *Username*) printf "%s\\n" "$GITHUB_USERNAME" ;;\n  *Password*) printf "%s\\n" "$GITHUB_TOKEN" ;;\n  *) echo "" ;;\nesac\n',encoding='utf-8')
    p.chmod(p.stat().st_mode|stat.S_IXUSR)
    env=os.environ.copy(); env.update({'GIT_ASKPASS':str(p),'GIT_TERMINAL_PROMPT':'0','GITHUB_TOKEN':token,'GITHUB_USERNAME':username})
    return d,env

def publish_project(root, commit_message=None, dry_run=False):
    root=Path(root).resolve(); g=_cfg(root); pf=preflight(root)
    if pf['issues']: raise RuntimeError('Preflight GitHub falló:\n- '+'\n- '.join(pf['issues']))
    if dry_run: return {'status':'dry_run','files':pf['files'],'bytes':pf['bytes'],'remote':g['remote_url'],'branch':g.get('branch','main')}
    token=_token(g.get('secret_name','GITHUB_TOKEN')); askdir,env=_askpass(token,g.get('owner','git'))
    stage=Path('/content/seps-segmento1-risk-code-publish') if Path('/content').exists() else Path(tempfile.gettempdir())/'seps-segmento1-risk-code-publish'
    if stage.exists(): shutil.rmtree(stage)
    try:
        clone=_run(['git','clone','--no-tags',g['remote_url'],str(stage)],env=env,check=False)
        if clone.returncode!=0: raise RuntimeError(f'git clone falló: {clone.stderr.strip()}')
        # Vaciar working tree conservando .git y reconstruir snapshot publicable.
        for child in stage.iterdir():
            if child.name=='.git': continue
            if child.is_dir(): shutil.rmtree(child)
            else: child.unlink()
        for src,rel in collect_publish_files(root):
            dst=stage/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        branch=g.get('branch','main')
        _run(['git','checkout','-B',branch],cwd=stage,env=env)
        _run(['git','config','user.name',g.get('author_name','MathematicaTutorias AI')],cwd=stage,env=env)
        _run(['git','config','user.email',g.get('author_email','mathematicatutorias-ai@users.noreply.github.com')],cwd=stage,env=env)
        _run(['git','add','-A'],cwd=stage,env=env)
        status=_run(['git','status','--porcelain'],cwd=stage,env=env).stdout.strip()
        if status:
            msg=commit_message or g.get('commit_message','Release 015')
            _run(['git','commit','-m',msg],cwd=stage,env=env)
        push=_run(['git','push','-u','origin',branch],cwd=stage,env=env,check=False)
        if push.returncode!=0: raise RuntimeError(f'git push falló: {push.stderr.strip()}')
        head=_run(['git','rev-parse','HEAD'],cwd=stage,env=env).stdout.strip()
        return {'status':'pushed' if status else 'up_to_date','files':pf['files'],'bytes':pf['bytes'],'remote':g['remote_url'],'branch':branch,'commit':head}
    finally:
        shutil.rmtree(askdir,ignore_errors=True)
