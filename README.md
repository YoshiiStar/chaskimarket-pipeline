# ChaskiMarket — Pipeline de ventas automatizado

Armé este proyecto para practicar automatización de datos y BI de punta a punta, de cara a postular a prácticas de analista de datos. La idea era simular algo parecido a lo que pasa en una empresa de verdad: todos los días llega un archivo de ventas nuevo, como si viniera de un punto de venta, y en vez de abrirlo y revisarlo a mano, todo el flujo corre solo: valida la calidad de los datos, actualiza una base acumulativa y avisa por correo si algo salió mal.

ChaskiMarket es una cadena ficticia de 4 minimarkets en Lima que inventé para tener un caso de negocio con el que trabajar (tiendas, categorías, productos, medios de pago), pero el pipeline en sí no depende de ese negocio en particular: el patrón (llega un archivo, se limpia, se valida, se avisa) es el mismo que usaría para cualquier fuente que reciba datos periódicamente. Lo que más me interesaba practicar acá era justamente eso: que el proceso corra solo todos los días sin que nadie lo esté mirando.

## Cómo está armado el flujo

Todos los días cae un CSV nuevo en `data/incoming/`, simulando la exportación diaria del punto de venta. El Programador de tareas de Windows dispara `etl_diario.py`, que con pandas limpia el archivo: quita duplicados, descarta filas con tienda o producto que no existen en las dimensiones, y filtra cantidades fuera de rango. Con lo que queda, calcula el monto de cada línea y lo inserta en una base SQLite acumulativa (`data/chaskimarket.db`).

Ahí mismo compara las ventas del día contra el promedio de los últimos 30 días y arma un resumen en JSON con las métricas y, si corresponde, las anomalías detectadas (calidad de datos o caída de ventas). Ese resumen se manda por HTTP a un webhook de n8n corriendo en Docker, que según el contenido decide si toca mandar un correo de alerta o uno de resumen normal, y lo envía por Gmail.

Power BI, por su lado, está conectado directo a la base SQLite vía un driver ODBC, así que el dashboard se actualiza solo con darle "Actualizar" después de cada corrida, sin tener que exportar nada a mano.

```
CSV diario → ETL en Python (pandas + SQLite) → Programador de tareas de Windows
   → webhook a n8n (Docker) → alerta o resumen por Gmail
   → dashboard en Power BI (conectado vía ODBC)
```

## Estructura del proyecto

```
chaskimarket-pipeline/
├── generar_datos.py           # genera dimensiones, histórico e "incoming" de ejemplo
├── etl_diario.py               # el script que corre cada día
├── preview_dashboard.py        # genera gráficos de referencia (charts_preview/)
├── data/
│   ├── dimensiones/             # tiendas.csv, categorias.csv, productos.csv
│   ├── incoming/                # archivos de ventas pendientes de procesar
│   ├── procesados/              # archivos ya procesados
│   └── chaskimarket.db          # base acumulativa, a la que se conecta Power BI
├── resumen/                     # un JSON por cada día procesado
├── n8n/
│   ├── generar_workflow.py      # script para regenerar el flujo de n8n
│   └── chaskimarket_pipeline.json
├── powerbi/
│   └── INSTRUCCIONES_POWERBI.md
├── charts_preview/              # vista previa de cómo se ve el dashboard
└── requirements.txt
```

## Tecnologías

Python (pandas, sqlite3, requests) para el ETL, n8n corriendo en Docker como orquestador y para mandar los correos, Gmail vía OAuth2 para las notificaciones, Power BI Desktop con el driver ODBC de SQLite para el dashboard, y matplotlib solo para generar las vistas previas de los gráficos que están en este repo.

## Cómo correrlo en tu máquina

```bash
pip install -r requirements.txt

python generar_datos.py        # genera dimensiones, histórico e incoming/
python etl_diario.py           # procesa el archivo más antiguo pendiente
python preview_dashboard.py    # genera los gráficos de vista previa
```

Para el flujo completo con notificaciones, hace falta además:

1. Levantar n8n en Docker (`docker run -it --rm -p 5678:5678 n8nio/n8n`) e importar `n8n/chaskimarket_pipeline.json`.
2. Conectar tu cuenta de Gmail en los nodos de n8n (te pide autorizar por OAuth2 la primera vez).
3. Programar `etl_diario.py` en el Programador de tareas de Windows para que corra todos los días.
4. Conectar Power BI a `data/chaskimarket.db` siguiendo `powerbi/INSTRUCCIONES_POWERBI.md`.

## El bug que más trabajo me dio: rename() vs replace() en Windows

Cuando terminaba de procesar un archivo, el script tenía que moverlo de `data/incoming/` a `data/procesados/`. La primera versión usaba `os.rename()`, que en Linux simplemente sobrescribe el destino si ya existe, pero en Windows lanza `FileExistsError` cuando el archivo de destino ya está ahí. El problema es que ese error no tumbaba nada visible a simple vista: el archivo se quedaba en `incoming/`, y en la siguiente corrida el pipeline lo volvía a tomar como "pendiente" y lo insertaba de nuevo en la base.

Me di cuenta corriendo el pipeline dos veces seguidas sobre el mismo día para probar el manejo de errores, y viendo que las ventas totales de esa fecha me daban el doble de lo esperado en el resumen. Al principio pensé que era un problema en el cálculo del monto, hasta que revisé la tabla `ventas` directo y encontré las filas duplicadas. Cambié `os.rename()` por `Path.replace()`, que en Windows sí hace el reemplazo atómico aunque el destino ya exista, y el problema desapareció. Quedó como buen recordatorio de que hay funciones de la librería estándar que no se comportan igual entre sistemas operativos, y que conviene probarlas en el SO real donde va a correr el proceso, no asumir.

## Qué aprendí haciendo esto

La parte de limpieza de datos con pandas ya la tenía más o menos dominada por mis otros proyectos; lo nuevo acá fue todo lo relacionado con dejar algo corriendo desatendido: pensar en qué pasa si el proceso corre dos veces, cómo detectar anomalías sin que alguien esté mirando el dashboard a cada rato, y cómo armar un mecanismo de aviso (el resumen en JSON + el webhook a n8n) que decida solo si hace falta escalar algo por correo. También fue la primera vez que conecté Power BI a una fuente que se sigue actualizando sola en vez de a un archivo estático, lo cual cambia bastante cómo uno piensa el modelo de datos.

## Capturas

(agregar captura aquí) — dashboard de Power BI con las ventas actualizadas

(agregar captura aquí) — correo de alerta recibido en Gmail cuando el pipeline detecta una anomalía

## Autor

Wiener William Cataño Pérez — estudiante de los últimos ciclos de Ingeniería de Sistemas en la UTP, postulando a prácticas de analista de datos.
[LinkedIn](https://www.linkedin.com/in/wiener-william-cataño-perez-0896712b4/) · [GitHub](https://github.com/YoshiiStar)
