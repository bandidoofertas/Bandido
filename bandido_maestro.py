import requests
import json
from credenciales import ACCOUNT_ID, DATABASE_ID, API_TOKEN

URL_D1 = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def publicar_oferta(titulo, precio_original, precio_oferta, descuento, cupon, tienda, url_afiliado):
    query = """
        INSERT INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, url_afiliado, imagen_url)
        VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?, ?, ?, ?, '');
    """
    
    payload = {
        "sql": query,
        "params": [titulo, precio_original, precio_oferta, descuento, cupon, tienda, url_afiliado]
    }
    
    try:
        response = requests.post(URL_D1, headers=HEADERS, data=json.dumps(payload))
        res_data = response.json()
        
        if response.status_code == 200 and res_data.get("success"):
            print(f"🦝 ¡Éxito! Bandido publicó la oferta: {titulo}")
        else:
            print(f"❌ Error al publicar: {res_data}")
    except Exception as e:
        print(f"❌ Error de red: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando motor de Bandido Ofertas...")
    publicar_oferta(
        titulo="Laptop ASUS TUF Gaming A15",
        precio_original="$22,999 MXN",
        precio_oferta="$16,499 MXN",
        descuento="-28%",
        cupon="BANDIDOTUF",
        tienda="Amazon México",
        url_afiliado="https://amazon.com.mx"
    )