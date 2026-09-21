# Atlas · continuidad técnica del proyecto

Atlas no es solo un diagrama. Es el mecanismo de continuidad entre ejecuciones y entre sesiones de trabajo.

Cada ejecución del MASTER reconstruye:

- `CODE_ATLAS.json`: archivos, SHA-256 y símbolos Python detectados.
- `DEPENDENCY_GRAPH.json`: nodos y relaciones de código/artefactos, además de validación de referencias.
- `DATA_LINEAGE_GRAPH.json`: lineage desde SEPS hasta SQLite, features, inferencia y dashboard.
- `STATE_MANIFEST.json`: versión, update, estado de la SQLite, último corte y resumen de la última corrida.
- `RELEASE_MANIFEST.json`: fingerprint reproducible del proyecto.
- `atlas.sqlite`: representación consultable de nodos, aristas y archivos.
- `atlas.html`: vista rápida del estado y lineage.
- `latest_state.json`: resumen operacional de la última ejecución.
- `handoff/LATEST_STATE.zip`: paquete de continuidad que debe pasarse a la siguiente intervención.
- `handoff/snapshots/SEPS_STATE_*.zip`: snapshots recientes; se conserva solo el número configurado en YAML.

## Regla de continuidad

Antes de modificar el proyecto, el estado anterior se representa por `LATEST_STATE.zip`. Después del cambio se reconstruye Atlas, se exige `unresolved = 0` y se genera un nuevo `LATEST_STATE.zip`.

El handoff no contiene la SQLite operativa ni descargas SEPS: ambas son reconstruibles. Sí contiene código, configuración, contratos, tests, MASTER, SQL, shell del dashboard y manifiestos Atlas.
