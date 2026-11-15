import json
import re
from cfg import BASE_DIR

PROMOS_PATH = BASE_DIR / "promos.json"

def cargar_promos() -> dict:
    try:
        with open(PROMOS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"amazon": {}, "mercadolibre": {}}

def limpiar_monto(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return 0.0
    limpio = re.sub(r"[^\d.]", "", str(val).replace(",", ""))
    try:
        return float(limpio) if limpio else 0.0
    except ValueError:
        return 0.0

def auditar_numeros(oferta: dict) -> dict:
    p_of = limpiar_monto(oferta.get("precio_oferta"))
    p_or = limpiar_monto(oferta.get("precio_original"))
    desc_str = str(oferta.get("descuento", ""))

    pct_txt = 0.0
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", desc_str)
    if m:
        pct_txt = float(m.group(1))

    if p_or <= p_of and p_of > 0 and 0 < pct_txt < 99:
        p_or = round(p_of / (1.0 - (pct_txt / 100.0)), 2)

    pct_real = round(((p_or - p_of) / p_or) * 100) if (p_or > p_of > 0) else round(pct_txt)

    anomalia = False
    motivo = ""
    if p_of <= 15.0:
        anomalia = True
        motivo = "Precio menor a $15 MXN (posible accesorio suelto o error)"
    elif pct_real > 85:
        anomalia = True
        motivo = f"Descuento inverosímil del {pct_real}% (posible precio inflado)"

    return {
        "precio_oferta": p_of,
        "precio_original": p_or,
        "pct_real": pct_real,
        "anomalia": anomalia,
        "motivo": motivo
    }

def detectar_banco(texto: str) -> str:
    t = texto.lower()
    alias = [
        ("mercado pago", "Mercado Pago"), ("mercadopago", "Mercado Pago"),
        ("citibanamex", "Banamex"), ("banamex", "Banamex"),
        ("bancomer", "BBVA"), ("bbva", "BBVA"),
        ("santander", "Santander"), ("banorte", "Banorte"),
        ("hsbc", "HSBC"), ("scotiabank", "Scotiabank"),
        ("invex", "Invex"), ("afirme", "Afirme"),
        ("mifel", "Mifel"), ("bancoppel", "BanCoppel"),
        ("openbank", "OpenBank")
    ]
    for palabra, nombre_oficial in alias:
        if re.search(rf"\b{re.escape(palabra)}\b", t):
            return nombre_oficial
    return ""

def calcular_tarjeta(oferta: dict, mensaje: str) -> dict:
    tienda = str(oferta.get("tienda", "Mercado Libre México"))
    es_amz = "amazon" in tienda.lower()
    clave_tienda = "amazon" if es_amz else "mercadolibre"
    nombre_tienda = "Amazon México" if es_amz else "Mercado Libre"

    nums = auditar_numeros(oferta)
    base = nums["precio_oferta"]
    banco = detectar_banco(mensaje)
    promos = cargar_promos().get(clave_tienda, {})

    if not banco:
        return {"tiene_banco": False, "precio_final": base, "codigo": "", "detalle": f"Oferta directa en {nombre_tienda}."}

    lista_ops = promos.get(banco)
    if not lista_ops:
        return {"tiene_banco": True, "precio_final": base, "codigo": "", "detalle": f"Sin cupón registrado para {banco} en {nombre_tienda}."}

    op = lista_ops[0]
    minimo = op.get("min", 0)
    if base > 0 and minimo > 0 and base < minimo:
        faltante = minimo - base
        return {
            "tiene_banco": True,
            "precio_final": base,
            "codigo": op.get("code", ""),
            "detalle": f"Cupón {op.get('code', '')} pide compra mínima de ${minimo:,.0f} MXN (te faltan ${faltante:,.0f} MXN)."
        }

    desc = 0.0
    if op.get("fijo", 0) > 0:
        desc = float(op["fijo"])
    elif op.get("pct", 0) > 0 and base > 0:
        desc = round(base * (op["pct"] / 100.0), 2)
        if op.get("tope", 0) > 0 and desc > op["tope"]:
            desc = float(op["tope"])

    final = round(max(0.0, base - desc), 2)
    cod_txt = f" usando el código {op['code']}" if op.get("code") else ""
    return {
        "tiene_banco": True,
        "precio_final": final,
        "codigo": op.get("code", ""),
        "detalle": f"Queda en ${final:,.0f} MXN{cod_txt} ({op.get('desc', '')})."
    }