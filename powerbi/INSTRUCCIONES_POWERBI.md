# Cómo conectar Power BI al pipeline de ChaskiMarket

El pipeline (`etl_diario.py`, disparado por n8n) va acumulando datos limpios
en `data/chaskimarket.db` (SQLite). Power BI se conecta directamente a esa
base de datos, así que cada vez que el pipeline corre, el dashboard tiene
datos nuevos con solo darle "Actualizar".

## 1. Conectar Power BI Desktop a la base SQLite

Power BI no tiene un conector nativo para SQLite, así que se usa el driver
ODBC (es la forma más simple sin instalar nada de pago):

1. Instala el driver ODBC de SQLite: [http://www.ch-werner.de/sqliteodbc/](http://www.ch-werner.de/sqliteodbc/)
   (descarga `sqliteodbc.exe` para Windows de 64 bits).
2. En Windows, abre "Orígenes de datos ODBC (64 bits)" → pestaña "DSN de
   usuario" → "Agregar" → selecciona "SQLite3 ODBC Driver" → en
   "Database Name" selecciona el archivo `data/chaskimarket.db` → dale un
   nombre al DSN, por ejemplo `ChaskiMarketDB`.
3. En Power BI Desktop: **Obtener datos → ODBC** → selecciona el DSN
   `ChaskiMarketDB` → Power BI te mostrará las tablas `ventas`, `tiendas`,
   `categorias`, `productos` → selecciona todas y "Cargar".

## 2. Modelo de datos (relaciones)

Une las tablas así (Power BI las detecta automáticamente si los nombres de
columna coinciden, pero verifícalas en la vista de "Modelo"):

- `ventas.tienda_id` → `tiendas.tienda_id`
- `ventas.producto_id` → `productos.producto_id`
- `productos.categoria_id` → `categorias.categoria_id`

## 3. Medidas sugeridas (DAX)

```dax
Ventas Totales = SUM(ventas[monto])

Ticket Promedio = AVERAGE(ventas[monto])

Ventas Promedio Diario =
AVERAGEX(
    VALUES(ventas[fecha]),
    CALCULATE(SUM(ventas[monto]))
)

Variación vs Promedio =
DIVIDE(
    CALCULATE(SUM(ventas[monto]), FILTER(ventas, ventas[fecha] = MAX(ventas[fecha]))),
    [Ventas Promedio Diario]
) - 1
```

## 4. Visuales recomendados (mismo criterio que en Dashboard-Analytics)

- **Tarjetas (KPIs):** Ventas Totales, Ticket Promedio, Ventas del último día.
- **Gráfico de línea:** Ventas por fecha, con una línea de referencia en el
  promedio (para que se note visualmente cualquier caída, igual que en
  `charts_preview/01_ventas_diarias.png`).
- **Gráfico de barras:** Ventas por tienda.
- **Gráfico de barras horizontales:** Ventas por categoría.
- **Tabla o matriz:** Top 10 productos por monto vendido.
- Opcional: una tarjeta o indicador visual que muestre si el último archivo
  procesado tuvo una anomalía (puedes leer el campo `tiene_anomalia` del
  último `resumen/resumen_<fecha>.json` como una fuente de datos adicional).

## 5. Actualización automática (para producción real)

Power BI Desktop se actualiza manualmente (botón "Actualizar"). Para que se
actualice solo, en un entorno real se publicaría el reporte a **Power BI
Service** y se configuraría un **gateway de datos local** (Power BI
necesita esto para conectarse a una base de datos que vive en tu propia
máquina, no en la nube) con una actualización programada después de la hora
en que corre el pipeline de n8n (por ejemplo, 8:30am si el pipeline corre a
las 8:00am).

Esto requiere una cuenta de Power BI Pro/gateway, así que para el
portafolio basta con documentarlo (como aquí) y mostrar el `.pbix`
funcionando localmente con "Actualizar" manual — es exactamente lo que se
explica en una entrevista técnica.
