# Contrato · publicación web

`githubpage/` contiene únicamente el producto de consumo público: dashboard estático, assets y JSON derivados.

## Entidades

- El selector se construye desde `dim_entity` y, por tanto, refleja todas las entidades realmente disponibles en los Parquet canónicos para el universo configurado.
- La entidad inicial se resuelve desde `focus_entity` en `config/project.yaml`; no puede hardcodearse en el JavaScript ni en los exportadores.
- Segmento 1 es benchmark, no la entidad mostrada.

## Inferencia

El bloque de inferencia se muestra siempre.

- Si existe modelo calibrado: presenta riesgo para 6/12/18 meses y la mediana contemporánea del Segmento 1.
- Si no existe suficiente evidencia histórica: muestra explícitamente `Modelo predictivo aún no calibrado` y no presenta una probabilidad numérica.

## DEMO

Si todavía no existen datos reales, el dashboard puede renderizar datos sintéticos únicamente para probar la UX. Debe mostrar simultáneamente banner y watermark `DEMO · SIN DATOS REALES`. Nunca se publicará un DEMO sin esa marca.

## Publicación y autoría

`publication` en `config/project.yaml` controla fuente, autoría y disclaimer. El campo `author` puede quedar vacío. El sitio debe identificar los cálculos como elaboración independiente y no como producto oficial de la SEPS.

## Aviso académico e informativo
El dashboard debe mostrar de forma visible que se trata de una elaboración independiente, con propósito académico e informativo, construida sobre información pública de la SEPS. Debe aclarar que no constituye calificación oficial de riesgo, afirmación de insolvencia/default, recomendación financiera, asesoría de inversión ni invitación a retirar o colocar fondos. El aviso no sustituye la trazabilidad de fuentes, fórmulas, supuestos y limitaciones.
