"""
generar_datos.py
------------------
Genera los datos de ejemplo para el proyecto ChaskiMarket:

1. Tablas de dimensión (tiendas, categorias, productos) -> data/dimensiones/
2. Una base de datos histórica ya cargada y limpia (chaskimarket.db) con
   ventas de junio a inicios de septiembre 2026 -> data/chaskimarket.db
3. Diez archivos CSV "entrantes" (uno por día, del 8 al 17 de septiembre
   2026) en data/incoming/, simulando la exportación diaria de un POS.
   Incluye dos días problemáticos a propósito, para poder demostrar las
   alertas del pipeline:
     - 2026-09-13: alta tasa de errores de calidad de datos
     - 2026-09-16: caída fuerte de ventas (ej. corte de sistema en tiendas)
"""
import csv
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

random.seed(7)

BASE = Path(__file__).parent
DIM_DIR = BASE / "data" / "dimensiones"
INCOMING_DIR = BASE / "data" / "incoming"
DB_PATH = BASE / "data" / "chaskimarket.db"

DIM_DIR.mkdir(parents=True, exist_ok=True)
INCOMING_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# DIMENSIONES
# ---------------------------------------------------------------------
tiendas = [
    (1, "ChaskiMarket Breña", "Breña"),
    (2, "ChaskiMarket Jesús María", "Jesús María"),
    (3, "ChaskiMarket Independencia", "Independencia"),
    (4, "ChaskiMarket Chorrillos", "Chorrillos"),
]

categorias = [
    (1, "Abarrotes"),
    (2, "Bebidas"),
    (3, "Snacks"),
    (4, "Limpieza"),
    (5, "Cuidado personal"),
]

productos_por_categoria = {
    1: [("Arroz 1kg", 4.2), ("Azúcar 1kg", 4.8), ("Aceite 1L", 9.5), ("Fideos 500g", 3.2), ("Atún lata", 5.9)],
    2: [("Gaseosa 500ml", 3.5), ("Agua mineral 1L", 2.0), ("Jugo envasado 1L", 5.5), ("Cerveza lata", 6.0)],
    3: [("Papitas 150g", 4.5), ("Galletas paquete", 2.8), ("Chocolate barra", 3.0), ("Maní salado", 3.8)],
    4: [("Detergente 1kg", 8.9), ("Lejía 1L", 4.0), ("Esponja x3", 3.5), ("Papel higiénico x4", 7.5)],
    5: [("Shampoo 400ml", 12.5), ("Jabón de tocador", 2.5), ("Pasta dental", 6.0), ("Desodorante", 9.9)],
}

productos = []
pid = 1
for cat_id, items in productos_por_categoria.items():
    for nombre, precio in items:
        productos.append((pid, nombre, cat_id, precio))
        pid += 1
NUM_PRODUCTOS = pid - 1

with open(DIM_DIR / "tiendas.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["tienda_id", "nombre_tienda", "distrito"])
    w.writerows(tiendas)

with open(DIM_DIR / "categorias.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["categoria_id", "nombre_categoria"])
    w.writerows(categorias)

with open(DIM_DIR / "productos.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["producto_id", "nombre_producto", "categoria_id", "precio_unitario"])
    w.writerows(productos)

MEDIOS_PAGO = ["Efectivo", "Tarjeta", "Yape/Plin"]
TIENDA_IDS = [t[0] for t in tiendas]
PRODUCTO_IDS = list(range(1, NUM_PRODUCTOS + 1))


def _hora_aleatoria():
    return f"{random.randint(8, 21):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"


def generar_filas_dia(fecha, n_ventas, sucio=False, cantidad_dirty=0):
    """Genera filas de venta para un día. `sucio` agrega basura extra.

    Cada fila lleva una hora con resolución de segundos para que dos
    transacciones distintas casi nunca coincidan exactamente por azar
    (evita duplicados "falsos" que no representan un error real).
    """
    filas = []
    for _ in range(n_ventas):
        tienda_id = random.choice(TIENDA_IDS)
        producto_id = random.choice(PRODUCTO_IDS)
        cantidad = random.randint(1, 6)
        medio_pago = random.choice(MEDIOS_PAGO)
        filas.append([fecha.isoformat(), _hora_aleatoria(), tienda_id, producto_id, cantidad, medio_pago])

    if sucio:
        for _ in range(cantidad_dirty):
            tipo_error = random.choice(["tienda_invalida", "producto_invalido", "cantidad_invalida", "duplicado"])
            if tipo_error == "tienda_invalida":
                filas.append([fecha.isoformat(), _hora_aleatoria(), 999, random.choice(PRODUCTO_IDS), random.randint(1, 4), "Efectivo"])
            elif tipo_error == "producto_invalido":
                filas.append([fecha.isoformat(), _hora_aleatoria(), random.choice(TIENDA_IDS), 9999, random.randint(1, 4), "Tarjeta"])
            elif tipo_error == "cantidad_invalida":
                filas.append([fecha.isoformat(), _hora_aleatoria(), random.choice(TIENDA_IDS), random.choice(PRODUCTO_IDS),
                              random.choice([-2, 0, 300]), "Yape/Plin"])
            else:  # duplicado exacto: el sistema de punto de venta reenvía la misma transacción
                if filas:
                    filas.append(list(filas[random.randint(0, len(filas) - 1)]))
    return filas


# ---------------------------------------------------------------------
# HISTÓRICO YA CARGADO (junio 1 - septiembre 7, 2026) -> chaskimarket.db
# ---------------------------------------------------------------------
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.executescript("""
CREATE TABLE IF NOT EXISTS tiendas (tienda_id INTEGER PRIMARY KEY, nombre_tienda TEXT, distrito TEXT);
CREATE TABLE IF NOT EXISTS categorias (categoria_id INTEGER PRIMARY KEY, nombre_categoria TEXT);
CREATE TABLE IF NOT EXISTS productos (producto_id INTEGER PRIMARY KEY, nombre_producto TEXT, categoria_id INTEGER, precio_unitario REAL);
CREATE TABLE IF NOT EXISTS ventas (
    venta_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT, hora TEXT, tienda_id INTEGER, producto_id INTEGER, cantidad INTEGER,
    medio_pago TEXT, monto REAL, procesado_en TEXT
);
""")
cur.executemany("INSERT OR REPLACE INTO tiendas VALUES (?,?,?)", tiendas)
cur.executemany("INSERT OR REPLACE INTO categorias VALUES (?,?)", categorias)
cur.executemany("INSERT OR REPLACE INTO productos VALUES (?,?,?,?)", productos)

precio_por_producto = {p[0]: p[3] for p in productos}
start_hist = date(2026, 6, 1)
end_hist = date(2026, 9, 7)
dia = start_hist
while dia <= end_hist:
    n_ventas = random.randint(180, 260)
    filas = generar_filas_dia(dia, n_ventas, sucio=False)
    for fecha, hora, tienda_id, producto_id, cantidad, medio_pago in filas:
        monto = round(cantidad * precio_por_producto[producto_id], 2)
        cur.execute(
            "INSERT INTO ventas (fecha, hora, tienda_id, producto_id, cantidad, medio_pago, monto, procesado_en) VALUES (?,?,?,?,?,?,?,?)",
            (fecha, hora, tienda_id, producto_id, cantidad, medio_pago, monto, "carga_inicial"),
        )
    dia += timedelta(days=1)
conn.commit()
conn.close()
print(f"Histórico cargado en {DB_PATH} ({start_hist} a {end_hist})")

# ---------------------------------------------------------------------
# ARCHIVOS ENTRANTES (8 al 17 de septiembre 2026) -> data/incoming/
# ---------------------------------------------------------------------
dias_incoming = [date(2026, 9, 8) + timedelta(days=i) for i in range(10)]

for dia in dias_incoming:
    if dia == date(2026, 9, 13):
        # Día con problema de calidad de datos: ~20% de filas basura
        n_ventas = 220
        filas = generar_filas_dia(dia, n_ventas, sucio=True, cantidad_dirty=int(n_ventas * 0.25))
    elif dia == date(2026, 9, 16):
        # Día con caída fuerte de ventas (ej. corte de sistema en tiendas)
        filas = generar_filas_dia(dia, 60, sucio=True, cantidad_dirty=5)
    else:
        n_ventas = random.randint(180, 260)
        filas = generar_filas_dia(dia, n_ventas, sucio=True, cantidad_dirty=int(n_ventas * 0.03))

    fname = INCOMING_DIR / f"ventas_{dia.isoformat()}.csv"
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "hora", "tienda_id", "producto_id", "cantidad", "medio_pago"])
        w.writerows(filas)
    print(f"Generado {fname.name} ({len(filas)} filas)")

print("\nListo. El histórico ya está en la base de datos; los 10 archivos de")
print("data/incoming/ simulan los próximos 10 días que el pipeline procesará uno por uno.")
