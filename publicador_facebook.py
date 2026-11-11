import os
import requests
from personalidad_bandido import redactar_alerta_oferta

try:
    from credenciales import FB_ACCESS_TOKEN, FB_PAGE_ID
except ImportError:
    FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
    FB_PAGE_ID = os.getenv("FB_PAGE_ID", "1410612968801274")

def publicar_oferta_facebook(item, ruta_imagen=None):
    if not FB_ACCESS_TOKEN:
        print("❌ Error: No se encontró FB_ACCESS_TOKEN.")
        return False

    # Permitir ofertas de Nivel 1, 2 y 3 (descartar solo 4 y 5)
    nivel = item.get("nivel", 4)
    if nivel > 3:
        print(f"💤 [FACEBOOK] Oferta '{item.get('titulo')}' nivel {nivel} omitida (muy baja calidad o humo).")
        return False

    mensaje_coqueto = redactar_alerta_oferta(item)
    payload = {
        "message": mensaje_coqueto,
        "access_token": FB_ACCESS_TOKEN
    }

    target_id = FB_PAGE_ID if FB_PAGE_ID else "me"
    url_photos = f"https://graph.facebook.com/v18.0/{target_id}/photos"
    url_feed = f"https://graph.facebook.com/v18.0/{target_id}/feed"

    try:
        if ruta_imagen and os.path.exists(ruta_imagen):
            print(f"📸 [FACEBOOK] Publicando foto en la Fanpage {target_id}...")
            with open(ruta_imagen, "rb") as img_file:
                files = {"source": img_file}
                response = requests.post(url_photos, data=payload, files=files, timeout=30)
        else:
            print(f"📝 [FACEBOOK] Publicando post de texto en la Fanpage {target_id}...")
            response = requests.post(url_feed, data=payload, timeout=30)

        resultado = response.json()
        
        if "id" in resultado or "post_id" in resultado:
            post_id = resultado.get("id") or resultado.get("post_id")
            print(f"✅ ¡Publicado en Facebook con éxito! ID: {post_id}")
            return True
        else:
            print(f"❌ Error Meta Graph API: {resultado}")
            return False

    except Exception as e:
        print(f"❌ Excepción conectando a Facebook: {e}")
        return False

if __name__ == "__main__":
    oferta_prueba = {
        "titulo": "Prueba Niveles 1 a 3 - Bandido Ofertas",
        "precio_original": "$1,000 MXN",
        "precio_oferta": "$750 MXN",
        "descuento": "25%",
        "cupon": "BANDIDONIVEL3",
        "tienda": "Amazon México",
        "metodos_pago": "Pago con tarjeta",
        "url_afiliado": "https://www.amazon.com.mx",
        "nivel": 3
    }
    print("--- PRUEBA DE PUBLICACIÓN LOCAL FACEBOOK (NIVEL 3) ---")
    publicar_oferta_facebook(oferta_prueba)
