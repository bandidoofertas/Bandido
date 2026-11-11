import random

def redactar_alerta_oferta(item):
    titulo = item.get("titulo", "Producto increíble")
    precio_oferta = item.get("precio_oferta", "")
    precio_original = item.get("precio_original", "")
    descuento = item.get("descuento", "")
    cupon = item.get("cupon", "Sin cupón")
    tienda = item.get("tienda", "la tienda")
    metodos_pago = item.get("metodos_pago", "")
    url = item.get("url_afiliado", "#")
    nivel = item.get("nivel", 3)

    if nivel == 1:
        ganchos = [
            f"¡Ay, cazador! 🔥 Mira nada más esta joya que encontré para ti en {tienda}. ¡Es una ganga histórica!",
            f"Si dejas ir esta hermosura en {tienda}, me rompes el corazón (y a tu bolsillo también 💔). ¡Fuego total!",
            f"¡Corre antes de que se lo lleve otro, cazador! 🏃‍♂️💨 Esto casi me lo roba la competencia de lo bueno que está."
        ]
    elif nivel == 2:
        ganchos = [
            f"Pss, pss... cazador 👀. Encontré este ofertón en {tienda} que te va a encantar.",
            f"¿Buscando calidad sin gastar una fortuna? 🦝 Te traje esta chulada recién horneada.",
            f"¡Ojo aquí! 🎯 Esta oferta en {tienda} tiene un descuento bien jugoso que no puedes ignorar."
        ]
    else:
        ganchos = [
            f"Una sorpresita más que te robé con cariño de {tienda} 🎁.",
            f"Para los gustos exigentes pero ahorradores... Mira lo que hallé por ahí, cazador 😉.",
            f"Pasaba por {tienda} y no pude evitar traerte esta opción sólida."
        ]

    gancho_elegido = random.choice(ganchos)
    mensaje = f"{gancho_elegido}\n\n"
    mensaje += f"📦 *{titulo}*\n"
    if precio_original:
        mensaje += f"💸 Antes: ~{precio_original}~\n"
    mensaje += f"🏷️ *AHORA: {precio_oferta}* (-{descuento})\n"
    mensaje += f"🛒 Tienda: {tienda}\n"
    if cupon and cupon != "Sin cupón":
        mensaje += f"✂️ Cupón secreto: {cupon}\n"
    if metodos_pago:
        mensaje += f"💳 *Tip de pago:* {metodos_pago}\n"
    mensaje += f"\n👉 ¡Pícalo antes de que vuele aquí:\n{url}"
    return mensaje

def respuesta_chat_interactivo(nombre_usuario="cazador"):
    respuestas = [
        f"¡Hola, {nombre_usuario}! 🦝 Qué gusto verte por aquí. ¿Vienes a ver qué más te robé de las tiendas hoy? La oferta sigue activa, pero los mejores chollos vuelan.",
        f"Míralo quién se aparece... 😏 Si andas buscando el enlace exacto o los trucos de pago para esa joya, pásate por nuestra web oficial. ¡Ahí tengo todo bien ordenado para ti!",
        f"¡Ay, {nombre_usuario}! Me ruborizas con tantas preguntas 🤭. Todo lo que necesitas saber (precios, cupones y dónde cazarlo) está en nuestra web. ¡No te me duermas!"
    ]
    return random.choice(respuestas)
