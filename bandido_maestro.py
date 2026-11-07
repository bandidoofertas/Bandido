import json
import requests
from credenciales import ACCOUNT_ID, DATABASE_ID, API_TOKEN

URL_D1 = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def generar_enlace_afiliado(url_original, tienda):
    """
    Transforma la URL según la tienda.
    Por ahora devuelve la URL directa. Cuando tengas tus IDs de afiliado,
    solo activamos las plantillas de parámetros.
    """
    tienda_lower = tienda.lower()
    
    # Tiendas prioritarias sin afiliado obligatorio (Fidelidad y Caché)
    if "walmart" in tienda_lower or "bodega aurrera" in tienda_lower or "aurrera" in tienda_lower:
        return url_original
        
    # Futuros enlaces de afiliados (Placeholder)
    if "amazon" in tienda_lower:
        # return f"{url_original}?tag=TU_TAG_AMAZON"
        return url_original
    elif "mercado libre" in tienda_lower:
        # return f"{url_original}?pdp_filters=...TU_TAG"
        return url_original
        
    return url_original

def publicar_oferta(titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, es_minimo_historico, url_original):
    id_unico = str(abs(hash(titulo + precio_oferta + tienda)))
    url_final = generar_enlace_afiliado(url_original, tienda)
    minimo_val = 1 if es_minimo_historico else 0
    
    query = """
        INSERT INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, es_minimo_historico, url_afiliado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    
    payload = {
        "sql": query,
        "params": [
            id_unico, titulo, precio_original, precio_oferta, descuento, 
            cupon, tienda, categoria, caracteristicas, minimo_val, url_final
        ]
    }

    try:
        response = requests.post(URL_D1, headers=HEADERS, json=payload)
        resultado = response.json()
        
        if resultado.get("success"):
            print(f"🦝 ¡Éxito! Bandido cazó y publicó: {titulo} [{tienda} | {categoria}]")
        else:
            print(f"❌ Error al publicar: {resultado}")
    except Exception as e:
        print(f"❌ Excepción de red: {e}")

if __name__ == "__main__":
    print("🚀 Ejecutando cazador de Bandido con soporte de viñetas y categorías...")
    
    # Ejemplo 1: Computadoras / Laptops
    publicar_oferta(
        titulo="Laptop ASUS TUF Gaming A15",
        precio_original="$24,999 MXN",
        precio_oferta="$17,499 MXN",
        descuento="30%",
        cupon="BUENFINBANDIDO",
        tienda="Amazon México",
        categoria="Computadoras",
        caracteristicas="AMD Ryzen 7 • RTX 4050 • 16GB RAM • 512GB SSD",
        es_minimo_historico=True,
        url_original="https://www.amazon.com.mx/dp/B00EXAMPLE1"
    )
    
    # Ejemplo 2: Consolas
    publicar_oferta(
        titulo="Consola Nintendo Switch OLED",
        precio_original="$6,599 MXN",
        precio_oferta="$4,290 MXN",
        descuento="35%",
        cupon="DESCUENTOMAMÁ",
        tienda="Bodega Aurrera",
        categoria="Consolas",
        caracteristicas="Pantalla OLED 7 pulgadas • 64GB Almacenamiento • Base LAN",
        es_minimo_historico=False,
        url_original="https://www.bodegaaurrera.com.mx/ip/nintendo-switch-oled"
    )
    
    # Ejemplo 3: Televisores
    publicar_oferta(
        titulo="Pantalla Hisense 55 4K Google TV",
        precio_original="$8,999 MXN",
        precio_oferta="$5,490 MXN",
        descuento="39%",
        cupon="SIN CUPÓN",
        tienda="Walmart México",
        categoria="Televisores",
        caracteristicas="Panel 4K UHD • Google TV Smart • HDR10+ • Dolby Vision",
        es_minimo_historico=True,
        url_original="https://www.walmart.com.mx/ip/pantalla-hisense-55"
    )

    # Ejemplo 4: Audífonos
    publicar_oferta(
        titulo="Audífonos KZ Castor Bass Tuning",
        precio_original="$699 MXN",
        precio_oferta="$420 MXN",
        descuento="40%",
        cupon="AUDIOBANDIDO",
        tienda="AliExpress",
        categoria="Audifonos",
        caracteristicas="Dual Driver Dinámico • Switches de ecualización • Conector 3.5mm",
        es_minimo_historico=True,
        url_original="https://es.aliexpress.com/item/1005001"
    )