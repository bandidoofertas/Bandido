import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from personalidad_bandido import redactar_alerta_oferta

try:
    from credenciales import ACCOUNT_ID, DATABASE_ID, API_TOKEN
except ImportError:
    ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID")
    DATABASE_ID = os.getenv("CF_DATABASE_ID")
    API_TOKEN = os.getenv("CF_API_TOKEN")

URL_D1 = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"

HEADERS_CF = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-MX,es;q=0.9"
}

def generar_enlace_afiliado(url_original, tienda):
    if not url_original:
        return ""
    url_limpia = url_original.split('?')[0]
    tienda_lower = tienda.lower()
    
    if "mercado libre" in tienda_lower or "mercadolibre" in tienda_lower:
        TAG_ML = "TU_TAG_DE_AFILIADO_ML" 
        return f"{url_limpia}?matt_tool=12345678&matt_word={TAG_ML}"
    elif "aliexpress" in tienda_lower:
        TAG_ALI = "TU_ID_ALIEXPRESS"
        return f"https://s.click.aliexpress.com/e/_{TAG_ALI}?bz=300x250&dp={url_limpia}"
    return url_original

def calcular_scoring_y_niveles(precio_original_num, precio_oferta_num, tiene_cupon, es_historico_real):
    if precio_original_num <= 0:
        return 0.0, 5

    descuento_real = round(((precio_original_num - precio_oferta_num) / precio_original_num) * 100, 2)

    if not es_historico_real and descuento_real < 15:
        return descuento_real, 5

    if (descuento_real >= 40 or (descuento_real >= 25 and tiene_cupon)) and es_historico_real:
        score = 1  
    elif descuento_real >= 25 or (descuento_real >= 15 and tiene_cupon):
        score = 2  
    elif descuento_real >= 15:
        score = 3  
    elif descuento_real >= 5:
        score = 4  
    else:
        score = 5  

    return descuento_real, score

def guardar_en_d1(titulo, precio_original, precio_oferta, descuento_str, cupon, tienda, categoria, caracteristicas, score, metodos_pago, fecha_vencimiento, url_afiliado):
    id_unico = str(abs(hash(titulo + precio_oferta + tienda)))
    
    query = """
        INSERT OR REPLACE INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, nivel, metodos_pago, fecha_vencimiento, url_afiliado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    
    payload = {
        "sql": query,
        "params": [
            id_unico, titulo, precio_original, precio_oferta, descuento_str, 
            cupon, tienda, categoria, caracteristicas, score, metodos_pago, fecha_vencimiento, url_afiliado
        ]
    }

    try:
        response = requests.post(URL_D1, headers=HEADERS_CF, json=payload)
        resultado = response.json()
        if resultado.get("success"):
            print(f"🦝 [CAZADO Y GUARDADO] -> {titulo} [Nivel {score}] [{tienda}]")
        else:
            print(f"❌ Error al guardar en D1: {resultado}")
    except Exception as e:
        print(f"❌ Excepción de red con Cloudflare: {e}")

def limpiar_ofertas_expiradas():
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = "DELETE FROM ofertas WHERE fecha_vencimiento IS NOT NULL AND fecha_vencimiento < ?;"
    payload = {"sql": query, "params": [fecha_actual]}
    try:
        requests.post(URL_D1, headers=HEADERS_CF, json=payload)
        print("🧹 [LIMPIEZA] Ofertas expiradas eliminadas de D1 con éxito.")
    except Exception as e:
        print(f"⚠️ Error limpiando ofertas expiradas: {e}")

def raspar_y_procesar_ofertas():
    print("🔍 Iniciando barrido inteligente de ofertas...")
    limpiar_ofertas_expiradas()

    lote_ofertas = [
        {
            "titulo": "Laptop ASUS TUF Gaming A15",
            "p_orig": ",999 MXN", "p_ofer": ",499 MXN",
            "p_orig_num": 24999.0, "p_ofer_num": 17499.0,
            "cupon": "BUENFINBANDIDO", "tienda": "Amazon México",
            "categoria": "Computadoras", "caracteristicas": "AMD Ryzen 7 • RTX 4050 • 16GB RAM",
            "es_historico_real": True,
            "metodos_pago": "10% extra pagando con Tarjeta de Débito BBVA",
            "vencimiento": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "url": "https://www.amazon.com.mx/dp/B00EXAMPLE1"
        }
    ]

    for item in lote_ofertas:
        tiene_cupon = bool(item["cupon"] and item["cupon"].strip() != "" and "SIN CUPÓN" not in item["cupon"].upper())
        desc_val, score = calcular_scoring_y_niveles(item["p_orig_num"], item["p_ofer_num"], tiene_cupon, item["es_historico_real"])
        
        if score == 5:
            print(f"🚫 [DESCARTADA - HUMO] {item['titulo']} no pasa el filtro.")
            continue

        descuento_str = f"{desc_val}%"
        url_final = generar_enlace_afiliado(item["url"], item["tienda"])
        
        # Guardar en base de datos D1
        guardar_en_d1(
            titulo=item["titulo"],
            precio_original=item["p_orig"],
            precio_oferta=item["p_ofer"],
            descuento_str=descuento_str,
            cupon=item["cupon"] if tiene_cupon else "Sin cupón",
            tienda=item["tienda"],
            categoria=item["categoria"],
            caracteristicas=item["caracteristicas"],
            score=score,
            metodos_pago=item["metodos_pago"],
            fecha_vencimiento=item["vencimiento"],
            url_afiliado=url_final
        )

        # Generar texto con la personalidad del mapache para difusión
        item_para_redes = {
            "titulo": item["titulo"],
            "precio_original": item["p_orig"],
            "precio_oferta": item["p_ofer"],
            "descuento": descuento_str,
            "cupon": item["cupon"],
            "tienda": item["tienda"],
            "metodos_pago": item["metodos_pago"],
            "url_afiliado": url_final,
            "nivel": score
        }
        
        mensaje_coqueto = redactar_alerta_oferta(item_para_redes)
        print("\n--- MENSAJE GENERADO PARA REDES ---")
        print(mensaje_coqueto)
        print("----------------------------------\n")

if __name__ == "__main__":
    print("🚀 [WAH] Arrancando núcleo autónomo de Bandido Ofertas...")
    raspar_y_procesar_ofertas()
    print("🏁 Ciclo autónomo finalizado con éxito.")
