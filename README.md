# SEPS Segmento 1 Risk

Monitor reproducible de riesgo financiero para cooperativas del **Segmento 1** del sistema financiero popular y solidario de Ecuador, construido a partir de información pública de la **Superintendencia de Economía Popular y Solidaria (SEPS)**.

El proyecto descarga e integra los estados financieros mensuales publicados por la SEPS, construye indicadores comparables entre entidades, genera series temporales y señales de deterioro, y publica un **dashboard HTML estático** listo para GitHub Pages.

> **Propósito:** análisis académico e informativo.  
> No constituye una calificación oficial de riesgo, una afirmación de insolvencia o default, recomendación financiera ni asesoría de inversión.

---

## Inicio rápido

El flujo completo está pensado para ejecutarse desde **Google Colab**.

### 1. Abrir el notebook maestro

Abra:

```text
MASTER_SEPS.ipynb
```

en Google Colab.

### 2. Montar Google Drive

El notebook monta Drive y trabaja sobre:

```text
/content/drive/MyDrive/seps-segmento1-risk
```

Si el proyecto está en otra ubicación, ajuste `PROJECT_ROOT` en la celda de configuración inicial.

### 3. Ejecutar todo

Use:

```text
Entorno de ejecución → Ejecutar todo
```

El MASTER se encarga de:

1. descubrir publicaciones nuevas o modificadas de la SEPS;
2. descargar únicamente lo necesario;
3. filtrar el universo al Segmento 1;
4. convertir la información a Parquet mensual;
5. verificar cambios mediante SHA;
6. reconstruir indicadores y benchmarks;
7. generar señales e índice de riesgo relativo;
8. reconstruir el dashboard estático;
9. actualizar Atlas/Handoff;
10. limpiar archivos temporales.

### 4. Abrir el dashboard

El producto final queda en:

```text
githubpage/index.html
```

La carpeta `githubpage/` es autocontenida y puede publicarse como sitio estático.

---

# Cómo funciona

## 1. Fuente oficial

La fuente principal son los **estados financieros mensuales** publicados por la SEPS.

La ingestión conserva únicamente las entidades que pertenecen al:

```text
Segmento 1
```

en cada fecha de corte.

No se utiliza una lista fija de cooperativas actuales para reconstruir el pasado.

---

## 2. Descarga temporal

Los archivos publicados por la SEPS se utilizan únicamente como insumo temporal:

```text
SEPS
  ↓
descarga
  ↓
parseo
  ↓
validación
  ↓
Parquet
  ↓
eliminar ZIP / CSV / TXT temporal
```

Los archivos fuente no se conservan permanentemente.

Si se necesita reconstruir el proyecto desde cero, se vuelven a descargar desde la SEPS.

---

## 3. Almacenamiento canónico

La fuente local canónica es **Parquet particionado por año y mes**:

```text
data/parquet/eeff/
├── year=2018/
│   ├── month=01/eeff.parquet
│   ├── month=02/eeff.parquet
│   └── ...
├── ...
└── year=2026/
    ├── month=01/eeff.parquet
    └── ...
```

**DuckDB** se utiliza como motor analítico sobre esos Parquet.

No se mantiene una base DuckDB monolítica.

---

## 4. Actualización incremental

El pipeline utiliza dos niveles de control de cambios.

### SHA de publicación

Si una publicación de la SEPS no cambió:

```text
SHA igual → no reprocesar
```

### SHA de partición mensual

Si una publicación cambió, el proyecto compara cada mes:

```text
enero      igual → no tocar
febrero    igual → no tocar
...
agosto     corregido → reemplazar agosto
septiembre nuevo     → crear septiembre
```

Esto evita reconstruir toda la historia ante una corrección puntual.

---

# Indicadores principales

El dashboard construye indicadores directamente desde las cuentas contables publicadas por la SEPS.

Entre los principales:

### Morosidad

\[
\mathrm{Morosidad}
=
\frac{\mathrm{Cartera\ improductiva}}
{\mathrm{Cartera\ bruta}}
\]

La composición de cartera improductiva contempla el cambio del catálogo contable ocurrido desde mayo de 2021.

### Cobertura

\[
\mathrm{Cobertura}
=
\frac{|\mathrm{Provisiones}|}
{\mathrm{Cartera\ improductiva}}
\]

### Liquidez

\[
\mathrm{Liquidez}
=
\frac{\mathrm{Fondos\ disponibles}}
{\mathrm{Depósitos\ de\ corto\ plazo}}
\]

### Capitalización

\[
\mathrm{Patrimonio/Activos}
=
\frac{\mathrm{Patrimonio}}
{\mathrm{Activos}}
\]

### Crecimiento de depósitos

Variaciones de depósitos a 3 y 12 meses.

### Rentabilidad

Se utiliza un proxy contable de ROA:

\[
\mathrm{ROA}
=
\frac{\mathrm{Ingresos}-\mathrm{Gastos}}
{\mathrm{Activos}}
\]

Las fórmulas operativas y cuentas utilizadas se encuentran en:

```text
config/features.yaml
```

---

# Índice de riesgo relativo

Mientras no exista una muestra histórica suficiente de eventos adversos para calibrar un modelo supervisado, el dashboard muestra un:

```text
Índice de riesgo relativo · 0–100
```

El índice compara cada entidad contra el **Segmento 1 contemporáneo**.

Actualmente integra:

- morosidad;
- cobertura;
- liquidez;
- crecimiento de depósitos;
- patrimonio / activos;
- rentabilidad.

Los pesos se definen en:

```text
config/project.yaml
```

y pueden modificarse sin tocar código.

Las bandas visuales son:

```text
0–33    Bajo
34–66   Medio
67–100  Alto
```

El índice **no debe interpretarse como una probabilidad de default**.

Si en el futuro existe una muestra suficiente de eventos históricos, el proyecto está preparado para incorporar modelos de riesgo a horizontes de:

```text
6 meses
12 meses
18 meses
```

---

# Dashboard

El dashboard es una página **100 % estática**.

No requiere:

- servidor;
- Streamlit;
- Dash;
- API;
- base de datos en producción.

El MASTER genera todo lo necesario dentro de:

```text
githubpage/
```

La interfaz incluye:

- selector de cooperativa;
- selector de período;
- agregación mensual, trimestral, semestral y anual;
- líneas y velas OHLC;
- KPIs con variación respecto al período anterior;
- morosidad vs Segmento 1;
- depósitos;
- liquidez;
- solvencia;
- rentabilidad;
- índice de riesgo relativo;
- señales del último corte;
- contribución de variables;
- radar frente al Segmento 1;
- distribución de entidades;
- evolución histórica del riesgo;
- metodología y limitaciones con MathJax.

---

# Estructura del proyecto

```text
seps-segmento1-risk/
│
├── MASTER_SEPS.ipynb          # orquestador principal en Colab
├── README.md
├── CHANGELOG.md
├── CONTRATO.md
├── pyproject.toml
│
├── config/                    # configuración humana en YAML
│   ├── project.yaml
│   ├── sources.yaml
│   ├── features.yaml
│   └── github.yaml
│
├── src/sepsrisk/              # lógica reusable
│   ├── ingestion/
│   ├── features/
│   ├── qa/
│   ├── reporting/
│   ├── publication/
│   └── ...
│
├── scripts/                   # operaciones ejecutables
├── tests/                     # pruebas automatizadas
├── contracts/                 # contratos técnicos específicos
├── sql/                       # esquemas/consultas auxiliares
│
├── notebooks/
│   └── jobs/                  # diagnósticos e intervenciones puntuales
│
├── data/
│   ├── parquet/               # datos canónicos; no se publican en Git
│   ├── state/                 # manifiestos incrementales
│   └── temp/                  # temporales
│
├── atlas/                     # grafo técnico, lineage y handoff
│
└── githubpage/                # dashboard estático publicable
    ├── index.html
    ├── assets/
    └── data/
```

---

# Configuración

El proyecto evita hardcodear reglas operativas dentro del código.

La configuración principal vive en YAML.

## `config/project.yaml`

Define:

- universo analizado;
- entidad inicial del dashboard;
- bandas y pesos del índice;
- almacenamiento;
- inferencia;
- progreso;
- migración;
- Atlas;
- publicación.

## `config/sources.yaml`

Define:

- fuentes SEPS;
- páginas de descubrimiento;
- patrones de nombres;
- extensiones aceptadas;
- equivalencias de columnas.

## `config/features.yaml`

Define:

- cuentas contables;
- componentes financieros;
- fórmulas de indicadores;
- cambios metodológicos por fecha.

---

# Atlas y continuidad

El proyecto incluye **Atlas**, utilizado para mantener trazabilidad técnica y continuidad entre intervenciones.

Atlas registra:

- código;
- configuración;
- dependencias;
- lineage;
- contratos;
- tests;
- productos generados;
- estado del pipeline.

El handoff más reciente se genera en:

```text
atlas/handoff/LATEST_STATE.zip
```

Los datos Parquet no forman parte de Atlas.

---

# Jobs de diagnóstico

Las investigaciones puntuales se mantienen separadas del pipeline principal:

```text
notebooks/jobs/
```

Por ejemplo:

```text
002_inspeccion_cruda_base_y_morosidad.ipynb
```

Los jobs deben ser, por defecto, de diagnóstico y no modificar los datos canónicos salvo que indiquen explícitamente lo contrario.

---

# Publicación del código en GitHub

Repositorio del código:

```text
https://github.com/mathematicatutorias-ai/seps-segmento1-risk-code
```

Rama principal:

```text
main
```

El MASTER incluye una celda opcional para publicar el snapshot reproducible del proyecto.

La autenticación utiliza el Secret de Colab:

```text
GITHUB_TOKEN
```

El token **nunca** se almacena en el repositorio.

No se publican:

- Parquet;
- SQLite;
- DuckDB;
- descargas SEPS;
- archivos temporales;
- salidas pesadas de jobs;
- credenciales;
- handoffs comprimidos.

---

# Reproducibilidad

El repositorio contiene el código y la configuración necesarios para reconstruir el proyecto.

En términos conceptuales:

```text
clonar código
    ↓
abrir MASTER_SEPS.ipynb
    ↓
ejecutar pipeline
    ↓
descargar SEPS
    ↓
reconstruir Parquet
    ↓
recalcular indicadores
    ↓
regenerar dashboard
```

Los datos derivados no son necesarios para versionar el código.

---

# Control de calidad

El pipeline incluye verificaciones sobre:

- esquema;
- duplicados;
- continuidad temporal;
- claves contables;
- integridad de particiones;
- fórmulas de features;
- exportación del dashboard;
- Atlas.

Los errores de cálculo de una feature **no se omiten silenciosamente**: el pipeline debe detenerse e identificar la fórmula que falló.

---

# Fuente y alcance

**Fuente de datos:** Superintendencia de Economía Popular y Solidaria (SEPS), Portal Estadístico.

Este proyecto es una elaboración independiente sobre información pública.

El análisis debe interpretarse junto con:

- metodología;
- supuestos;
- calidad de la información publicada;
- cobertura temporal;
- disponibilidad de indicadores;
- limitaciones de un índice relativo no calibrado.

---

# Historial de cambios

El historial de releases y correcciones **no se mantiene en este README**.

Consulte:

```text
CHANGELOG.md
```

El README describe **qué es el proyecto, cómo funciona y cómo usarlo**; el CHANGELOG documenta **qué cambió entre versiones**.

---

## Estado del proyecto

- Python ≥ 3.10
- almacenamiento: Parquet + Zstandard
- motor analítico: DuckDB
- ejecución principal: Google Colab
- salida pública: HTML/JavaScript estático
- universo: cooperativas Segmento 1
- configuración: YAML
- actualización: incremental por SHA
