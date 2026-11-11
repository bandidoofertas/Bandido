import os
import requests
from personalidad_bandido import redactar_alerta_oferta

try:
    from credenciales import FB_ACCESS_TOKEN
except ImportError:
    FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")

# Endpoint oficial de la Graph API de Meta (v18.0 o superior) para páginas de Facebook
# Se usa /me/photos si hay imagen adjunta, o /me/feed si es solo texto.
GRAPH_API_URL = "https://graph.facebook.com/v18.0/me/photos"

def publicar_oferta_facebook(item, ruta_imagen=None):
    """
    Publica una oferta de Nivel 1 o 2 en la Fanpage de Facebook utilizando la Graph API.
    Adjunta la imagen optimizada y el texto redactado por el mapache.
    """
    if not FB_ACCESS_TOKEN:
        print("❌ Error: No se encontró el FB_ACCESS_TOKEN en las credenciales o variables de entorno.")
        return False

    # Validar que la oferta sea de nivel 1 o 2 (las más jugosas)
    nivel = item.get("nivel", 3)
    if nivel > 2:
        print(f"💤 [FACEBOOK] La oferta '{item.get('titulo')}' es de nivel {nivel}, se omite para evitar saturar la fanpage.")
        return False

    # Generar texto coqueto del mapache
    mensaje_coqueto = redactar_alerta_oferta(item)

    # Parámetros para la Graph API
    payload = {
        "message": mensaje_coqueto,
        "access_token": FB_ACCESS_TOKEN
    }

    try:
        if ruta_imagen and os.path.exists(ruta_imagen):
            # Publicación con imagen adjunta (Endpoint de fotos)
            print(f"📸 [FACEBOOK] Publicando oferta con imagen adjunta en la Fanpage...")
            with open(ruta_imagen, "rb") as img_file:
                files = {"source": img_file}
                response = requests.post(GRAPH_API_URL, data=payload, files=files, timeout=30)
        else:
            # Publicación de respaldo solo texto/enlace en el muro (/me/feed)
            print(f"📝 [FACEBOOK] Publicando texto en el muro de la Fanpage...")
            feed_url = "https://graph.facebook.com/v18.0/me/feed"
            response = requests.post(feed_url, data=payload, timeout=30)

        resultado = response.json()
        
        if "id" in resultado:
            print(f"✅ ¡Publicado con éxito en Facebook! ID de post: {resultado['id']}")
            return True
        else:
            print(f"❌ Error devuelto por Meta Graph API: {resultado}")
            return False

    except Exception as e:
        print(f"❌ Excepción de red conectando a la Graph API de Facebook: {e}")
        return False

if __name__ == "__main__":
    # Prueba rápida local simulando una oferta Nivel 1
    oferta_prueba = {
        "titulo": "Laptop ASUS TUF Gaming A15 (Prueba API Meta)",
        "precio_original": "$24,999 MXN",
        "precio_oferta": "$17,499 MXN",
        "descuento": "30%",
        "cupon": "BANDIDOMETA",
        "tienda": "Amazon México",
        "metodos_pago": "10% extra con tarjeta participante",
        "url_afiliado": "https://www.amazon.com.mx",
        "nivel": 1
    }
    print("--- PRUEBA DE PUBLICACIÓN LOCAL FACEBOOK ---")
    publicar_oferta_facebook(oferta_prueba)
