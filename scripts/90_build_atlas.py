from sepsrisk.atlas.build import build_atlas
import json
print(json.dumps(build_atlas(),ensure_ascii=False,indent=2))
