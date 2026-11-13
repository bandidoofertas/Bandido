import os
import time
import requests
from personalidad_bandido import redactar_alerta_oferta
from imagen_bandido import generar_imagen_con_qr

try:
    from credenciales import FB_ACCESS_TOKEN, FB_PAGE_ID
except ImportError:
    FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
    FB_PAGE_ID = os.getenv("FB_PAGE_ID", "1410612968801274")

ARCHIVO_ULTIMA_HISTORIA = os.path.join("C:\\Bandido\\Bandido", "ultima_historia_fb.txt")
INTERVALO_HISTORIA_SEGUNDOS = 3600  # 1 historia cada hora

def puede_publicar_historia() -> bool:
    if not os.path.exists(ARCHIVO_ULTIMA_HISTORIA):
        return True
    try:
        with open(ARCHIVO_ULTIMA_HISTORIA, "r") as f:
            ultimo_ts = float(f.read().strip())
        return (time.time() - ultimo_ts) >= INTERVALO_HISTORIA_SEGUNDOS
    except:
        return True

def registrar_publicacion_historia():
    with open(ARCHIVO_ULTIMA_HISTORIA, "w") as f:
        f.write(str(time.time()))

def publicar_oferta_facebook(item: dict) -> bool:
    if not FB_ACCESS_TOKEN:
        print("❌ Error: No se encontró FB_ACCESS_TOKEN.")
        return False

    nivel = item.get("score") or item.get("nivel", 5)
    if nivel > 3:
        print(f"💤 [FACEBOOK] Oferta omitida por score bajo ({nivel}).")
        return False

    if not puede_publicar_historia():
        print("⏳ [FACEBOOK STORIES] Aún no pasa 1 hora desde la última historia.")
        return False

    print("🎨 Generando imagen vertical con QR para Historia de Facebook...")
    ruta_imagen = generar_imagen_con_qr(item)
    if not ruta_imagen or not os.path.exists(ruta_imagen):
        print("❌ No se pudo generar la imagen para la historia.")
        return False

    target_id = FB_PAGE_ID if FB_PAGE_ID else "me"

    try:
        # Paso 1: Subir foto sin publicar en feed
        url_upload = f"https://graph.facebook.com/v19.0/{target_id}/photos"
        with open(ruta_imagen, "rb") as img_file:
            res_up = requests.post(
                url_upload,
                data={"published": "false", "access_token": FB_ACCESS_TOKEN},
                files={"source": img_file},
                timeout=30
            ).json()

        photo_id = res_up.get("id")
        if not photo_id:
            print(f"❌ Error subiendo foto base a Meta: {res_up}")
            return False

        # Paso 2: Publicar como Historia de la Página
        url_story = f"https://graph.facebook.com/v19.0/{target_id}/photo_stories"
        res_story = requests.post(
            url_story,
            data={"photo_id": photo_id, "access_token": FB_ACCESS_TOKEN},
            timeout=30
        ).json()

        if "post_id" in res_story or res_story.get("success"):
            registrar_publicacion_historia()
            print(f"✅ ¡Historia publicada en Facebook con éxito! ID: {res_story}")
            return True
        else:
            print(f"❌ Error publicando Historia en Meta Graph API: {res_story}")
            return False

    except Exception as e:
        print(f"❌ Excepción conectando a Facebook Stories: {e}")
        return False