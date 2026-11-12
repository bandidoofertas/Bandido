import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from google import genai

# Cargar credenciales de producción locales o desde variables de entorno (GitHub Actions)
try:
    from credenciales import (
        ACCOUNT_ID, DATABASE_ID, API_TOKEN, GEMINI_API_KEY
    )
except ImportError:
    ACCOUNT_ID = os.getenv("ACCOUNT_ID")
    DATABASE_ID = os.getenv("DATABASE_ID")
    API_TOKEN = os.getenv("API_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# Inicializar cliente oficial de Gemini
client = genai.Client()

# Configuración de los endpoints oficiales de Cloudflare D1
URL_D1 = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"

HEADERS_D1 = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Cabeceras para simular un navegador real y evitar bloqueos anti-bot en tiendas
HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

def generar_enlace_afiliado(url_original, tienda):
    """Transforma la URL según la tienda o la devuelve directa de forma segura."""
    try:
        tienda_lower = tienda.lower()
        if any(k in tienda_lower for k in ["walmart", "bodega aurrera", "aurrera", "adidas"]):
            return url_original
        return url_original
    except Exception as e:
        print(f"⚠️ [Advertencia URL] No se pudo procesar el enlace para {tienda}: {e}")
        return url_original

def cerebro_ia_antihumo(datos_oferta_bruta):
    """
    Motor de razonamiento autónomo estricto de Bandido (Escala 1 a 8).
    - 1 a 3: Gangas TOP / Fuego 🔥
    - 4 a 5: Ofertas razonables / Estándar
    - 6 a 8: Basura / Falsas rebajas con precios artificialmente inflados (Se descartan)
    """
    system_instruction = (
        "Eres Bandido, un mapache coqueto, astuto, pícaro y experto analista "
        "en comercio electrónico en México. Tu misión es desenterrar gangas reales "
        "y cazar sin piedad el 'humo' corporativo y las falsas rebajas donde las tiendas "
        "inflan el precio base para engañar a los compradores."
    )

    prompt = f"""
    {system_instruction}
    Analiza esta oferta y responde estrictamente en formato JSON puro (sin bloques markdown ni texto adicional):
    
    - Título: {datos_oferta_bruta.get('titulo')}
    - Precio Original: {datos_oferta_bruta.get('precio_original')}
    - Precio de Oferta: {datos_oferta_bruta.get('precio_oferta')}
    - Tienda: {datos_oferta_bruta.get('tienda')}
    - URL: {datos_oferta_bruta.get('url')}
    
    Escala 1 a 8: 1-3 (Gangas TOP), 4-5 (Razonables), 6-8 (Basura/Falsas rebajas con precio inflado).
    
    Estructura JSON requerida:
    {{
      "score": int,
      "descartar": bool,
      "razonamiento_antihumo": "Explicación detallada del análisis de precio y detección de humo",
      "mensaje_redes": "Texto persuasivo con emojis de mapache (🦝) listo para difundir si se aprueba"
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        texto = response.text.strip()
        if texto.startswith("```json"):
            texto = texto[7:]
        if texto.endswith("```"):
            texto = texto[:-3]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"❌ [Error en Cerebro IA Gemini]: {e}")
        return None

def extraer_ofertas_mercadolibre():
    """Scraper real para Mercado Libre México (Sección de Ofertas)"""
    ofertas = []
    url_base = "https://www.mercadolibre.com.mx/ofertas"
    
    try:
        print("🔍 [SCRAPER] Conectando con Mercado Libre México...")
        response = requests.get(url_base, headers=HEADERS_WEB, timeout=12)
        if response.status_code != 200:
            print(f"⚠️ Mercado Libre respondió con código HTTP {response.status_code}")
            return ofertas
            
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.promotion-item')
        
        for item in items[:15]:  # Captura un lote razonable por ejecución
            try:
                titulo_el = item.select_one('.promotion-item__title')
                precio_oferta_el = item.select_one('.andes-money-amount__fraction')
                link_el = item.select_one('a.promotion-item__link-container') or item.select_one('a')
                
                if not titulo_el or not precio_oferta_el or not link_el:
                    continue
                    
                titulo = titulo_el.text.strip()
                p_oferta_str = f"${precio_oferta_el.text.strip()} MXN"
                
                # Intentar capturar precio tachado original si existe
                precio_orig_el = item.select_one('.andes-money-amount--previous .andes-money-amount__fraction')
                p_orig_str = f"${precio_orig_el.text.strip()} MXN" if precio_orig_el else p_oferta_str
                
                link_producto = link_el.get('href', '')
                
                ofertas.append({
                    "titulo": titulo,
                    "precio_original": p_orig_str,
                    "precio_oferta": p_oferta_str,
                    "tienda": "Mercado Libre",
                    "categoria": "General",
                    "caracteristicas": "Oferta relámpago extraída de Mercado Libre",
                    "url": link_producto
                })
            except Exception:
                continue
                
        print(f"✅ [SCRAPER M.L.] Se extrajeron {len(ofertas)} ofertas con éxito.")
    except Exception as e:
        print(f"❌ [Error Scraper Mercado Libre]: {e}")
        
    return ofertas

def extraer_ofertas_amazon():
    """Scraper real para Amazon México (Sección de Ofertas / Goldbox)"""
    ofertas = []
    url_base = "https://www.amazon.com.mx/gp/goldbox"
    
    try:
        print("🔍 [SCRAPER] Conectando con Amazon México...")
        response = requests.get(url_base, headers=HEADERS_WEB, timeout=12)
        if response.status_code != 200:
            print(f"⚠️ Amazon México respondió con código HTTP {response.status_code}")
            return ofertas
            
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.grid-row .a-section.a-spacing-none, .feed-shared-feed-item')
        
        for item in items[:15]:
            try:
                titulo_el = item.select_one('.a-size-base, .a-link-normal')
                precio_el = item.select_one('.a-price .a-offscreen')
                link_el = item.select_one('a.a-link-normal')
                
                if not titulo_el or not precio_el:
                    continue
                    
                titulo = titulo_el.text.strip()
                p_oferta_str = precio_el.text.strip()
                link_producto = f"https://www.amazon.com.mx{link_el.get('href')}" if link_el and link_el.get('href', '').startswith('/') else url_base
                
                ofertas.append({
                    "titulo": titulo,
                    "precio_original": p_oferta_str, 
                    "precio_oferta": p_oferta_str,
                    "tienda": "Amazon México",
                    "categoria": "General",
                    "caracteristicas": "Oferta relámpago extraída de Amazon",
                    "url": link_producto
                })
            except Exception:
                continue
                
        print(f"✅ [SCRAPER AMAZON] Se extrajeron {len(ofertas)} ofertas con éxito.")
    except Exception as e:
        print(f"❌ [Error Scraper Amazon]: {e}")
        
    return ofertas

def guardar_en_cloudflare_d1(oferta_analizada):
    """Inserta o actualiza la oferta aprobada en la base de datos Cloudflare D1 de forma segura."""
    try:
        titulo = oferta_analizada.get('titulo')
        precio_oferta = oferta_analizada.get('precio_oferta')
        precio_original = oferta_analizada.get('precio_original')
        tienda = oferta_analizada.get('tienda')
        score = oferta_analizada.get('score')
        razonamiento = oferta_analizada.get('razonamiento_antihumo')
        url_original = oferta_analizada.get('url', '')
        
        # ID Único Criptográfico Estable (Previene duplicados en D1)
        string_base = f"{str(titulo).strip().lower()}-{str(tienda).strip().lower()}"
        id_unico = hashlib.sha256(string_base.encode('utf-8')).hexdigest()

        url_final = generar_enlace_afiliado(url_original, tienda)
        
        query = """
            INSERT INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, es_minimo_historico, url_afiliado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                titulo = excluded.titulo,
                precio_original = excluded.precio_original,
                precio_oferta = excluded.precio_oferta,
                descuento = excluded.descuento,
                categoria = excluded.categoria,
                caracteristicas = excluded.caracteristicas,
                es_minimo_historico = excluded.es_minimo_historico,
                url_afiliado = excluded.url_afiliado;
        """
        
        descuento_str = f"Score {score}"
        es_minimo = 1 if score <= 2 else 0

        payload = {
            "sql": query,
            "params": [
                id_unico, str(titulo), str(precio_original), str(precio_oferta), descuento_str, 
                "Sin cupón", str(tienda), "General", str(razonamiento), es_minimo, str(url_final)
            ]
        }

        response = requests.post(URL_D1, headers=HEADERS_D1, json=payload, timeout=12)
        if response.status_code != 200:
            print(f"❌ [Cloudflare HTTP Error] Código {response.status_code}: {response.text}")
            return False
            
        resultado = response.json()
        if resultado.get("success"):
            print(f"🦝 [Score {score}] Sincronizado en D1 -> {titulo} [{tienda}]")
            return True
        else:
            print(f"❌ [Cloudflare D1 Error]: {resultado}")
            return False

    except Exception as e:
        print(f"❌ [Error en Inserción D1]: {e}")
        return False

if __name__ == "__main__":
    print("🚀 [BANDIDO PRODUCCIÓN] Iniciando ciclo autónomo con Scrapers + Cerebro Gemini (1-8) + D1...\n")
    
    # 1. Ejecutamos los scrapers reales de las tiendas configuradas
    ofertas_ml = extraer_ofertas_mercadolibre()
    ofertas_amz = extraer_ofertas_amazon()
    
    todas_las_ofertas = ofertas_ml + ofertas_amz
    print(f"\n📊 Total de ofertas reales recolectadas: {len(todas_las_ofertas)}")
    
    if not todas_las_ofertas:
        print("💡 Nota: Las tiendas aplicaron protección temporal o no devolvieron elementos en esta pasada. El sistema reintentará en el siguiente ciclo automático.")
    
    # 2. Procesar cada oferta real a través del cerebro IA y Cloudflare D1
    for oferta in todas_las_ofertas:
        print(f"\n🧠 Analizando con IA: {oferta['titulo']} [{oferta['tienda']}]")
        analisis_ia = cerebro_ia_antihumo(oferta)
        
        if not analisis_ia:
            print("   ⚠️ El cerebro IA no devolvió respuesta. Saltando...")
            continue
            
        score = analisis_ia.get('score', 8)
        descartar = analisis_ia.get('descartar', True)
        razonamiento = analisis_ia.get('razonamiento_antihumo', '')
        
        print(f"   Score asignado: {score} | ¿Descartar?: {descartar}")
        print(f"   Razonamiento: {razonamiento}")
        
        # 3. Filtro Antihumo Estricto (Acepta niveles 1 a 5; rechaza niveles 6 a 8 de humo)
        if not descartar and score <= 5:
            print("   ✅ ¡Oferta aprobada por Bandido!")
            oferta['score'] = score
            oferta['razonamiento_antihumo'] = razonamiento
            
            # Guardar de forma segura en Cloudflare D1
            guardar_en_cloudflare_d1(oferta)
        else:
            print("   🗑️ Oferta rechazada por humo o precio inflado artificialmente.")
            
    print("\n✨ Ciclo de producción finalizado con éxito.")