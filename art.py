import io
import os
import time
import textwrap
import qrcode
import requests
from PIL import Image, ImageDraw, ImageFont
from cfg import DIR_QR, WORKER_URL
from calc import auditar_numeros

def _fuente(tamano: int, negrita: bool = False):
    rutas = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if negrita else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf" if negrita else "C:\\Windows\\Fonts\\calibri.ttf"
    ]
    for r in rutas:
        if os.path.exists(r):
            try:
                return ImageFont.truetype(r, tamano)
            except Exception:
                continue
    return ImageFont.load_default()

def crear_tarjeta(oferta: dict) -> str:
    url_img = oferta.get("imagen_url", "")
    url_af = oferta.get("url_afiliado") or WORKER_URL
    oid = oferta.get("id", int(time.time() * 1000))
    titulo = str(oferta.get("titulo", "Oferta Destacada"))
    tienda = str(oferta.get("tienda", "Tienda")).upper()

    nums = auditar_numeros(oferta)
    p_of = nums["precio_oferta"]
    p_or = nums["precio_original"]
    pct = nums["pct_real"]

    p_of_txt = f"${p_of:,.0f} MXN" if p_of > 0 else "Ver en sitio"
    p_or_txt = f"Antes: ${p_or:,.0f} MXN" if p_or > p_of > 0 else ""
    badge = f"-{pct}% OFF" if pct > 0 else "OFERTA"

    lienzo = Image.new("RGB", (1080, 1080), (15, 23, 42))
    draw = ImageDraw.Draw(lienzo)

    f_head = _fuente(30, True)
    f_badge = _fuente(28, True)
    f_tit = _fuente(26, True)
    f_tach = _fuente(24, False)
    f_prec = _fuente(56, True)
    f_qr = _fuente(22, True)
    f_foot = _fuente(20, False)

    # Barra superior
    draw.rounded_rectangle([40, 30, 1040, 105], radius=16, fill=(30, 41, 59))
    draw.text((65, 50), f"BANDIDO OFERTAS  |  {tienda}", fill=(56, 189, 248), font=f_head)
    draw.rounded_rectangle([830, 40, 1020, 95], radius=12, fill=(220, 38, 38))
    draw.text((855, 52), badge, fill=(255, 255, 255), font=f_badge)

    # Vitrina blanca (Optimización para que la foto del producto luzca más grande y centrada)
    draw.rounded_rectangle([40, 125, 1040, 680], radius=24, fill=(255, 255, 255))
    if url_img and url_img.startswith("http"):
        try:
            r = requests.get(url_img, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            if r.status_code == 200:
                prod = Image.open(io.BytesIO(r.content)).convert("RGBA")
                # Aumentamos el tamaño máximo para que no se vea tan pequeña
                prod.thumbnail((960, 530), Image.Resampling.LANCZOS)
                px = (1080 - prod.width) // 2
                py = 125 + (555 - prod.height) // 2
                lienzo.paste(prod, (px, py), prod)
        except Exception as e:
            print(f"⚠️ [ART] Sin imagen remota: {e}")

    # Caja inferior izquierda (Datos limpios sin descripciones técnicas kilométricas)
    draw.rounded_rectangle([40, 700, 745, 1040], radius=20, fill=(30, 41, 59))
    y_txt = 720
    for linea in textwrap.wrap(titulo, width=42)[:2]:
        draw.text((65, y_txt), linea, fill=(248, 250, 252), font=f_tit)
        y_txt += 32

    if p_or_txt:
        draw.text((65, 815), p_or_txt, fill=(148, 163, 184), font=f_tach)

    draw.text((65, 855), p_of_txt, fill=(74, 222, 128), font=f_prec)
    draw.text((65, 955), "Comenta tu banco y te calculo promo extra", fill=(56, 189, 248), font=f_foot)
    draw.text((65, 990), "bandidoofertas.com", fill=(148, 163, 184), font=f_foot)

    # Caja inferior derecha (QR)
    draw.rounded_rectangle([765, 700, 1040, 1040], radius=20, fill=(255, 255, 255))
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url_af)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="#0f172a", back_color="white").convert("RGB").resize((225, 225), Image.Resampling.LANCZOS)
    lienzo.paste(img_qr, (790, 720))

    draw.text((805, 960), "ESCANEA AQUÍ", fill=(15, 23, 42), font=f_qr)
    draw.text((802, 990), "O ENTRA AL LINK", fill=(37, 99, 235), font=f_qr)

    salida = DIR_QR / f"qr_{oid}.jpg"
    lienzo.save(salida, "JPEG", quality=94)
    return str(salida)