import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from cerebro_ia import cerebro_autonomo_bandido
from publicador_facebook import publicar_oferta_facebook

try:
    from credenciales import ACCOUNT_ID, DATABASE_ID, API_TOKEN, GEMINI_API_KEY
except ImportError:
    ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID")
    DATABASE_ID = os.getenv("CF_DATABASE_ID")
    API_TOKEN = os.getenv("CF_API_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

URL_D1 = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"
HEADERS_CF = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def generar_enlace_afiliado(url_original, tienda):
    if not url_original: return ""
    url_limpia = url_original.split('?')[0]
    if "amazon" in tienda.lower():
        return f"{url_limpia}?tag=TU_TAG_AMAZON_MX"
    elif "mercadolibre" in tienda.lower():
        return f"{url_limpia}?matt_tool=12345678"
    return url_original

def guardar_en_d1(titulo, precio_original, precio_oferta, descuento, cupon, tienda, score, url_afiliado, url_imagen):
    id_unico = str(abs(hash(titulo + precio_oferta + tienda)))
    query = """
        INSERT OR REPLACE INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, nivel, url_afiliado, url_imagen, enviado_whatsapp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
    """
    payload = {"sql": query, "params": [id_unico, titulo, precio_original, precio_oferta, descuento, cupon, tienda, score, url_afiliado, url_imagen]}
    try:
        requests.post(URL_D1, headers=HEADERS_CF, json=payload)
        print(f"🦝 [DB] Oferta guardada en Cloudflare D1 -> {titulo} [Nivel {score}]")
    except Exception as e:
        print(f"❌ Error guardando en D1: {e}")

def raspar_amazon(url):
    try:
        res = requests.get(url, headers=HEADERS_WEB, timeout=10)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.text, 'html.parser')
        titulo = soup.find('span', id='productTitle')
        if not titulo: return None
        
        precio_whole = soup.find('span', class_='a-price-whole')
        precio_oferta = float(precio_whole.text.replace(',', '').replace('.', '').strip()) if precio_whole else 0.0
        
        img_elem = soup.find('img', id='landingImage')
        url_imagen = img_elem.get('src') if img_elem else ""

        return {
            "titulo": titulo.text.strip(),
            "p_orig": f"${precio_oferta * 1.3:,.2f} MXN", # Estimado base o extraído
            "p_ofer": f"${precio_oferta:,.2f} MXN",
            "p_ofer_num": precio_oferta,
            "tienda": "Amazon México",
            "url_imagen": url_imagen,
            "url_afiliado": generar_enlace_afiliado(url, "Amazon México")
        }
    except Exception as e:
        print(f"⚠️ Error raspando Amazon: {e}")
        return None

def ejecutar_ciclo_autonomo():
    print("🧠 [BANDIDO IA] Iniciando ciclo autónomo con Gemini 2.5 Flash...")
    
    # URL de prueba para el ciclo
    url_prueba = "https://www.amazon.com.mx/dp/B07XJ8C8F5"
    datos_brutos = raspar_amazon(url_prueba)
    
    if not datos_brutos:
        print("❌ No se pudo extraer información del producto.")
        return

    # Cerebro de IA toma la decisión completa
    analisis_ia = cerebro_autonomo_bandido(datos_brutos)
    
    if not analisis_ia or analisis_ia.get("descartar") or analisis_ia.get("score", 5) > 3:
        print(f"🚫 [HUMO DETECTADO] Gemini descartó la oferta. Razón: {analisis_ia.get('razonamiento_antihumo') if analisis_ia else 'Fallo de IA'}")
        return

    score = analisis_ia.get("score")
    print(f"✅ [GANA APROBADA] Nivel {score}. Razón: {analisis_ia.get('razonamiento_antihumo')}")

    # Guardar en D1
    guardar_en_d1(
        titulo=datos_brutos["titulo"],
        precio_original=datos_brutos["p_orig"],
        precio_oferta=datos_brutos["p_ofer"],
        descuento="Descuento IA",
        cupon="SIN CUPÓN",
        tienda=datos_brutos["tienda"],
        score=score,
        url_afiliado=datos_brutos["url_afiliado"],
        url_imagen=datos_brutos["url_imagen"]
    )

    # Publicar automáticamente en Facebook si es Nivel 1, 2 o 3
    item_para_redes = {
        "titulo": datos_brutos["titulo"],
        "precio_original": datos_brutos["p_orig"],
        "precio_oferta": datos_brutos["p_ofer"],
        "descuento": "Especial IA",
        "cupon": "SIN CUPÓN",
        "tienda": datos_brutos["tienda"],
        "url_afiliado": datos_brutos["url_afiliado"],
        "nivel": score
    }
    
    # Opcional: sobreescribir el mensaje con el texto generado por Gemini
    publicar_oferta_facebook(item_para_redes, ruta_imagen=None)

if __name__ == "__main__":
    ejecutar_ciclo_autonomo()
