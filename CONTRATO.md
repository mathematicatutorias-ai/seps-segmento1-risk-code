# CONTRATO · SEPS Segmento 1 Risk · 010

## Persistencia

`data/parquet/eeff/year=YYYY/month=MM/eeff.parquet` es la **única fuente local canónica** de EEFF.
DuckDB es efímero y se reconstruye desde Parquet en cada ejecución. No se mantiene una base DuckDB monolítica.

## Incrementalidad

- Una publicación con SHA idéntico se omite.
- Una publicación modificada se vuelve a parsear.
- Cada mes se compara mediante fingerprint de `(cutoff_date,ruc,account,record_sha256)`.
- Una partición idéntica no se reescribe.
- Una partición nueva/corregida reemplaza atómicamente solo ese mes.
- Los archivos fuente descargados y extraídos se eliminan al terminar.

## Migración legacy

La SQLite <=008 solo se elimina después de:
1. copiarla a almacenamiento local de Colab;
2. migrar el 100% de `fact_eeff` a Parquet;
3. verificar igualdad exacta de filas y claves primarias con DuckDB.

Si la verificación falla, la SQLite no se elimina.

## Dashboard

Después de cada fuente confirmada se reconstruyen features/señales sobre todos los Parquet disponibles y se actualizan `githubpage/data/live_bundle.js` e `index.html`.

## Atlas

Atlas registra código, configuración, lineage, manifiestos y estado; nunca incluye Parquet, SQLite legacy ni descargas SEPS.


## Update 011 · Contrato de features y publicación
- Una feature derivada puede depender de otra feature declarada anteriormente en `config/features.yaml`; el motor DEBE incorporar cada resultado al entorno antes de evaluar la siguiente.
- Ningún error de fórmula puede omitirse silenciosamente: el pipeline debe detenerse con `FeatureEvaluationError` y diagnóstico explícito.
- El dashboard público debe mostrar un aviso visible de propósito académico/informativo e independencia, además de la fuente y limitaciones.
- El aviso de propósito no sustituye la obligación de mantener cálculos, fuentes y metodología verificables.

## Contrato UX 013
- `githubpage/` es estático: sin polling, autoreload ni botón de actualización.
- El sidebar debe ser colapsable y usar iconografía local/SVG.
- El panel de riesgo siempre usa escala 0–100 con bandas configurables.
- Sin calibración: se denomina **Índice de riesgo relativo** y debe explicitar que no es probabilidad de default.
- Con calibración: puede mostrarse **Probabilidad estimada de evento adverso** con horizonte e incertidumbre.
- Los paneles inferiores deben consumir datos reales derivados del bundle, nunca series sintéticas salvo `mode=demo`.
- El disclaimer académico/informativo y la elaboración independiente deben ser visibles.


## Contrato UX 014
- La página publicada es estática; no realiza polling ni autoreload.
- El velocímetro resume todas las variables de riesgo configuradas y debe funcionar para cualquier entidad con al menos un componente comparable; los pesos disponibles se renormalizan.
- El índice relativo 0–100 nunca se rotula como probabilidad. Solo un modelo calibrado puede mostrar probabilidad estimada de evento adverso.
- El enlace superior de alcance abre la metodología completa con MathJax dentro de la misma página.
- Cambiar el indicador principal actualiza simultáneamente datos, título, descripción y formato de eje.


## Update 015 · KPI temporales y publicación GitHub
Las tarjetas resumen comparan el último valor con el cierre del período anterior según la agregación seleccionada. La publicación del código usa `config/github.yaml`, excluye datos operativos y requiere el Secret `GITHUB_TOKEN` en Colab.
