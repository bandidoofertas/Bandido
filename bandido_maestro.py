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
    Si no hay programa de afiliado pero la tienda es segura, devuelve el link directo.
    """
    tienda_lower = tienda.lower()
    
    # Tiendas prioritarias / seguras sin afiliado obligatorio (Fidelidad y Caché)
    if "walmart" in tienda_lower or "bodega aurrera" in tienda_lower or "aurrera" in tienda_lower or "adidas" in tienda_lower:
        return url_original
        
    # Futuros enlaces de afiliados (Placeholder)
    if "amazon" in tienda_lower:
        # return f"{url_original}?tag=TU_TAG_AMAZON"
        return url_original
    elif "mercado libre" in tienda_lower:
        # return f"{url_original}?pdp_filters=...TU_TAG"
        return url_original
        
    return url_original

def calcular_scoring_y_niveles(precio_original_num, precio_oferta_num, tiene_cupon):
    """
    Calcula el descuento real y asigna el puntaje inteligente de 1 a 5 para el Buen Fin:
    - Nivel 1 a 3: Mega Ofertas / Alertas de Fuego (Van a Telegram, WhatsApp, Facebook y cola de video).
    - Nivel 4 a 5: Ofertas Estándar / Rellenos (Van únicamente a la Web).
    """
    if precio_original_num <= 0:
        descuento_real = 0.0
        score = 5
    else:
        descuento_real = ((precio_original_num - precio_oferta_num) / precio_original_num) * 100
        descuento_real = round(descuento_real, 2)

    # Reglas de Scoring Antihumo
    if descuento_real >= 40 or (descuento_real >= 30 and tiene_cupon):
        score = 1  # Gangas históricas / Fuego total 🔥
    elif descuento_real >= 25:
        score = 2  # Muy buena oferta
    elif descuento_real >= 15:
        score = 3  # Oferta sólida
    elif descuento_real >= 5:
        score = 4  # Descuento moderado / Estándar
    else:
        score = 5  # Precio regular / Relleno web

    return descuento_real, score

def publicar_oferta(titulo, precio_original, precio_oferta, cupon, tienda, categoria, caracteristicas, url_original):
    """
    Procesa el análisis inteligente de la oferta, calcula su score de 1 a 5,
    determina canales de difusión y la guarda de forma segura en la Base de Datos D1.
    """
    # Limpiar strings de precios para calcular números limpios ($17,499 MXN -> 17499.0)
    try:
        p_orig_num = float(precio_original.replace("$", "").replace("MXN", "").replace(",", "").strip())
        p_ofer_num = float(precio_oferta.replace("$", "").replace("MXN", "").replace(",", "").strip())
    except:
        p_orig_num = 0.0
        p_ofer_num = 0.0

    # Determinar si hay cupón activo
    tiene_cupon = bool(cupon and cupon.strip() != "" and "SIN CUPÓN" not in cupon.upper())
    
    # Calcular descuento real y Score (1 a 5)
    descuento_val, score = calcular_scoring_y_niveles(p_orig_num, p_ofer_num, tiene_cupon)
    descuento_str = f"{descuento_val}%"

    # Definir si es mínimo histórico basado en el score de alta calidad (1 o 2)
    es_minimo_historico = 1 if score <= 2 else 0

    id_unico = str(abs(hash(titulo + precio_oferta + tienda)))
    url_final = generar_enlace_afiliado(url_original, tienda)
    
    # Query optimizada para Cloudflare D1
    query = """
        INSERT OR REPLACE INTO ofertas (id, titulo, precio_original, precio_oferta, descuento, cupon, tienda, categoria, caracteristicas, es_minimo_historico, url_afiliado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    
    payload = {
        "sql": query,
        "params": [
            id_unico, titulo, precio_original, precio_oferta, descuento_str, 
            cupon if tiene_cupon else "Sin cupón", tienda, categoria, caracteristicas, 
            es_minimo_historico, url_final
        ]
    }

    try:
        response = requests.post(URL_D1, headers=HEADERS, json=payload)
        resultado = response.json()
        
        if resultado.get("success"):
            destino = "Redes + Web + Video (Nivel 1-3)" if score <= 3 else "Solo Web (Nivel 4-5)"
            print(f"🦝 [Score {score}] ¡Éxito! Bandido cazó: {titulo} [{tienda}] -> Destino: {destino}")
        else:
            print(f"❌ Error al publicar en D1: {resultado}")
    except Exception as e:
        print(f"❌ Excepción de red con D1: {e}")

if __name__ == "__main__":
    print("🚀 Ejecutando motor maestro de Bandido con Scoring Inteligente (1-5) y Filtros Buen Fin...")
    
    # Pruebas con los productos base
    publicar_oferta(
        titulo="Laptop ASUS TUF Gaming A15",
        precio_original="$24,999 MXN",
        precio_oferta="$17,499 MXN",
        cupon="BUENFINBANDIDO",
        tienda="Amazon México",
        categoria="Computadoras",
        caracteristicas="AMD Ryzen 7 • RTX 4050 • 16GB RAM • 512GB SSD",
        url_original="https://www.amazon.com.mx/dp/B00EXAMPLE1"
    )
    
    publicar_oferta(
        titulo="Consola Nintendo Switch OLED",
        precio_original="$6,599 MXN",
        precio_oferta="$4,290 MXN",
        cupon="",
        tienda="Bodega Aurrera",
        categoria="Consolas",
        caracteristicas="Pantalla OLED 7 pulgadas • 64GB Almacenamiento • Base LAN",
        url_original="https://www.bodegaaurrera.com.mx/ip/nintendo-switch-oled"
    )
    
    publicar_oferta(
        titulo="Tenis Adidas Ultrarun Deportivos",
        precio_original="$1,899 MXN",
        precio_oferta="$1,750 MXN",
        cupon="SIN CUPÓN",
        tienda="Adidas",
        categoria="Moda",
        caracteristicas="Suela amortiguada • Tejido transpirable",
        url_original="https://www.adidas.mx/tenis-ultrarun"
    )