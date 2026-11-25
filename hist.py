import re
import requests
from cfg import get_db


def init_hist():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historial_precios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_normal TEXT,
                precio REAL,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hist_url ON historial_precios(url_normal)")


def registrar_precio(url_normal: str, precio: float):
    if not url_normal or precio <= 0:
        return
    init_hist()
    with get_db() as conn:
        conn.execute("INSERT INTO historial_precios (url_normal, precio) VALUES (?, ?)", (url_normal, precio))


def consultar_camel_amz(asin: str) -> dict:
    """Consulta rápida al historial público de Amazon México sin API key."""
    try:
        r = requests.get(
            f"https://mx.camelcamelcamel.com/product/{asin}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0"},
            timeout=7
        )
        if r.status_code != 200:
            return {}
        txt = r.text
        precios = [float(p.replace(",", "")) for p in re.findall(r"\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)", txt)]
        precios_validos = [p for p in precios if p > 20]
        if len(precios_validos) >= 2:
            return {"min_hist": min(precios_validos), "prom_hist": round(sum(precios_validos) / len(precios_validos), 2)}
    except Exception:
        pass
    return {}


def verificar_historial(url_normal: str, precio_actual: float, tienda: str) -> dict:
    init_hist()

    # Consultar precios previos ANTES de insertar el actual (solo ventana vigente de 12h)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT precio FROM historial_precios 
            WHERE url_normal = ? AND fecha >= datetime('now', '-12 hours')
            ORDER BY id DESC LIMIT 20
            """,
            (url_normal,)
        ).fetchall()

    precios_db = [r["precio"] for r in rows]
    es_humo = False
    nota = "Precio validado."

    # 1. Revisar memoria local vigente (si hubo cambios dentro de la misma ventana de 12h)
    if len(precios_db) >= 1:
        promedio_local = sum(precios_db) / len(precios_db)
        if precio_actual > promedio_local * 1.03:
            es_humo = True
            nota = f"Humo detectado: subió respecto a su precio previo registrado (${promedio_local:,.0f} MXN)."
        elif precio_actual < promedio_local * 0.95:
            nota = f"Bajada adicional verificada frente a su registro previo de ${promedio_local:,.0f} MXN."

    # 2. Revisar historial externo si es Amazon
    if not es_humo and "amazon" in tienda.lower():
        m = re.search(r"/dp/([A-Z0-9]{10})", url_normal)
        if m:
            camel = consultar_camel_amz(m.group(1))
            if camel.get("prom_hist"):
                prom = camel["prom_hist"]
                minimo = camel["min_hist"]
                if precio_actual > prom * 1.02:
                    es_humo = True
                    nota = f"Humo en Amazon: hoy cuesta ${precio_actual:,.0f}, pero su promedio histórico es ${prom:,.0f} MXN."
                elif precio_actual <= minimo * 1.05:
                    nota = f"¡Mínimo histórico real! Antes promediaba ${prom:,.0f} MXN."
                else:
                    nota = f"Descuento real debajo de su promedio histórico de ${prom:,.0f} MXN."

    # Registrar el precio actual solo después de evaluar
    registrar_precio(url_normal, precio_actual)
    return {"es_humo": es_humo, "nota": nota}