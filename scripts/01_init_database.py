from sepsrisk.storage.parquet_store import migrate_legacy_sqlite,storage_summary
print('Migración:',migrate_legacy_sqlite())
print('Storage:',storage_summary())
