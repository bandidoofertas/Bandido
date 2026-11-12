import json
import hashlib
import requests
from bs4 import BeautifulSoup
from credenciales import ACCOUNT_ID, DATABASE_ID, API_TOKEN

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

def calcular_scoring_y_niveles(precio_original_num, precio_oferta_num, tiene_cupon):
    """Calcula el descuento real y asigna el puntaje inteligente de 1 al 5."""
    try:
        if precio_original_num <= 0:
            return 0.0, 5
            
        descuento_real = ((precio_original_num - precio_oferta_num) / precio_original_num) * 100
        descuento_real = round(descuento_real, 2)

        # Reglas de Scoring Antihumo
        if descuento_real >= 40 or (descuento_real >= 30 and tiene_cupon):
            score = 1  # Gangas históricas 🔥
        elif descuento_real >= 25:
            score = 2  # Muy buena oferta
        elif descuento_real >= 15:
            score = 3  # Oferta sólida
        elif descuento_real >= 5:
            score = 4  # Descuento moderado
        else:
            score = 5  # Precio regular

        return descuento_real, score
    except Exception as e:
        print(f"❌ [Error en Scoring] Falló el cálculo matemático de precios: {e}")
        return 0.0, 5

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
                    "cupon": "",
                    "tienda": "Mercado Libre",
                    "categoria": "General",
                    "caracteristicas": "Oferta relámpago extraída de Mercado Libre",
                    "url": link_producto
                })
            except Exception:
                continue
                
        print(f"✅ [SCRAPER M.L.] Se extrajeron {lenofertas if 'ofertas' in locals() else len(ofertas)} ofertas con éxito.")
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
                    "precio_original": p_oferta_str, # Se alinea al precio actual si no hay lista explícita
                    "precio_oferta": p_oferta_str,
                    "cupon": "",
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

def procesar_y_guardar_oferta(oferta_bruta):
    """Procesa, calcula métricas, evita duplicados y guarda directo en Cloudflare D1."""
    try:
        titulo = oferta_bruta.get('titulo')
        precio_original = oferta_bruta.get('precio_original')
        precio_oferta = oferta_bruta.get('precio_oferta')
        tienda = oferta_bruta.get('tienda')
        
        if not titulo or not precio_oferta or not tienda:
            return False

        cupon = oferta_bruta.get('cupon', '')
        categoria = oferta_bruta.get('categoria', 'General')
        caracteristicas = oferta_bruta.get('caracteristicas', '')
        url_original = oferta_bruta.get('url', '')

        # Limpieza de precios para cálculo numérico
        try:
            p_orig_num = float(str(precio_original).replace("$", "").replace("MXN", "").replace(",", "").strip())
            p_ofer_num = float(str(precio_oferta).replace("$", "").replace("MXN", "").replace(",", "").strip())
        except Exception:
            p_orig_num = 0.0
            p_ofer_num = 0.0

        tiene_cupon = bool(cupon and str(cupon).strip() != "" and "SIN CUPÓN" not in str(cupon).upper())
        descuento_val, score = calcular_scoring_y_niveles(p_orig_num, p_ofer_num, tiene_cupon)
        descuento_str = f"{descuento_val}%"
        es_minimo_historico = 1 if score <= 2 else 0

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
                cupon = excluded.cupon,
                categoria = excluded.categoria,
                caracteristicas = excluded.caracteristicas,
                es_minimo_historico = excluded.es_minimo_historico,
                url_afiliado = excluded.url_afiliado;
        """
        
        payload = {
            "sql": query,
            "params": [
                id_unico, str(titulo), str(precio_original), str(precio_oferta), descuento_str, 
                str(cupon) if tiene_cupon else "Sin cupón", str(tienda), str(categoria), 
                str(caracteristicas), es_minimo_historico, str(url_final)
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
    print("🚀 [BANDIDO PRODUCCIÓN] Iniciando ciclo de scraping real en vivo...\n")
    
    # Ejecutamos los scrapers reales de las tiendas configuradas
    ofertas_ml = extraer_ofertas_mercadolibre()
    ofertas_amz = extraer_ofertas_amazon()
    
    todas_las_ofertas = ofertas_ml + ofertas_amz
    print(f"\n📊 Total de ofertas reales recolectadas: {len(todas_las_ofertas)}")
    
    if not todas_las_ofertas:
        print("💡 Nota: Las tiendas aplicaron protección temporal o no devolvieron elementos en esta pasada. El sistema reintentará en el siguiente ciclo automático.")
    
    # Procesar y enviar directamente a Cloudflare D1
    for oferta in todas_las_ofertas:
        procesar_y_guardar_oferta(oferta)
        
    print("\n✨ Ciclo de producción finalizado con éxito.")