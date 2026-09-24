"""
preview_dashboard.py
----------------------
Genera una vista previa (PNG) de cómo debería verse el dashboard de Power
BI, a partir de los datos ya en chaskimarket.db. Esto NO reemplaza el
.pbix real (que se arma en Power BI Desktop siguiendo
powerbi/INSTRUCCIONES_POWERBI.md), pero sirve como referencia visual y
para el README.
"""
import sqlite3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "chaskimarket.db"
OUT = BASE / "charts_preview"
OUT.mkdir(exist_ok=True)

BLUE = "#2a78d6"
RED = "#e34948"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e5e4e0"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": TEXT_PRIMARY,
    "axes.labelcolor": TEXT_SECONDARY, "xtick.color": TEXT_SECONDARY, "ytick.color": TEXT_SECONDARY,
    "font.size": 11, "axes.edgecolor": GRID,
})


def limpiar_ejes(ax, eje="y"):
    for s in ["top", "right", "left" if eje == "y" else "bottom"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis=eje, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)


conn = sqlite3.connect(DB_PATH)
fact = pd.read_sql("""
    SELECT v.fecha, v.tienda_id, v.producto_id, v.cantidad, v.monto,
           t.nombre_tienda, p.nombre_producto, c.nombre_categoria
    FROM ventas v
    JOIN tiendas t ON v.tienda_id = t.tienda_id
    JOIN productos p ON v.producto_id = p.producto_id
    JOIN categorias c ON p.categoria_id = c.categoria_id
""", conn)
conn.close()

fact["fecha"] = pd.to_datetime(fact["fecha"])

# ---------------------------------------------------------------------
# 1. Ventas diarias, últimos 30 días, resaltando anomalías
# ---------------------------------------------------------------------
ultimos = fact[fact["fecha"] >= fact["fecha"].max() - pd.Timedelta(days=29)]
por_dia = ultimos.groupby("fecha")["monto"].sum()
promedio = por_dia.mean()

fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(por_dia.index, por_dia.values, color=BLUE, linewidth=2, marker="o", markersize=4, zorder=3)
ax.axhline(promedio, color=TEXT_SECONDARY, linewidth=1, linestyle="--", zorder=2)
ax.annotate(f"Promedio: S/ {promedio:,.0f}", (por_dia.index[0], promedio), textcoords="offset points",
            xytext=(0, 6), fontsize=9, color=TEXT_SECONDARY)
# resaltar días con caída fuerte
for fecha, valor in por_dia.items():
    if valor < promedio * 0.5:
        ax.scatter([fecha], [valor], color=RED, s=70, zorder=4)
        ax.annotate("Anomalía", (fecha, valor), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=9, color=RED, fontweight="bold")
limpiar_ejes(ax)
ax.set_title("Ventas diarias — últimos 30 días (ChaskiMarket)", fontsize=13, fontweight="bold", loc="left")
ax.set_ylabel("Ventas (S/.)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.savefig(OUT / "01_ventas_diarias.png", dpi=150)
plt.close()

# ---------------------------------------------------------------------
# 2. Ventas por tienda (todo el histórico)
# ---------------------------------------------------------------------
por_tienda = fact.groupby("nombre_tienda")["monto"].sum().sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(7.5, 4.5))
bars = ax.bar(por_tienda.index, por_tienda.values, color=BLUE, width=0.6, zorder=3)
limpiar_ejes(ax)
ax.set_title("Ventas totales por tienda", fontsize=13, fontweight="bold", loc="left")
ax.set_ylabel("Ventas (S/.)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
for b in bars:
    ax.annotate(f"S/ {b.get_height():,.0f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                textcoords="offset points", xytext=(0, 4), ha="center", fontsize=9)
plt.xticks(rotation=15, ha="right")
plt.tight_layout()
plt.savefig(OUT / "02_ventas_por_tienda.png", dpi=150)
plt.close()

# ---------------------------------------------------------------------
# 3. Ventas por categoría
# ---------------------------------------------------------------------
por_cat = fact.groupby("nombre_categoria")["monto"].sum().sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(7.5, 4))
bars = ax.barh(por_cat.index, por_cat.values, color=BLUE, height=0.6, zorder=3)
limpiar_ejes(ax, eje="x")
ax.set_title("Ventas por categoría de producto", fontsize=13, fontweight="bold", loc="left")
ax.set_xlabel("Ventas (S/.)")
for b in bars:
    ax.annotate(f"S/ {b.get_width():,.0f}", (b.get_width(), b.get_y() + b.get_height() / 2),
                textcoords="offset points", xytext=(4, 0), va="center", fontsize=9)
plt.tight_layout()
plt.savefig(OUT / "03_ventas_por_categoria.png", dpi=150)
plt.close()

print(f"Ventas totales histórico: S/ {fact['monto'].sum():,.2f}")
print(f"Gráficos guardados en {OUT}/")
