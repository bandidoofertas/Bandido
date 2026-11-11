import os
import requests
from datetime import datetime
from personalidad_bandido import redactar_alerta_oferta
from imagen_bandido import descargar_y_optimizar_imagen

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

TELEFONO_DESTINO = os.getenv("WHATSAPP_DESTINO", "+52155XXXXXXXX")

def obtener_ofertas_pendientes_whatsapp():
    query = "SELECT * FROM ofertas WHERE enviado_whatsapp = 0 AND nivel <= 3 ORDER BY nivel ASC, rowid DESC LIMIT 5;"
    payload = {"sql": query}
    try:
        response = requests.post(URL_D1, headers=HEADERS_CF, json=payload)
        resultado = response.json()
        if resultado.get("success") and resultado.get("result"):
            return resultado["result"][0].get("results", [])
    except Exception as e:
        print(f"❌ Error consultando D1 para WhatsApp: {e}")
    return []

def marcar_como_enviado_whatsapp(id_oferta):
    query = "UPDATE ofertas SET enviado_whatsapp = 1 WHERE id = ?;"
    payload = {"sql": query, "params": [id_oferta]}
    try:
        requests.post(URL_D1, headers=HEADERS_CF, json=payload)
    except Exception as e:
        print(f"⚠️ Error actualizando estado de WhatsApp en D1 para ID {id_oferta}: {e}")

def enviar_whatsapp_con_multimedia(telefono, mensaje, ruta_imagen):
    """
    Estructura lista para conectar con la API de WhatsApp (Meta Cloud / Evolution / Baileys)
    enviando tanto el texto con la personalidad del mapache como la foto del producto.
    """
    print(f"📱 [WHATSAPP MULTIMEDIA] Enviando a -> {telefono}")
    if ruta_imagen and os.path.exists(ruta_imagen):
        print(f"🖼️ [FOTO ADJUNTA] Imagen optimizada lista desde: {ruta_imagen}")
    
    print("--------------------------------------------------")
    print(mensaje)
    print("--------------------------------------------------")
    return True

def procesar_difusion_whatsapp():
    print("🦝 [WHATSAPP] Buscando gangas pendientes con soporte multimedia...")
    ofertas = obtener_ofertas_pendientes_whatsapp()

    if not ofertas:
        print("💤 No hay ofertas pendientes para WhatsApp en este ciclo.")
        return

    for item in ofertas:
        item_para_redes = {
            "titulo": item.get("titulo"),
            "precio_original": item.get("precio_original"),
            "precio_oferta": item.get("precio_oferta"),
            "descuento": item.get("descuento"),
            "cupon": item.get("cupon"),
            "tienda": item.get("tienda"),
            "metodos_pago": item.get("metodos_pago"),
            "url_afiliado": item.get("url_afiliado"),
            "nivel": item.get("nivel")
        }

        mensaje_final = redactar_alerta_oferta(item_para_redes)
        
        # Procesar y optimizar la imagen del producto (si la base de datos almacena el campo url_imagen)
        url_img_original = item.get("url_imagen", "https://via.placeholder.com/600")
        ruta_optimizada = descargar_y_optimizar_imagen(url_img_original)

        exito = enviar_whatsapp_con_multimedia(TELEFONO_DESTINO, mensaje_final, ruta_optimizada)

        if exito:
            marcar_como_enviado_whatsapp(item.get("id"))
            print(f"✅ Oferta {item.get('titulo')} enviada con éxito (Texto + Imagen).\n")
            
        # Limpieza de archivo temporal
        if ruta_optimizada and os.path.exists(ruta_optimizada):
            os.remove(ruta_optimizada)

if __name__ == "__main__":
    print("🚀 Iniciando motor multimedia de difusión para WhatsApp...")
    procesar_difusion_whatsapp()
    print("🏁 Ciclo multimedia finalizado.")
