
# 0.15.0 · Update 015

- Tarjetas KPI con flechas ↑/↓ respecto al período anterior según agregación seleccionada.
- Color semántico: verde = movimiento favorable; rojo = movimiento adverso; gris = estable/no comparable.
- Tooltip accesible con magnitud del cambio en puntos porcentuales o puntos de índice.
- Configuración `config/github.yaml` para `mathematicatutorias-ai/seps-segmento1-risk-code`.
- Publicación segura a GitHub desde la última celda del MASTER usando Secret `GITHUB_TOKEN` y `GIT_ASKPASS` temporal.
- `.gitignore` y preflight impiden publicar bases operativas, Parquet, SQLite/DuckDB, snapshots ZIP y secretos evidentes.
- Contrato de publicación GitHub y tests específicos del update.

# CHANGELOG

## 0.14.0 · Update 014
- Velocímetro 0–100 robusto para todas las entidades: fallback cliente exacto usando el bundle multi-entidad, percentiles contemporáneos y pesos YAML.
- Evolución histórica, contribuyentes y distribución pueden reconstruirse en navegador aun cuando un bundle previo no contenga `risk_index`.
- Selector principal sincroniza título, unidad y contenido del gráfico.
- Metodología completa en modal accesible desde “Ver alcance, metodología y limitaciones”, con MathJax y fórmulas explícitas.
- Separación explícita entre índice relativo y probabilidad calibrada de evento adverso.
- Página completamente estática: sin polling, autoreload ni botón de actualización.
- Robustecimiento del cálculo backend del índice frente a tipos y duplicados.

# Changelog

## 0.13.0 · Update 013
- Rediseño integral del dashboard estático siguiendo el mockup aprobado.
- Sidebar colapsable con iconos y navegación compacta.
- Se elimina polling/autoreload y cualquier botón de actualización: GitHub Page 100% estática.
- Velocímetro 0–100 con bandas verde/amarillo/rojo. Si el modelo no está calibrado muestra **Índice de riesgo relativo**; si existe modelo calibrado muestra **Probabilidad estimada**.
- Índice relativo calculado con percentiles contemporáneos del Segmento 1 y pesos configurables en `config/project.yaml`.
- Nuevos paneles: depósitos, liquidez, solvencia, resultados, señales, contribuyentes al riesgo, radar S1, distribución de entidades, evolución del índice y metodología.
- Mantiene selector multi-entidad, OHLC, benchmark S1 y disclaimer académico.
- Morosidad corregida en 0.11 se conserva.

## 0.10.0 · Update 010
- Corrige el arranque del pipeline en Colab: `PipelineProgress` recibe ahora el bloque `progress` mediante `cfg=` en lugar del argumento obsoleto `leave=`.
- Añade prueba de regresión para impedir que vuelva a romperse la inicialización del progreso.
- No modifica Parquet, estado incremental ni datos existentes; puede instalarse encima del 009 sin perder lo ya procesado.

## 0.9.0 · Update 009
- Sustituye SQLite monolítica por **Parquet mensual + DuckDB efímero**.
- Migración automática y verificada desde SQLite <=008.
- Incremental por SHA de fuente y SHA de partición mensual.
- Solo reescribe meses nuevos/corregidos.
- Dashboard sigue reconstruyéndose tras cada fuente confirmada.

## 0.8.0
- Dashboard local consume `live_bundle.js` directamente.

## 0.11.0 · Update 011
- Corrige el motor de features: cada feature derivada calculada se añade al entorno de evaluación y puede ser usada por features posteriores.
- `delinquency_ratio` vuelve a calcularse a partir de `loan_portfolio_gross`; el bug previo ocultaba un `NameError` y eliminaba morosidad silenciosamente.
- Las fórmulas de features ya no usan `except Exception: continue`; ahora un error lanza `FeatureEvaluationError` con nombre, fórmula y causa.
- `method_version` de features pasa a `features.yaml:0.11`.
- Añade aviso visible de análisis académico/informativo e independiente en el dashboard, además del disclaimer del footer.
- No incluye ni reemplaza Parquet, DuckDB persistente, SQLite legacy ni estado incremental del usuario.