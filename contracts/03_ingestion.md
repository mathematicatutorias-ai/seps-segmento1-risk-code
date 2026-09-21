# Ingestión · 009

Descarga temporal → SHA de publicación → parseo por chunks → filtro S1 → agrupación mensual → fingerprint mensual → escritura atómica solo de particiones cambiadas → manifiesto → limpieza.

## Resume

- Fuente anual cerrada con `qa_status=ok`: se salta antes de descargar.
- Periodo corriente: se vuelve a comprobar.
- SHA de publicación idéntico: se omite.
- SHA mensual idéntico: no se reescribe el Parquet.
- Mes nuevo/corregido: solo ese `year/month` se reemplaza.

## Observabilidad

El MASTER muestra etapa, porcentaje, tiempo y ETA. Descarga y parseo muestran progreso interno. Tras cada fuente confirmada se reconstruye el dashboard con todo lo disponible.

## Migración <=008

La SQLite legacy se migra en `/content`, se verifica por filas y PK, y solo después puede eliminarse de Drive. Si falla la verificación no se borra.
