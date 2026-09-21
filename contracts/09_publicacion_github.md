# Contrato 09 · Publicación del código en GitHub

Repositorio de código: `https://github.com/mathematicatutorias-ai/seps-segmento1-risk-code`.
Rama principal: `main`. Visibilidad: pública.

## Regla de publicación
El repositorio contiene el proyecto reproducible completo (código, configuración, contratos, tests, notebooks, Atlas textual y `githubpage/`) pero **no** contiene las bases operativas ni archivos de datos derivados de gran volumen.

Se excluyen como mínimo: `data/`, `*.parquet`, `*.sqlite`, `*.duckdb`, `*.db`, ZIP de handoff/snapshots, caches y salidas de jobs.

## Autenticación
El token nunca se almacena en archivos del proyecto. Colab lee exclusivamente el secreto `GITHUB_TOKEN` desde Secrets. La publicación usa `GIT_ASKPASS` temporal y el remote permanece sin credenciales.

## Seguridad previa al push
Antes de copiar el snapshot al clon temporal se valida tamaño de archivos y patrones evidentes de tokens/llaves privadas. Si existe una alerta, el push se cancela.
