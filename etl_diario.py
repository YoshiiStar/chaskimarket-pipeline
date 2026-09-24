"""
etl_diario.py
--------------
Script que corre solo todos los días (vía el Programador de tareas de
Windows) y, al terminar, le avisa a n8n mandándole el resumen por HTTP
a un nodo "Webhook" (en vez de que n8n "entre" a ejecutar el script:
aquí es el script el que "avisa" cuando termina — arquitectura tipo
"push" en vez de "pull").

Qué hace:
  1. Busca el archivo más antiguo sin procesar en data/incoming/.
  2. Lo limpia: valida tienda_id/producto_id contra las dimensiones,
     descarta cantidades imposibles, elimina filas duplicadas.
  3. Calcula el monto de cada línea (cantidad x precio_unitario).
  4. Inserta las filas válidas en la base de datos acumulativa
     (data/chaskimarket.db), que es a la que luego se conecta Power BI.
  5. Compara las ventas del día contra el promedio histórico y detecta
     dos tipos de anomalía:
       - "calidad_datos": muchas filas se descartaron por errores.
       - "caida_ventas": el monto total del día es mucho menor al
         promedio histórico (ej. corte de sistema, tienda cerrada).
  6. Mueve el archivo procesado a data/procesados/.
  7. Escribe un resumen en resumen/resumen_<fecha>.json Y se lo manda a
     n8n por HTTP POST (webhook), para que el flujo decida si mandar un
     correo de alerta o de resumen.

Uso:
    python etl_diario.py
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).parent
INCOMING_DIR = BASE / "data" / "incoming"
PROCESADOS_DIR = BASE / "data" / "procesados"
RESUMEN_DIR = BASE / "resumen"
DB_PATH = BASE / "data" / "chaskimarket.db"

PROCESADOS_DIR.mkdir(parents=True, exist_ok=True)
RESUMEN_DIR.mkdir(parents=True, exist_ok=True)

UMBRAL_CALIDAD = 0.10   # si se descarta más del 10% de filas -> alerta de calidad
UMBRAL_CAIDA = 0.5      # si las ventas del día son < 50% del promedio -> alerta de caída

# URL del nodo Webhook de n8n. Ahora que el flujo está "Published"
# (activo) en n8n, usamos la "Production URL": el webhook escucha
# permanentemente, sin necesidad de abrir n8n ni darle a "Listen for
# test event" cada vez.
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/chaskimarket"


def enviar_a_n8n(resumen):
    """Manda el resumen a n8n por HTTP. Si n8n no está corriendo o la URL
    está mal, no debe tumbar el ETL: solo avisa por stderr y sigue."""
    try:
        r = requests.post(N8N_WEBHOOK_URL, json=resumen, timeout=5)
        print(f"[n8n] Webhook respondió con status {r.status_code}", file=sys.stderr)
    except requests.exceptions.RequestException as e:
        print(f"[n8n] No se pudo avisar a n8n ({N8N_WEBHOOK_URL}): {e}", file=sys.stderr)


def siguiente_archivo_pendiente():
    archivos = sorted(INCOMING_DIR.glob("ventas_*.csv"))
    return archivos[0] if archivos else None


def cargar_dimensiones(conn):
    tiendas = pd.read_sql("SELECT tienda_id FROM tiendas", conn)
    productos = pd.read_sql("SELECT producto_id, precio_unitario FROM productos", conn)
    return set(tiendas["tienda_id"]), productos.set_index("producto_id")["precio_unitario"].to_dict()


def promedio_historico(conn, dias=30):
    q = """
        SELECT fecha, SUM(monto) AS total_dia
        FROM ventas
        GROUP BY fecha
        ORDER BY fecha DESC
        LIMIT ?
    """
    df = pd.read_sql(q, conn, params=(dias,))
    if df.empty:
        return None
    return df["total_dia"].mean()


def main():
    archivo = siguiente_archivo_pendiente()
    if archivo is None:
        print(json.dumps({"estado": "sin_pendientes", "mensaje": "No hay archivos nuevos en data/incoming/"}))
        return

    fecha_archivo = archivo.stem.replace("ventas_", "")

    conn = sqlite3.connect(DB_PATH)
    tiendas_validas, precio_por_producto = cargar_dimensiones(conn)
    promedio = promedio_historico(conn)

    df = pd.read_csv(archivo)
    filas_leidas = len(df)

    # --- Limpieza ---
    df = df.drop_duplicates()
    tras_duplicados = len(df)

    df = df[df["tienda_id"].isin(tiendas_validas)]
    df = df[df["producto_id"].isin(precio_por_producto.keys())]
    df = df[(df["cantidad"] > 0) & (df["cantidad"] <= 100)]
    filas_validas = len(df)
    filas_descartadas = filas_leidas - filas_validas
    pct_descartado = filas_descartadas / filas_leidas if filas_leidas else 0

    df["precio_unitario"] = df["producto_id"].map(precio_por_producto)
    df["monto"] = (df["cantidad"] * df["precio_unitario"]).round(2)

    ahora = datetime.now().isoformat(timespec="seconds")
    df_insert = df[["fecha", "hora", "tienda_id", "producto_id", "cantidad", "medio_pago", "monto"]].copy()
    df_insert["procesado_en"] = ahora
    df_insert.to_sql("ventas", conn, if_exists="append", index=False)
    conn.commit()

    ventas_total_dia = float(df["monto"].sum())
    ticket_promedio = float(df["monto"].mean()) if filas_validas else 0.0

    # --- Detección de anomalías ---
    anomalias = []
    if pct_descartado > UMBRAL_CALIDAD:
        anomalias.append({
            "tipo": "calidad_datos",
            "detalle": f"Se descartó {pct_descartado:.0%} de las filas ({filas_descartadas} de {filas_leidas}), por encima del umbral de {UMBRAL_CALIDAD:.0%}.",
        })
    if promedio and ventas_total_dia < promedio * UMBRAL_CAIDA:
        anomalias.append({
            "tipo": "caida_ventas",
            "detalle": f"Ventas del día S/ {ventas_total_dia:,.2f} muy por debajo del promedio histórico S/ {promedio:,.2f} (< {UMBRAL_CAIDA:.0%}).",
        })

    conn.close()

    # --- Mover archivo procesado ---
    destino = PROCESADOS_DIR / archivo.name
    archivo.replace(destino)

    resumen = {
        "estado": "procesado",
        "fecha": fecha_archivo,
        "archivo": archivo.name,
        "filas_leidas": filas_leidas,
        "filas_duplicadas_eliminadas": filas_leidas - tras_duplicados,
        "filas_validas": filas_validas,
        "filas_descartadas": filas_descartadas,
        "pct_descartado": round(pct_descartado, 4),
        "ventas_total_dia": round(ventas_total_dia, 2),
        "ticket_promedio": round(ticket_promedio, 2),
        "promedio_historico_30d": round(promedio, 2) if promedio else None,
        "tiene_anomalia": len(anomalias) > 0,
        "anomalias": anomalias,
        "procesado_en": ahora,
    }

    with open(RESUMEN_DIR / f"resumen_{fecha_archivo}.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    # Log legible para humanos
    print(f"[{fecha_archivo}] {filas_validas}/{filas_leidas} filas válidas | "
          f"Ventas: S/ {ventas_total_dia:,.2f} | Anomalías: {len(anomalias)}", file=sys.stderr)

    # Avisar a n8n (webhook) con el resumen del día
    enviar_a_n8n(resumen)

    print(json.dumps(resumen, ensure_ascii=False))


if __name__ == "__main__":
    main()
