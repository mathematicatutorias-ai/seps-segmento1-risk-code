# Modelo de datos · 009

La clave lógica EEFF es `(cutoff_date, ruc, account)`.

El almacén canónico es Parquet mensual particionado:

`data/parquet/eeff/year=YYYY/month=MM/eeff.parquet`

Cada fila conserva fecha, RUC, segmento, cuenta, descripción, entidad, saldo y `record_sha256`.

DuckDB crea views efímeras sobre todos los Parquet y deriva `dim_entity`, `dim_account`, features, peers, señales y riesgo durante cada ejecución. Las tablas derivadas no son la fuente de verdad.
