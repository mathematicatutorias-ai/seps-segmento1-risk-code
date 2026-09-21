from pathlib import Path
from sepsrisk.atlas.build import build_atlas

def test_atlas_handoff(tmp_path):
    # El builder real requiere la estructura del proyecto, por lo que se prueba sobre el root instalado.
    root=Path(__file__).resolve().parents[1]
    out=build_atlas(root,{'test':True})
    assert out['unresolved']==0
    assert (root/'atlas'/'handoff'/'LATEST_STATE.zip').exists()
    assert (root/'atlas'/'STATE_MANIFEST.json').exists()
