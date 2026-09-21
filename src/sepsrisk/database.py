"""Compatibility shim for releases <=008.

Update 009 no longer persists an operational SQLite. Use
`sepsrisk.storage.analytics.open_analytics()` for DuckDB queries and
`sepsrisk.storage.parquet_store` for canonical storage.
"""
from .storage.analytics import open_analytics
from .storage.parquet_store import legacy_sqlite_path,migrate_legacy_sqlite,storage_summary

def connect(root=None):return open_analytics(root)
def init_db(root=None):
    migrate_legacy_sqlite(root)
    return open_analytics(root)
def db_path(root=None):return legacy_sqlite_path(root)
def persistent_db_path(root=None):return legacy_sqlite_path(root)
def runtime_db_path(root=None):return legacy_sqlite_path(root)
def checkpoint_db(con,root=None):return None
