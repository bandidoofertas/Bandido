import json
import requests
from cfg import BASE_DIR, WORKER_URL, WORKER_TOKEN

PROMOS_PATH = BASE_DIR / "promos.json"
CAMPANA = "BLACK FRIDAY"

# Datos extraídos de tus capturas:
# Imagen 1 = Mercado Libre | Imágenes 2 a 6 = Amazon México
AMZ_LISTA = [
    {"banco": "Amazon Access (Invex)", "code": "ACCESST526", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% de descuento para nuevos usuarios Amazon Access (o 20% en 2da compra con ACCESS2DA20)"},
    {"banco": "BBVA", "code": "BBVAPAVO", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% de descuento + Hasta 15 MSI pagando a meses sin intereses"},
    {"banco": "Banamex", "code": "BNMXT526", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% de descuento + Hasta 24 MSI pagando a meses sin intereses"},
    {"banco": "Santander", "code": "SANTT526", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% de descuento + Hasta 12 MSI pagando a meses sin intereses"},
    {"banco": "Banorte", "code": "BNRTT526", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% de descuento pagando en una sola exhibición"},
    {"banco": "HSBC", "code": "HSBCT526", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% de descuento + Hasta 12 MSI pagando a meses sin intereses"},
    {"banco": "Nu", "code": "", "pct": 0, "fijo": 0, "min": 0, "tope": 100000, "desc": "Hasta $100,000 de bonificación en pases morados pagando a MSI"},
    {"banco": "DiDi Card", "code": "", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% de bonificación pagando en una sola exhibición"},
    {"banco": "Invex", "code": "INVEXPAVO", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% de descuento + Hasta 12 MSI"},
    {"banco": "BanCoppel", "code": "BCOPPAVOC", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% de descuento con T. Crédito + Hasta 12 MSI (o Débito con código BCOPPAVOD)"},
    {"banco": "Afirme", "code": "AFIRMEPAVO", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% de descuento + Hasta 12 MSI"},
    {"banco": "Kueski Pay", "code": "KUESKI30", "pct": 30, "fijo": 0, "min": 0, "tope": 0, "desc": "30% de descuento nuevos usuarios + 2 quincenas sin intereses (o $200 desc. con KUESKIMANIA)"}
]

ML_LISTA = [
    {"banco": "Mercado Pago", "code": "", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% cupón en compras con T. de Crédito y Mercado Crédito"},
    {"banco": "BBVA", "code": "BBVABFY", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% cupón en compras a 6 y 9 meses con T. de Crédito"},
    {"banco": "Banamex", "code": "BNMXBFY", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% cupón en compras a 3 meses con T. de Crédito"},
    {"banco": "Santander", "code": "SANTBFY", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% cupón en compras a 3, 6, 9 y 12 meses con T. de Crédito"},
    {"banco": "HSBC", "code": "HSBCBFY", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% cupón a una exhibición o 3 meses con T. de Crédito"},
    {"banco": "Banorte", "code": "BNRTBFY", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% cupón a una exhibición con T. de Crédito o Débito"},
    {"banco": "American Express", "code": "AMEXBFY", "pct": 10, "fijo": 0, "min": 0, "tope": 0, "desc": "10% cupón a una exhibición o 3 meses con T. de Crédito"},
    {"banco": "DiDi Card", "code": "DIDIBFY", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% cupón a una exhibición con T. de Crédito"},
    {"banco": "Afirme", "code": "AFRMBFY", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% cupón en compras con T. de Crédito"},
    {"banco": "Mifel", "code": "MIFEBFY", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% cupón a 3, 6, 9 y 12 meses con T. de Crédito"},
    {"banco": "Falabella", "code": "", "pct": 15, "fijo": 0, "min": 0, "tope": 0, "desc": "15% cashback a meses o 10% de contado"},
    {"banco": "Nu", "code": "", "pct": 0, "fijo": 0, "min": 0, "tope": 100000, "desc": "Hasta $100,000 de bonificación a partir de 6 MSI con T. de Crédito"}
]

def ejecutar():
    promos_local = {"amazon": {}, "mercadolibre": {}}
    for item in AMZ_LISTA:
        promos_local["amazon"][item["banco"]] = [{
            "code": item["code"],
            "pct": item["pct"],
            "fijo": item["fijo"],
            "min": item["min"],
            "tope": item["tope"],
            "desc": item["desc"]
        }]
    for item in ML_LISTA:
        promos_local["mercadolibre"][item["banco"]] = [{
            "code": item["code"],
            "pct": item["pct"],
            "fijo": item["fijo"],
            "min": item["min"],
            "tope": item["tope"],
            "desc": item["desc"]
        }]

    PROMOS_PATH.write_text(json.dumps(promos_local, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 [LOCAL OK] promos.json actualizado ({len(AMZ_LISTA)} bancos en Amazon, {len(ML_LISTA)} bancos en ML).")

    payload_web = {
        "campana": CAMPANA,
        "tiendas": {
            "amazon": [{"banco": i["banco"], "code": i["code"], "desc": i["desc"]} for i in AMZ_LISTA],
            "mercadolibre": [{"banco": i["banco"], "code": i["code"], "desc": i["desc"]} for i in ML_LISTA]
        }
    }

    r = requests.post(
        f"{WORKER_URL.rstrip('/')}/api/promos/actualizar",
        json=payload_web,
        headers={"Content-Type": "application/json", "Authorization": WORKER_TOKEN},
        timeout=15
    )
    print(f"☁️ [WEB STATUS {r.status_code}]: {r.text}")

if __name__ == "__main__":
    ejecutar()