from pathlib import Path
import argparse, json
from sepsrisk.publication.github import publish_project

ap=argparse.ArgumentParser()
ap.add_argument('--project-root',default='.')
ap.add_argument('--message',default=None)
ap.add_argument('--dry-run',action='store_true')
a=ap.parse_args()
print(json.dumps(publish_project(Path(a.project_root),commit_message=a.message,dry_run=a.dry_run),ensure_ascii=False,indent=2))
