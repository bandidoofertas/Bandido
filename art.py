import io
import os
import random
import time
import textwrap
import requests
from PIL import Image, ImageDraw, ImageFont
from cfg import DIR_QR
from calc import auditar_numeros

FRASES_BANNER_ROJO = [
    "💬 ¿TE GUSTÓ? COMENTA EL NÚMERO O TU BANCO Y TE PASO EL LINK 🦝🔥",
    "😏 NO TE HAGAS DEL ROGAR... COMENTA Y TE PASO EL LINK DIRECTO 👇",
    "💬 DIME QUÉ NÚMERO QUIERES EN COMENTARIOS ANTES DE QUE VUELE 🦝✨",
    "🔥 ¿DUDAS SI ES REAL? COMENTA TU BANCO Y TE CALCULO EXTRA 👇",
    "😉 COMENTA 'YO' O EL NÚMERO Y TE LO DEJO EN BANDEJA DE PLATA 🦝💎"
]


def _fuente(tamano: int, negrita: bool = False):
    rutas = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if negrita else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeuib.ttf" if negrita else "C:\\Windows\\Fonts\\segoeui.ttf",
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
    oid = oferta.get("id", int(time.time() * 1000))
    titulo = str(oferta.get("titulo", "Oferta Destacada"))
    tienda = str(oferta.get("tienda", "Tienda")).upper()
    score = int(oferta.get("score", 3) or 3)

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
    f_badge = _fuente(30, True)
    f_tit = _fuente(28, True)
    f_tach = _fuente(26, False)
    f_prec = _fuente(68, True)
    f_banner = _fuente(25, True)

    # 1. Barra superior (Morado poderoso si es Tier 0, Rojo intenso en el resto)
    color_badge = (124, 58, 237) if score == 0 else (220, 38, 38)
    etiqueta_top = f"👑 TIER 0 · {tienda}" if score == 0 else f"BANDIDO OFERTAS  |  {tienda}"

    draw.rounded_rectangle([40, 28, 1040, 102], radius=16, fill=(30, 41, 59))
    draw.text((65, 48), etiqueta_top, fill=(196, 181, 253) if score == 0 else (56, 189, 248), font=f_head)
    draw.rounded_rectangle([815, 36, 1025, 94], radius=12, fill=color_badge)
    draw.text((842, 48), badge, fill=(255, 255, 255), font=f_badge)

    # 2. Vitrina blanca ampliada para que el producto luzca enorme en móvil
    draw.rounded_rectangle([40, 118, 1040, 685], radius=24, fill=(255, 255, 255))
    if url_img and url_img.startswith("http"):
        try:
            r = requests.get(url_img, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            if r.status_code == 200:
                prod = Image.open(io.BytesIO(r.content)).convert("RGBA")
                prod.thumbnail((960, 540), Image.Resampling.LANCZOS)
                px = (1080 - prod.width) // 2
                py = 118 + (567 - prod.height) // 2
                lienzo.paste(prod, (px, py), prod)
        except Exception as e:
            print(f"⚠️ [ART] Sin imagen remota: {e}")

    # 3. Caja de Título y Precios (Ancho completo, sin QR)
    draw.rounded_rectangle([40, 702, 1040, 945], radius=20, fill=(30, 41, 59))
    y_txt = 720
    for linea in textwrap.wrap(titulo, width=56)[:2]:
        draw.text((68, y_txt), linea, fill=(248, 250, 252), font=f_tit)
        y_txt += 35

    if p_or_txt:
        draw.text((68, 805), p_or_txt, fill=(148, 163, 184), font=f_tach)
        # Línea de tachado visual sobre el precio anterior
        ancho_tach = draw.textlength(p_or_txt, font=f_tach)
        draw.line([(68, 820), (68 + ancho_tach, 820)], fill=(239, 68, 68), width=3)

    draw.text((68, 845), p_of_txt, fill=(74, 222, 128), font=f_prec)

    # Sello lateral de verificación antihumo
    draw.rounded_rectangle([730, 815, 1012, 920], radius=14, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
    draw.text((755, 833), "✓ PRECIO AUDITADO", fill=(56, 189, 248), font=_fuente(21, True))
    draw.text((765, 868), "bandidoofertas.com", fill=(203, 213, 225), font=_fuente(20, False))

    # 4. Banner Rojo Inferior con llamada coqueta a comentar
    draw.rounded_rectangle([40, 962, 1040, 1048], radius=18, fill=(220, 38, 38))
    frase_cta = random.choice(FRASES_BANNER_ROJO)
    ancho_cta = draw.textlength(frase_cta, font=f_banner)
    x_cta = max(55, int((1080 - ancho_cta) // 2))
    draw.text((x_cta, 991), frase_cta, fill=(255, 255, 255), font=f_banner)

    salida = DIR_QR / f"qr_{oid}.jpg"
    lienzo.save(salida, "JPEG", quality=94)
    return str(salida)