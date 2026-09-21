from pathlib import Path
import pytest

def test_empty_dashboard_exports_index_files():
    pytest.importorskip('duckdb');pytest.importorskip('pyarrow')
    from sepsrisk.storage.analytics import open_analytics
    from sepsrisk.reporting.export_dashboard import export_dashboard
    root=Path(__file__).resolve().parents[1];con=open_analytics(root)
    meta=export_dashboard(con,root);con.close()
    assert meta['mode']=='empty'
    assert (root/'githubpage/index.html').exists()
    assert (root/'githubpage/data/live_bundle.js').exists()
