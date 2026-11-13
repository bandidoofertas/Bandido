import requests
from urllib.parse import urlencode

def formatear_enlace_afiliado_ml(url_producto: str) -> str:
    """
    Inyecta automáticamente tus parámetros oficiales de afiliado de Mercado Libre México.
    """
    BASE_SOCIAL = "https://www.mercadolibre.com.mx/social/cofa20231216170418"
    MATT_WORD = "cofa20231216170418"
    MATT_TOOL = "92220708"
    
    parametros = {
        "matt_word": MATT_WORD,
        "matt_tool": MATT_TOOL,
        "forceInApp": "true"
    }
    
    if url_producto and url_producto != "#":
        parametros["ref_producto"] = url_producto
        
    return f"{BASE_SOCIAL}?{urlencode(parametros)}"

def extraer_mercado_libre():
    """
    Consulta directamente la API pública oficial de Mercado Libre México.
    Retorna datos estructurados limpios en formato JSON con ofertas reales en vivo.
    """
    url = "https://api.mercadolibre.com/sites/MLM/search?q=ofertas&limit=5"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    ofertas = []
    try:
        print("🔍 [API OFICIAL ML] Consultando endpoint público de Mercado Libre...")
        res = requests.get(url, headers=headers, timeout=10)
        print(f"📊 [API ML STATUS]: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            resultados = data.get('results', [])
            
            for item in resultados:
                titulo = item.get('title')
                precio = item.get('price')
                permalink = item.get('permalink')
                thumbnail = item.get('thumbnail')
                
                if titulo and permalink:
                    # Aplicamos tu estructura de afiliado matemática
                    url_final_afiliado = formatear_enlace_afiliado_ml(permalink)
                    
                    precio_formateado = f"${precio:,.2f} MXN" if isinstance(precio, (int, float)) else "Ver en sitio"
                    
                    ofertas.append({
                        "titulo": titulo[:100],
                        "precio_oferta": precio_formateado,
                        "precio_original": "",
                        "descuento": "Destacado",
                        "tienda": "Mercado Libre México",
                        "url_afiliado": url_final_afiliado,
                        "imagen_url": thumbnail or ""
                    })
    except Exception as e:
        print(f"⚠️ [API ML ERROR]: {e}")
        
    return ofertas

def extraer_amazon():
    """
    Estrategia ligera para Amazon México.
    """
    url = "https://www.amazon.com.mx/gp/goldbox"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    ofertas = []
    try:
        print("🔍 [SCRAPER AMZ] Conectando con Amazon México...")
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            # Mantendremos la validación estricta; si Amazon bloquea el HTML estático, retornará vacío limpiamente
            pass
    except Exception as e:
        print(f"⚠️ [AMZ ERROR]: {e}")
    return ofertas

def cazar_todas_las_ofertas():
    todas = []
    todas.extend(extraer_mercado_libre())
    #todas.extend(extraer_amazon())
    print(f"✅ Total de ofertas reales recolectadas: {len(todas)}")
    return todas

if __name__ == "__main__":
    print("--- PRUEBA LOCAL API OFICIAL ---")
    resultados = cazar_todas_las_ofertasfor r in resultados:
    for r in resultados:
        print(r)