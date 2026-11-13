import os
from PIL import Image, ImageDraw, ImageFont
import qrcode

def procesar_imagen_con_qr(ruta_imagen_original: str, precio_oferta: str, url_afiliado: str, output_path: str = "imagen_final.jpg") -> str:
    """
    Toma la imagen real del producto, genera un código QR con el link de afiliado,
    le incrusta el precio y el QR de manera limpia, y guarda el resultado listo para WhatsApp.
    """
    if not ruta_imagen_original or not os.path.exists(ruta_imagen_original):
        print("⚠️ No se encontró la imagen original para procesar el QR.")
        return None

    try:
        # 1. Abrir la imagen base del producto
        base_img = Image.open(ruta_imagen_original).convert("RGB")
        w_orig, h_orig = base_img.size

        # Redimensionar opcionalmente si es muy grande para mantener un estándar uniforme (ej. 1000x1000)
        target_size = 1000
        base_img = base_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        w, h = base_img.size

        # 2. Generar el Código QR con el enlace de afiliado
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(url_afiliado)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        # Redimensionar el QR a un tamaño adecuado (ej. 220x220 píxeles)
        qr_size = 220
        img_qr = img_qr.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # 3. Crear una franja o lienzo inferior o esquina para el QR y el precio
        # Pegar el QR en la esquina inferior derecha con un pequeño margen (ej. 30px)
        margin = 30
        pos_x = w - qr_size - margin
        pos_y = h - qr_size - margin

        # Dibujar un fondo blanco semitransparente o sólido detrás del QR para que resalte
        padding = 15
        box_bg = Image.new("RGB", (qr_size + (padding * 2), qr_size + (padding * 2) + 40), color=(255, 255, 255))
        
        # Pegar QR sobre su cajita blanca
        box_bg.paste(img_qr, (padding, padding))

        # 4. Agregar el Texto del Precio debajo del QR en la cajita
        draw = ImageDraw.Draw(box_bg)
        try:
            # Intentar cargar una fuente del sistema, si falla usa la predeterminada
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            font = ImageFont.load_default()

        # Escribir el precio centrado en la cajita blanca debajo del QR
        precio_texto = f"A solo {precio_oferta}"
        draw.text((padding + 10, qr_size + 15), precio_texto, fill=(220, 38, 38), font=font) # Rojo llamativo

        # 5. Incrustar la caja completa (QR + Precio) en la imagen principal del producto
        base_img.paste(box_bg, (pos_x - padding, pos_y - padding))

        # 6. Guardar la imagen final lista para redes
        base_img.save(output_path, "JPEG", quality=95)
        print(f"✅ Imagen con QR y precio generada con éxito: {output_path}")
        return output_path

    except Exception as e:
        print(f"⚠️ Error al procesar la imagen con QR: {e}")
        return None

if __name__ == "__main__":
    # Prueba rápida local
    print("🧪 Probando generador de QR y precio...")
    # Asegúrate de tener una imagen de prueba en la carpeta
    procesar_imagen_con_qr(
        ruta_imagen_original="imagenes_bandido/real_12345.jpg", 
        precio_oferta="$5,999", 
        url_afiliado="https://mercadolibre.com.mx/social/cofa20231216170418"
    )
