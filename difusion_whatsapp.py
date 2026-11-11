import os
import requests
from datetime import datetime
from personalidad_bandido import redactar_alerta_oferta

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

# Configuración provisional de número de teléfono (personal / pruebas)
# Cambia esta variable o usa os.getenv("WHATSAPP_DESTINO") cuando llegue la eSIM definitiva
TELEFONO_DESTINO = os.getenv("WHATSAPP_DESTINO", "+52155XXXXXXXX") # Reemplaza con tu número de pruebas actual

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

def simular_envio_whatsapp(telefono, mensaje):
    """
    Simula el envío o se conecta a una pasarela (como Meta Cloud API / Baileys / Evolution API).
    Por ahora realiza un despliegue limpio en consola listo para integrarse con la API definitiva.
    """
    print(f"📱 [WHATSAPP OUT] Enviando a -> {telefono}")
    print("--------------------------------------------------")
    print(mensaje)
    print("--------------------------------------------------")
    # Aquí iría el requests.post a tu proveedor de API de WhatsApp usando TELEFONO_DESTINO
    return True

def procesar_difusion_whatsapp():
    print("🦝 [WHATSAPP] Buscando gangas pendientes de difusión...")
    ofertas = obtener_ofertas_pendientes_whatsapp()

    if not ofertas:
        print("💤 No hay ofertas pendientes para WhatsApp en este ciclo.")
        return

    for item in ofertas:
        # Preparamos el formato con la personalidad del mapache
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
        
        # Intentar envío
        exito = simular_envio_whatsapp(TELEFONO_DESTINO, mensaje_final)

        if exito:
            marcar_como_enviado_whatsapp(item.get("id"))
            print(f"✅ Oferta {item.get('titulo')} marcada como enviada en WhatsApp.\n")

if __name__ == "__main__":
    print("🚀 Iniciando motor de difusión autónoma para WhatsApp...")
    procesar_difusion_whatsapp()
    print("🏁 Ciclo de WhatsApp finalizado.")
