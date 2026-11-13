import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import qrcode

def generar_imagen_con_qr(item, ruta_destino="temp_oferta_qr.jpg"):
    """
    Descarga la imagen del producto, le incrusta un código QR dinámico 
    con el enlace de afiliado y genera una pieza visual atractiva para Facebook.
    """
    url_imagen = item.get("imagen_url")
    url_afiliado = item.get("url_afiliado", "https://bandido.bandidoofertas.workers.dev/")
    
    base_img = None
    try:
        if url_imagen:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url_imagen, headers=headers, timeout=10)
            if response.status_code == 200:
                base_img = Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        print(f"⚠️ No se pudo descargar la imagen base: {e}")
    
    # Si falla la descarga, creamos un fondo corporativo oscuro de respaldo
    if not base_img:
        base_img = Image.new("RGB", (800, 800), color=(15, 23, 42))

    # Redimensionar imagen a formato cuadrado limpio de 800x800
    base_img = base_img.resize((800, 800))
    
    # Generar Código QR con el enlace de afiliado o la web
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(url_afiliado)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((180, 180))
    
    # Pegar un fondo blanco esquinero para el QR en la esquina inferior derecha
    draw = ImageDraw.Draw(base_img)
    draw.rectangle([590, 590, 790, 790], fill=(255, 255, 255))
    base_img.paste(qr_img, (600, 600))
    
    # Guardar imagen optimizada
    base_img.save(ruta_destino, quality=90)
    return ruta_destino