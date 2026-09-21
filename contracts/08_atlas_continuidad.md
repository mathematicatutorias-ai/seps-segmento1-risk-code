# Contrato · Atlas y continuidad

Atlas debe permitir reconstruir el contexto técnico del proyecto sin depender de la memoria de una conversación.

## Productos obligatorios

- `CODE_ATLAS.json`
- `DEPENDENCY_GRAPH.json`
- `DATA_LINEAGE_GRAPH.json`
- `STATE_MANIFEST.json`
- `RELEASE_MANIFEST.json`
- `atlas.sqlite`
- `atlas.html`
- `latest_state.json`
- `handoff/LATEST_STATE.zip`

## Validación

Cada build de Atlas verifica que todas las aristas referencien nodos existentes y que los artefactos mínimos del proyecto existan. La condición de cierre es `unresolved = 0`.

## Handoff

`LATEST_STATE.zip` contiene código, configuración, contratos, SQL, tests, MASTER, documentación operativa, shell del dashboard y manifiestos Atlas. No contiene Parquet canónicos, SQLite legacy, archivos descargados de SEPS ni temporales.

Cada build conserva snapshots recientes bajo `atlas/handoff/snapshots/` según `atlas.keep_snapshots`.
