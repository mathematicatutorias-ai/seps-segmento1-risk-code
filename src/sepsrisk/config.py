from pathlib import Path
import yaml
def project_root(start=None):
    p=Path(start or Path.cwd()).resolve()
    for c in [p,*p.parents]:
        if (c/'config'/'project.yaml').exists(): return c
    raise FileNotFoundError('No se encontró config/project.yaml')
def load_yaml(name,root=None):
    root=Path(root) if root else project_root()
    return yaml.safe_load((root/'config'/name).read_text(encoding='utf-8'))
