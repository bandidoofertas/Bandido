import os
import io
import json
import time
import qrcode
import requests
from PIL import Image, ImageDraw
import credenciales

WORKER_URL = "https://bandido.bandidoofertas.workers.dev"
HISTORIAL_FB = os.path.join("C:\\Bandido\\Bandido", "historial_fb.json")
CARPETA_QR_FB = os.path.join("C:\\Bandido\\Bandido", "imagenes_fb_qr")

if not os.path.exists(CARPETA_QR_FB):
    os.makedirs(CARPETA_QR_FB)


def cargar_historial() -> set:
    if os.path.exists(HISTORIAL_FB):
        try:
            with open(HISTORIAL_FB, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def guardar_historial(urls: set):
    with open(HISTORIAL_FB, "w", encoding="utf-8") as f:
        json.dump(list(urls), f, ensure_ascii=False, indent=2)


def crear_imagen_con_qr(oferta: dict) -> str:
    """Descarga la foto del producto, la monta en lienzo limpio 1080x1080 y estampa el QR del enlace afiliado."""
    url_img = oferta.get("imagen_url", "")
    url_afiliado = oferta.get("url_afiliado", "")
    oferta_id = oferta.get("id", int(time.time()))

    lienzo = Image.new("RGB", (1080, 1080), (15, 23, 42))

    # Fondo blanco superior para la foto del producto
    draw = ImageDraw.Draw(lienzo)
    draw.rounded_rectangle([40, 40, 1040, 760], radius=24, fill=(255, 255, 255))

    if url_img and url_img.startswith("http"):
        try:
            r = requests.get(url_img, timeout=15)
            if r.status_code == 200:
                prod = Image.open(io.BytesIO(r.content)).convert("RGBA")
                prod.thumbnail((920, 660), Image.Resampling.LANCZOS)
                px = (1080 - prod.width) // 2
                py = 40 + (720 - prod.height) // 2
                lienzo.paste(prod, (px, py), prod)
        except Exception as e:
            print(f"⚠️ No se pudo descargar imagen para FB: {e}")

    # Generar código QR con el link de afiliado
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url_afiliado)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img_qr = img_qr.resize((240, 240), Image.Resampling.LANCZOS)

    # Pegar QR en la esquina inferior derecha
    lienzo.paste(img_qr, (790, 795))

    # Textos inferiores con precio y llamado a escanear
    precio = str(oferta.get("precio_oferta", ""))
    descuento = str(oferta.get("descuento", "OFERTA"))
    tienda = str(oferta.get("tienda", "Tienda")).upper()

    draw.text((60, 810), f"🦝 BANDIDO OFERTAS | {tienda}", fill=(56, 189, 248))
    draw.text((60, 865), f"PRECIO CAZADO: {precio} ({descuento})", fill=(74, 222, 128))
    draw.text((60, 920), "Escanea el QR o entra al link del comentario ->", fill=(248, 250, 252))
    draw.text((60, 975), "Web: bandido.bandidoofertas.workers.dev", fill=(148, 163, 184))

    ruta_salida = os.path.join(CARPETA_QR_FB, f"fb_oferta_{oferta_id}.jpg")
    lienzo.save(ruta_salida, "JPEG", quality=92)
    return ruta_salida


def publicar_en_facebook(ruta_imagen: str, oferta: dict) -> bool:
    page_id = getattr(credenciales, "FB_PAGE_ID", "")
    token = getattr(credenciales, "FB_ACCESS_TOKEN", "")
    if not page_id or not token:
        print("⚠️ Falta FB_PAGE_ID o FB_ACCESS_TOKEN en credenciales.py")
        return False

    titulo = oferta.get("titulo", "")
    precio = oferta.get("precio_oferta", "")
    descuento = oferta.get("descuento", "")
    piropo = oferta.get("razonamiento", "")
    link = oferta.get("url_afiliado", "")

    caption = (
        f"🔥 ¡GANGA CAZADA! ({descuento})\n\n"
        f"📦 {titulo}\n"
        f"💰 Precio: {precio}\n\n"
        f"🦝 {piropo}\n\n"
        f"👉 Consíguelo aquí antes de que vuele: {link}\n"
        f"🌐 Más gangas en vivo: https://bandido.bandidoofertas.workers.dev"
    )

    url_api = f"https://graph.facebook.com/v20.0/{page_id}/photos"
    try:
        with open(ruta_imagen, "rb") as img_file:
            res = requests.post(
                url_api,
                data={"caption": caption, "access_token": token},
                files={"source": img_file},
                timeout=30
            )
        if res.status_code == 200:
            print(f"✅ Publicado en Facebook con éxito: {titulo[:45]}...")
            return True
        else:
            print(f"❌ Error API Facebook ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Excepción publicando en Facebook: {e}")
    return False


def correr_publicador_cada_hora():
    print("🦝 Corredor de Facebook iniciado (1 publicación con QR cada 60 minutos)...")
    while True:
        try:
            historial = cargar_historial()
            r = requests.get(f"{WORKER_URL}/api/ofertas", timeout=15)
            ofertas = r.json() if r.status_code == 200 else []

            # Priorizar Score 1 y 2 no publicadas aún
            candidatas = [
                o for o in ofertas
                if o.get("url_afiliado") not in historial and o.get("score") in (1, 2)
            ]
            if not candidatas:
                candidatas = [o for o in ofertas if o.get("url_afiliado") not in historial]

            if candidatas:
                elegida = candidatas[0]
                ruta_img = crear_imagen_con_qr(elegida)
                if publicar_en_facebook(ruta_img, elegida):
                    historial.add(elegida["url_afiliado"])
                    guardar_historial(historial)
            else:
                print("😴 Sin ofertas nuevas pendientes para Facebook en este turno.")

        except Exception as e:
            print(f"⚠️ Error en ciclo de Facebook: {e}")

        print("⏳ Esperando 1 hora exacta para la siguiente publicación en Facebook...")
        time.sleep(3600)


if __name__ == "__main__":
    correr_publicador_cada_hora()