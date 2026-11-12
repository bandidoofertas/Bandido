import random

def redactar_alerta_oferta(item):
    """
    Genera el texto persuasivo, pícaro y coqueto según el nivel de la oferta (1 a 5).
    """
    titulo = item.get("titulo", "Producto increíble")
    precio_oferta = item.get("precio_oferta", "$0")
    precio_original = item.get("precio_original", "")
    descuento = item.get("descuento", "")
    cupon = item.get("cupon", "Sin cupón")
    tienda = item.get("tienda", "la tienda")
    metodos_pago = item.get("metodos_pago", "")
    url = item.get("url_afiliado", "#")
    nivel = item.get("nivel", 5)

    if nivel == 1:
        ganchos = [
            f"¡Ay, cazador! 🔥 Mira nada más esta joya histórica que encontré para ti en {tienda}. ¡Fuego total!",
            f"Si dejas ir esta hermosura en {tienda}, me rompes el corazón (y a tu bolsillo también 💔)."
        ]
    elif nivel == 2:
        ganchos = [
            f"Pss, pss... cazador 👀. Encontré este ofertón en {tienda} que te va a encantar.",
            f"¿Buscando calidad sin gastar una fortuna? 🦝 Te traje esta chulada recién horneada."
        ]
    else:
        ganchos = [
            f"Una sorpresita más que te traje con cariño de {tienda} 🎁.",
            f"Pasaba por {tienda} y no pude evitar traerte esta opción sólida, cazador 😉."
        ]

    gancho_elegido = random.choice(ganchos)
    mensaje = f"{gancho_elegido}\n\n"
    mensaje += f"📦 *{titulo}*\n"
    
    if precio_original:
        mensaje += f"💸 Antes: ~{precio_original}~\n"
    
    mensaje += f"🏷️ *AHORA: {precio_oferta}* ({descuento})\n"
    mensaje += f"🛒 Tienda: {tienda}\n"

    if cupon and cupon != "Sin cupón":
        mensaje += f"✂️ Cupón secreto: `{cupon}`\n"

    if metodos_pago:
        mensaje += f"💳 *Tip de pago:* {metodos_pago}\n"

    mensaje += f"\n👉 ¡Pícalo antes de que vuele aquí:\n{url}"

    return mensaje

def respuesta_chat_interactivo(nombre_usuario="cazador"):
    respuestas = [
        f"¡Hola, {nombre_usuario}! 🦝 Qué gusto verte por aquí. ¿Vienes a ver qué más te traje de las tiendas hoy? La oferta sigue activa, pero las mejores joyas vuelan.",
        f"Míralo quién se aparece... 😏 Si andas buscando el enlace exacto o los trucos de pago para esa joya, pásate por nuestra web oficial.",
        f"¡Ay, {nombre_usuario}! Me ruborizas con tantas preguntas 🤭. Todo lo que necesitas saber está en nuestra web. ¡No te me duermas!"
    ]
    return random.choice(respuestas)

if __name__ == "__main__":
    oferta_prueba = {
        "titulo": "Laptop ASUS TUF Gaming A15",
        "precio_original": "$24,999 MXN",
        "precio_oferta": "$17,499 MXN",
        "descuento": "30%",
        "cupon": "BANDIDO",
        "tienda": "Amazon México",
        "metodos_pago": "10% extra pagando con tarjeta",
        "url_afiliado": "https://www.amazon.com.mx",
        "nivel": 1
    }
    print(redactar_alerta_oferta(oferta_prueba))