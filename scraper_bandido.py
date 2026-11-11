import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from personalidad_bandido import redactar_alerta_oferta
from imagen_bandido import descargar_y_optimizar_imagen

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
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def generar_enlace_afiliado(url_original, tienda):
    if not url_original:
        return ""
    url_limpia = url_original.split('?')[0]
    tienda_lower = tienda.lower()
    
    if "mercado libre" in tienda_lower or "mercadolibre" in tienda_lower:
        TAG_ML = "TU_TAG_DE_AFILIADO_ML" 
        return f"{url_limpia}?matt_tool=12345678&matt_word={TAG_ML}"
    elif "amazon" in tienda_lower:
        TAG_AMZ = "TU_TAG_AMAZON_MX"
        return f"{url_limpia}?tag={TAG_AMZ}"
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

def guardar_en_d1(titulo, precio_original, precio_oferta, descuento_str, cupon, tienda, categoria, caracteristicas, score, metodos_pago, fecha_vencimiento, url_afiliado, url_imagen):
    id_unico = str(abs(hash(titulo + precio_oferta + tienda)))
    
    query = """
        INSERT OR REPLACE INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, nivel, metodos_pago, fecha_vencimiento, url_afiliado, url_imagen, enviado_whatsapp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
    """
    
    payload = {
        "sql": query,
        "params": [
            id_unico, titulo, precio_original, precio_oferta, descuento_str, 
            cupon, tienda, categoria, caracteristicas, score, metodos_pago, fecha_vencimiento, url_afiliado, url_imagen
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

def raspar_mercadolibre(url):
    try:
        res = requests.get(url, headers=HEADERS_WEB, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, 'html.parser')
        titulo_elem = soup.find('h1', class_='ui-pdp-title')
        if not titulo_elem:
            return None
        
        titulo = titulo_elem.text.strip()
        precio_fraccion = soup.find('span', class_='andes-money-amount__fraction')
        precio_oferta_num = float(precio_fraccion.text.replace(',', '')) if precio_fraccion else 0.0
        
        precio_orig_elem = soup.find('s', class_='andes-money-amount--previous')
        precio_orig_num = precio_oferta_num
        if precio_orig_elem:
            frac_orig = precio_orig_elem.find('span', class_='andes-money-amount__fraction')
            if frac_orig:
                precio_orig_num = float(frac_orig.text.replace(',', ''))

        img_elem = soup.find('img', class_='ui-pdp-image')
        url_imagen = img_elem.get('src') or img_elem.get('data-src') if img_elem else ""

        return {
            "titulo": titulo,
            "p_orig": f"${precio_orig_num:,.2f} MXN",
            "p_ofer": f"${precio_oferta_num:,.2f} MXN",
            "p_orig_num": precio_orig_num,
            "p_ofer_num": precio_oferta_num,
            "url_imagen": url_imagen,
            "tienda": "Mercado Libre México"
        }
    except Exception as e:
        print(f"⚠️ Error controlado raspando Mercado Libre ({url}): {e}")
        return None

def raspar_amazon(url):
    try:
        res = requests.get(url, headers=HEADERS_WEB, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, 'html.parser')
        titulo_elem = soup.find('span', id='productTitle')
        if not titulo_elem:
            return None
        
        titulo = titulo_elem.text.strip()
        precio_whole = soup.find('span', class_='a-price-whole')
        precio_fraction = soup.find('span', class_='a-price-fraction')
        precio_oferta_num = 0.0
        if precio_whole:
            val_str = precio_whole.text.replace(',', '').replace('.', '').strip()
            frac_str = precio_fraction.text.strip() if precio_fraction else "00"
            precio_oferta_num = float(f"{val_str}.{frac_str}")

        precio_orig_elem = soup.find('span', class_='a-text-price')
        precio_orig_num = precio_oferta_num
        if precio_orig_elem:
            span_price = precio_orig_elem.find('span', class_='a-offscreen')
            if span_price:
                clean_orig = span_price.text.replace('$', '').replace(',', '').replace('MXN', '').strip()
                precio_orig_num = float(clean_orig)

        img_elem = soup.find('img', id='landingImage')
        url_imagen = img_elem.get('src') if img_elem else ""

        return {
            "titulo": titulo,
            "p_orig": f"${precio_orig_num:,.2f} MXN",
            "p_ofer": f"${precio_oferta_num:,.2f} MXN",
            "p_orig_num": precio_orig_num,
            "p_ofer_num": precio_oferta_num,
            "url_imagen": url_imagen,
            "tienda": "Amazon México"
        }
    except Exception as e:
        print(f"⚠️ Error controlado raspando Amazon ({url}): {e}")
        return None

def raspar_y_procesar_ofertas():
    print("🔍 Iniciando barrido inteligente y seguro de ofertas...")
    limpiar_ofertas_expiradas()

    urls_objetivo = [
        {
            "url": "https://www.amazon.com.mx/dp/B07XJ8C8F5", 
            "tienda": "Amazon México",
            "categoria": "Tecnología",
            "cupon": "BANDIDOPRUEBA",
            "metodos_pago": "Meses sin intereses con tarjetas participantes",
            "es_historico_real": True
        }
    ]

    for objetivo in urls_objetivo:
        url = objetivo["url"]
        datos_item = None

        try:
            if "mercadolibre" in url.lower():
                datos_item = raspar_mercadolibre(url)
            elif "amazon" in url.lower():
                datos_item = raspar_amazon(url)
        except Exception as e:
            print(f"❌ Fallo crítico procesando URL {url}: {e}")
            continue
        
        if not datos_item or datos_item["p_ofer_num"] <= 0:
            print(f"⏭️ Omitiendo URL inválida o sin stock disponible: {url}")
            continue

        tiene_cupon = bool(objetivo["cupon"] and objetivo["cupon"].strip() != "" and "SIN CUPÓN" not in objetivo["cupon"].upper())
        desc_val, score = calcular_scoring_y_niveles(datos_item["p_orig_num"], datos_item["p_ofer_num"], tiene_cupon, objetivo["es_historico_real"])
        
        if score == 5:
            print(f"🚫 [DESCARTADA - HUMO] {datos_item['titulo']} no pasa el filtro antihumo.")
            continue

        descuento_str = f"{desc_val}%"
        url_final = generar_enlace_afiliado(url, datos_item["tienda"])
        vencimiento = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")

        guardar_en_d1(
            titulo=datos_item["titulo"],
            precio_original=datos_item["p_orig"],
            precio_oferta=datos_item["p_ofer"],
            descuento_str=descuento_str,
            cupon=objetivo["cupon"] if tiene_cupon else "Sin cupón",
            tienda=datos_item["tienda"],
            categoria=objetivo["categoria"],
            caracteristicas="Extraído en vivo por el motor autónomo de Bandido",
            score=score,
            metodos_pago=objetivo["metodos_pago"],
            fecha_vencimiento=vencimiento,
            url_afiliado=url_final,
            url_imagen=datos_item["url_imagen"]
        )

        item_para_redes = {
            "titulo": datos_item["titulo"],
            "precio_original": datos_item["p_orig"],
            "precio_oferta": datos_item["p_ofer"],
            "descuento": descuento_str,
            "cupon": objetivo["cupon"],
            "tienda": datos_item["tienda"],
            "metodos_pago": objetivo["metodos_pago"],
            "url_afiliado": url_final,
            "nivel": score
        }
        
        mensaje_coqueto = redactar_alerta_oferta(item_para_redes)
        print("\n--- MENSAJE GENERADO PARA REDES ---")
        print(mensaje_coqueto)
        print("----------------------------------\n")

if __name__ == "__main__":
    print("🚀 [WAH] Arrancando núcleo autónomo en producción - Bandido Ofertas...")
    raspar_y_procesar_ofertas()
    print("🏁 Ciclo autónomo completado sin interrupciones.")
