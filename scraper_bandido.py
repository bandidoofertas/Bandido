import os
import json
import requests
from bs4 import BeautifulSoup

# Intenta cargar credenciales locales; si no existen, lee de las variables de entorno de GitHub
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

def guardar_en_d1(titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, es_minimo_historico, url_original):
    id_unico = str(abs(hash(titulo + precio_oferta + tienda)))
    minimo_val = 1 if es_minimo_historico else 0
    
    query = """
        INSERT OR REPLACE INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, es_minimo_historico, url_afiliado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    
    payload = {
        "sql": query,
        "params": [
            id_unico, titulo, precio_original, precio_oferta, descuento, 
            cupon, tienda, categoria, caracteristicas, minimo_val, url_original
        ]
    }

    try:
        response = requests.post(URL_D1, headers=HEADERS_CF, json=payload)
        resultado = response.json()
        
        if resultado.get("success"):
            print(f"🦝 [CAZADO Y GUARDADO]: {titulo} [{tienda}]")
        else:
            print(f"❌ Error al guardar en D1: {resultado}")
    except Exception as e:
        print(f"❌ Excepción de red con Cloudflare: {e}")

def raspar_oferta_ejemplo_web(url_objetivo):
    print(f"🔍 Conectando y analizando URL: {url_objetivo} ...")
    try:
        response = requests.get(url_objetivo, headers=HEADERS_WEB, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Error al conectar con la web. Código: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        titulo_extraido = "Laptop Gamer Automática Nocturna"
        precio_ofertado = "$14,999 MXN"
        
        print(f"✅ ¡Datos extraídos con éxito por el bot autónomo!")
        
        guardar_en_d1(
            titulo=titulo_extraido,
            precio_original="$19,999 MXN",
            precio_oferta=precio_ofertado,
            descuento="25%",
            cupon="NOCHEBANDIDO",
            tienda="Amazon México",
            categoria="Computadoras",
            caracteristicas="AMD Ryzen 7 • 16GB RAM • SSD 512GB",
            es_minimo_historico=True,
            url_original=url_objetivo
        )

    except Exception as e:
        print(f"❌ Error ejecutando el scraper: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando el bot cazador automatizado de Bandido...")
    url_prueba = "https://httpbin.org/html" 
    raspar_oferta_ejemplo_web(url_prueba)
    print("🏁 Ciclo de scraping finalizado.")
    