from pathlib import Path
from sepsrisk.pipeline import _resume_skip_completed
from sepsrisk.storage.state import save_ingestion_manifest

def test_resume_skips_completed_closed_year(tmp_path):
    root=tmp_path;(root/'config').mkdir();(root/'data/state').mkdir(parents=True)
    (root/'config/project.yaml').write_text('paths:\n  state: data/state\n',encoding='utf-8')
    save_ingestion_manifest({'sources':{'eeff_monthly|EEFF-MEN-BASE-2025':{'qa_status':'ok'}},'partitions':{}},root)
    cfg={'progress':{'resume_skip_completed_closed_periods':True,'recheck_current_period':True,'force_recheck_all_sources':False}}
    assert _resume_skip_completed('eeff_monthly',{'title':'EEFF-MEN-BASE-2025'},cfg,root) is True
