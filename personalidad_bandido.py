import random

WEB_OFICIAL = "https://bandido.bandidoofertas.workers.dev/"

def redactar_alerta_oferta(item: dict) -> str:
    """
    Genera el texto persuasivo, pícaro y coqueto según el score/nivel de la oferta (1 a 5).
    """
    titulo = item.get("titulo", "Producto increíble")
    precio_oferta = item.get("precio_oferta", "$0")
    precio_original = item.get("precio_original", "")
    descuento = item.get("descuento", "")
    cupon = item.get("cupon", "Sin cupón")
    tienda = item.get("tienda", "la tienda")
    metodos_pago = item.get("metodos_pago", "")
    url = item.get("url_afiliado", WEB_OFICIAL)
    nivel = item.get("score") or item.get("nivel", 3)

    if nivel == 1:
        ganchos = [
            f"¡Ay, cazador! 🔥 Mira nada más esta joya histórica que encontré para ti en {tienda}. ¡Fuego total!",
            f"Si dejas ir esta hermosura en {tienda}, me rompes el corazón (y a tu bolsillo también 💔)."
        ]
    elif nivel == 2:
        ganchos = [
            f"Pss, pss... cazador 👀. Encontré este ofertón en {tienda} que te va a encantar.",
            f"¿Buscando calidad sin gastar una fortuna? 🦝 Te traje esta ganga recién horneada."
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
    
    etiqueta_desc = f" ({descuento})" if descuento else ""
    mensaje += f"🏷️ *AHORA: {precio_oferta}*{etiqueta_desc}\n"
    mensaje += f"🛒 Tienda: {tienda}\n"

    if cupon and cupon != "Sin cupón":
        mensaje += f"✂️ Cupón secreto: `{cupon}`\n"

    if metodos_pago:
        mensaje += f"💳 *Tip de pago:* {metodos_pago}\n"

    mensaje += f"\n👉 ¡Pícalo antes de que vuele aquí:\n{url}"
    return mensaje

def respuesta_chat_interactivo(nombre_usuario="cazador", url_oferta=None, oferta_activa=True) -> str:
    if oferta_activa and url_oferta:
        return (
            f"¡Hola, {nombre_usuario}! 🦝 Qué gusto verte por aquí... Si andabas buscando "
            f"el enlace directo para esa joya antes de que vuele, aquí lo tienes en bandeja de plata 😉👇\n{url_oferta}"
        )
    return (
        f"¡Ay, {nombre_usuario}! Llegaste un suspiro tarde y esa joya ya voló 💔... "
        f"Pero no te me pongas triste, pásate por mi guarida oficial donde tengo muchas más gangas esperándote 🦝✨:\n{WEB_OFICIAL}"
    )