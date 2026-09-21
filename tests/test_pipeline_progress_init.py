from sepsrisk.progress import PipelineProgress

def test_pipeline_progress_accepts_project_progress_cfg():
    cfg = {"enabled": True, "leave_completed": False, "show_download_bytes": True, "show_row_progress": True}
    ui = PipelineProgress(cfg=cfg, enabled=False)
    assert ui.cfg.leave_completed is False
    assert ui.enabled is False
