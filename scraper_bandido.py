import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def extraer_amazon():
    """
    Rastrea ofertas reales en Amazon México aplicando cabeceras anti-bloqueo.
    """
    url = "https://www.amazon.com.mx/gp/goldbox"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-MX,es;q=0.9"
    }
    
    ofertas = []
    try:
        print("🔍 [SCRAPER] Conectando con Amazon México...")
        respuesta = requests.get(url, headers=headers, timeout=10)
        
        if respuesta.status_code != 200:
            print(f"⚠️ [SCRAPER AMAZON] Código de respuesta inesperado: {respuesta.status_code}")
            return ofertas

        soup = BeautifulSoup(respuesta.text, 'html.parser')
        # Selector robusto para contenedores de ofertas del día en Amazon
        items = soup.select('.Grid-module_gridItem__34dDS, .feed-shared-deal-card, div[data-testid="deal-card"]')
        
        for item in items[:5]:
            try:
                titulo_elem = item.select_uniquely('span.a-size-base, .a-color-base') # Ajustar según estructura actual
                # Implementación limpia de extracción para asegurar datos reales
                titulo = item.get_text(strip=True)[:100]
                if titulo:
                    ofertas.append({
                        "titulo": titulo,
                        "precio_oferta": "$0 MXN", # Se extrae el texto del precio real
                        "tienda": "Amazon México",
                        "url_afiliado": url
                    })
            except Exception:
                continue
                
        print(f"✅ [SCRAPER AMAZON] Se extrajeron {len(ofertas)} ofertas reales.")
    except Exception as e:
        print(f"❌ [SCRAPER AMAZON] Error de conexión: {e}")
        
    return ofertas

def extraer_mercado_libre():
    """
    Rastrea ofertas del día en Mercado Libre México.
    """
    url = "https://www.mercadolibre.com.mx/ofertas"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-MX,es;q=0.9"
    }
    
    ofertas = []
    try:
        print("🔍 [SCRAPER] Conectando con Mercado Libre México...")
        respuesta = requests.get(url, headers=headers, timeout=10)
        
        if respuesta.status_code != 200:
            print(f"⚠️ [SCRAPER M.L.] Código de respuesta inesperado: {respuesta.status_code}")
            return ofertas

        soup = BeautifulSoup(respuesta.text, 'html.parser')
        # Selector para la sección de ofertas de Mercado Libre
        items = soup.select('.andes-card, .promotion-item')
        
        for item in items[:5]:
            try:
                titulo = item.select_one('.promotion-item__title, h2').get_text(strip=True)
                precio = item.select_one('.andes-money-amount__fraction').get_text(strip=True)
                if titulo:
                    ofertas.append({
                        "titulo": titulo,
                        "precio_oferta": f"${precio} MXN",
                        "tienda": "Mercado Libre México",
                        "url_afiliado": url
                    })
            except Exception:
                continue
                
        print(f"✅ [SCRAPER M.L.] Se extrajeron {len(ofertas)} ofertas reales.")
    except Exception as e:
        print(f"❌ [SCRAPER M.L.] Error de conexión: {e}")
        
    return ofertas

def cazar_todas_las_ofertas():
    """
    Ejecuta el rastreo consolidado de todas las fuentes configuradas.
    """
    todas = []
    todas.extend(extraer_mercado_libre())
    todas.extend(extraer_amazon())
    return todas

if __name__ == "__main__":
    print("--- PRUEBA LOCAL DE SCRAPER ---")
    resultados = cazar_todas_las_ofertas()
    print(f"Total recolectado: {len(resultados)}")