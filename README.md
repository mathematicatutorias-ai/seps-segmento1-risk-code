# SEPS Segmento 1 Risk · Update 010

Proyecto Colab para descargar EEFF mensuales de la SEPS, conservar únicamente Segmento 1, construir series y señales de deterioro y publicar un dashboard HTML estático.

> **011:** corrige el cálculo encadenado de features (incluida morosidad), hace visibles los errores de fórmula y añade el aviso académico/informativo al dashboard. No altera ni borra Parquet/estado existentes.

> **010:** corrección de compatibilidad del sistema de progreso en Colab. No altera ni borra Parquet/estado existentes.

## Arquitectura 009

- **Parquet particionado por `year/month` = almacenamiento canónico**.
- **DuckDB en memoria = motor analítico**; no se persiste un `.duckdb` grande.
- `data/state/*.json` guarda catálogo, SHA y manifiesto incremental.
- ZIP/TXT/CSV de SEPS son temporales y se eliminan.
- `githubpage/` contiene únicamente el dashboard publicable.
- Atlas/Handoff no contiene los datos Parquet.

## Incremental

1. SHA de publicación: si no cambió, no se procesa.
2. Si cambió, se parsea y calcula SHA lógico por mes.
3. Solo los meses nuevos o corregidos reemplazan su `eeff.parquet`.
4. Años cerrados ya confirmados se saltan antes de descargar.
5. Después de cada fuente confirmada se regenera el dashboard.

## Migración automática desde <=008

Si `data/operational/seps_segmento1.sqlite` o la copia activa en `/content` existe y aún no hay Parquet:

1. se elige la SQLite con más filas;
2. se copia a `/content`;
3. se migra allí a Parquet mensual;
4. DuckDB verifica filas y claves `(cutoff_date,ruc,account)`;
5. solo si la verificación es exacta, se elimina la SQLite legacy de Drive (configurable);
6. se copian los Parquet verificados a Drive.

Esto permite recuperar incluso una SQLite local más avanzada que no alcanzó a hacer checkpoint por cuota de Drive.

## Uso

Abra `MASTER_SEPS.ipynb` en Colab y ejecute **Run all**. El producto final está en `githubpage/index.html`.

## Dashboard 014
El producto público vive únicamente en `githubpage/` y es una página estática. No hace polling, no se autorecarga y no contiene controles de actualización. El build de Colab regenera sus datos cuando se ejecuta el MASTER.

La UX 014 incluye sidebar colapsable, KPIs, morosidad vs S1, velocímetro de riesgo 0–100, depósitos, liquidez, solvencia, resultados, señales, contribuyentes, radar, distribución de entidades, evolución del índice y metodología. Mientras no exista calibración supervisada suficiente, el velocímetro se rotula **Índice de riesgo relativo**, no probabilidad.


## Metodología 014
El enlace superior **Ver alcance, metodología y limitaciones** abre una metodología completa renderizada con MathJax. Incluye fórmulas de indicadores, percentiles contemporáneos, pesos, renormalización por faltantes, bandas del índice, distinción frente al modelo calibrado y limitaciones. El velocímetro tiene fallback cliente para que todas las entidades del bundle estático tengan índice cuando existan componentes suficientes.


## Publicación del código en GitHub · 015

El MASTER incluye una celda final opcional para publicar el snapshot reproducible del proyecto en `https://github.com/mathematicatutorias-ai/seps-segmento1-risk-code` (`main`). La autenticación se obtiene exclusivamente del Secret de Colab `GITHUB_TOKEN`; el token no se escribe en el proyecto ni en el remote de Git.

No se publican `data/`, Parquet, SQLite, DuckDB, ZIP de handoff/snapshots, caches ni salidas de jobs. El dashboard estático `githubpage/` sí forma parte del repositorio de código.
