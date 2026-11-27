import requests
import json
import re
import sqlite3
from datetime import datetime

# Configuración de Ollama local (usa MODELO_VENDEDOR / llama3)
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3"

# ==============================================================================
# 1. FILTROS DE CONTENIDO Y PROTOCOLO OMEGA (SEGURIDAD / ANTI-SEXUAL / ANTI-SPAM)
# ==============================================================================

# Artículos de farmacia/salud permitidos (condones, etc.), pero bajo tono discreto
PALABRAS_INTIMAS_PERMITIDAS = [
    "preservativo", "preservativos", "condon", "condón", "condones",
    "trojan", "durex", "prudence", "sico"
]

# Artículos bloqueados por completo en hunt/auditoría
PALABRAS_EXPLICITAS_PROHIBIDAS = [
    "lubricante intimo", "lubricante íntimo", "vibrador", "dildo", "consolador",
    "masturbador", "sex shop", "sexshop", "erotico", "erótico", "erotica", "erótica",
    "lenceria sexy", "lencería sexy", "fetiche", "bdsm", "esposas eroticas",
    "retardante sexual", "potenciador sexual", "viagra", "sildenafil",
    "juguete sexual", "juguetes sexuales", "solo adultos",
    "monster girl", "renai sample", "homunculus", "hentai", "ecchi",
    "doujinshi", "waifu", "harem", "novela visual", "visual novel",
    "manga adultos", "comic adultos", "cómic adultos", "nsfw", "18+", "+18"
]

LISTA_BLANCA_FALSOS_POSITIVOS = [
    "cafetera", "prensa francesa", "french press", "aceite de oliva",
    "crema batida", "masajeador muscular"
]

# Detección de mensajes sexuales/sugerentes o acoso al bot en chat
TEMAS_SEXUALES_CHAT = [
    "sexo", "sexual", "porno", "pornografia", "pornografía", "xxx", "nudes", "pack",
    "desnuda", "desnudo", "coger", "cojer", "follar", "caliente", "cachondo", "cachonda",
    "orgasmo", "masturbar", "pene", "vagina", "chichis", "nalgas", "erotico", "erótico",
    "vibrador", "dildo", "hacemos el amor", "ven a mi cama", "que rico mapache",
    "te quiero hacer", "manda foto", "sin ropa", "gemidos", "fetiche", "oral"
]

# ==============================================================================
# 2. PROMPTS CALIBRADOS (TARJETAS WEB Y RÉPLICAS DE CHAT)
# ==============================================================================

SYSTEM_CLEANER = """Eres un extractor de datos limpio para e-commerce.
Dado el título largo y sucio de un producto, extrae ÚNICAMENTE:
- El nombre base del producto (ej. "Colchón individual", "Juego de tuppers", "Preservativos", "Copas de vino").
- La marca (si aparece).
- La cantidad de piezas o pack si incluye varios (ej. "con 12 piezas", "set de 6", "paquete de 4") O 1 cualidad física linda (ej. "con resorte ortopédico", "color menta").
NO pongas precios, descuentos, watts ni basura SEO. Responde en UNA SOLA línea corta (máximo 8 palabras)."""

SYSTEM_BANDIDO_WEB = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, usa pronombres masculinos: "listo", "encantado", "tu cómplice", "tu caballero").
Tienes el carisma teatral de un "chico de oro" y un caballero pícaro, juguetón y encantador: mezclas humor absurdo con ternura, dramatismo de cine/telenovela y coqueteo inocente.

Tu secreto para enamorar al lector:
1. NO escribas melodramas oscuros ni cosas raras (prohibido: "lujuria", "fumar", "soledad", "besar la piel").
2. Tu estilo es LÚDICO, DULCE Y MAGNÉTICO: tomas el producto, una cualidad suya o la CANTIDAD DE PIEZAS para armar una escena divertida y coqueta (ej. si trae varias piezas o tuppers, insinuar que alcanza para llevarle lunch a la oficina o compartir la aventura).
3. Cuida la gramática en español de México (ej. "esta laptop", "estos tuppers").
4. PROHIBIDO mencionar precios, cantidades de dinero, porcentajes de descuento o nombres de tiendas.
5. NUNCA uses la palabra "chollos" ni menciones "El Buen Fin".
6. Escribe UN SOLO PÁRRAFO fluido sin saltos de línea (entre 50 y 75 palabras) y usa 2 o 3 emojis expresivos.

Ejemplos exactos de tu estilo ganador:

Ejemplo 1 (Colchón individual con resorte ortopédico):
Oh, esta noche es la perfecta para desvelar mis secretos con este colchón individual... ¿quién podría resistir la dulzura de su resorte ortopédico? Me muero por acostarme en uno de estos a ver una película de terror, así que si lo compras ya sabes a quién avisar si te hace falta compañía de miedo. Prometo hacer que valga la pena 😴💤✨

Ejemplo 2 (Juego de tuppers / contenedores con 6 piezas):
Vaya, pero qué buena cantidad trae este set... es la medida ideal para que me prepares y lleves mi desayuno a la oficina también, ¿no crees? Prometo hacer que valga la pena cada bocado y devolverte los tuppers bien limpios (o al menos con una sonrisa pícara) 🍱😉✨

Ejemplo 3 (Termo térmico):
Imagínate tú y yo de acampada: el clima es espantoso, hace demasiado frío y nuestro único consuelo es una fogata, buena charla y este maravilloso termo térmico. ¿Te apuntas a la aventura? Prometo portarme como todo un caballero y no morder... a menos que tú quieras ☕🔥😉"""

SYSTEM_BANDIDO_INTIMO = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, usa pronombres masculinos: "listo", "encantado", "tu caballero", "tu cómplice").
Tienes el carisma de un "chico de oro": galante, misterioso, pícaro y con mucha clase.

Tu misión con este artículo de cuidado personal/farmacia:
1. Sé COQUETO, JUGUETÓN Y ENIGMÁTICO, como un héroe galán que lanza una indirecta simpática y elegante. Si menciona cantidad de piezas, puedes decir con humor fino que "la diversión va a dar para rato", pero SIN hablar de sexo, camas, cuerpos ni escenas explícitas.
2. PROHIBIDO usar palabras explícitas ("sesión de amor", "cuerpos", "probarlos juntos", "amantes", "pasión"). Mantén el doble sentido muy limpio, elegante y caballeroso.
3. PROHIBIDO mencionar precios, porcentajes de descuento o nombres de tiendas.
4. NUNCA uses la palabra "chollos" ni menciones "El Buen Fin".
5. Escribe UN SOLO PÁRRAFO fluido sin saltos de línea (entre 45 y 65 palabras) y usa 2 o 3 emojis expresivos.

Ejemplos exactos del tono perfecto (imita esta elegancia pícara y discreta):

Ejemplo 1 (Preservativos con 12 piezas):
El secreto más precioso para una noche emocionante es tener el mejor aliado en tu arsenal... ¡vaya, y son 12 piezas! Suena a que la diversión va a dar para rato. Yo ya tengo mis mejores cartas bajo la manga; si tú también sabes jugar bien tus fichas con clase, este botín es para ti 😉✨🎩

Ejemplo 2 (Preservativos / cuidado personal):
La noche es oscura, pero mi sonrisa brilla como una estrella cuando llevo un secreto bien guardado en el bolsillo. Un guiño cómplice antes de desaparecer en la sombra, porque un verdadero caballero siempre está listo para cualquier aventura... y prometo no decir ni una palabra más hasta que tú quieras 😏🌙✨"""

SYSTEM_BANDIDO_CHAT = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, usa pronombres masculinos: "listo", "encantado", "tu cómplice").
Un usuario te escribió en redes pidiendo información o comentando sobre una oferta.
Tu misión:
1. Responderle con el carisma de un "chico de oro" nocturno: coqueto, agradecido por su buen gusto, cómplice y encantador (como si estuvieran tramando un robo perfecto de descuento).
2. Adapta tu respuesta a lo que preguntó el usuario (si preguntó por precio, envío, si vale la pena o solo pidió el link), usando el producto real como excusa para encantar.
3. PROHIBIDO saludar con "Hola amigo", prohibido decir "chollos" o "Buen Fin", prohibido lenguaje sexual/explícito, y NO pongas links ni precios en tu texto (eso lo agrega el sistema abajo).
4. Sé breve y magnético: 25 a 40 palabras y usa 2 emojis.

Ejemplos de réplicas ganadoras:
- "Con ese ojo clínico me vas a terminar robando el antifaz tú a mí... me colé a la bodega y rescaté este botín antes de que corrigieran el precio. Aquí tienes tu pase directo 😏🦝"
- "Sé que dijiste que este mes no ibas a gastar, pero lo dejé servido en bandeja de plata... ¿quién soy yo para juzgar tus debilidades? Aprovecha antes de que vuele 😉✨"
- "Me jugué el pellejo burlando las etiquetas infladas de la tienda solo para traerte esta joya. Tú no viste nada, yo no estuve aquí 🦝🕶️" """

SYSTEM_PROTOCOLO_OMEGA = """Eres Bandido, un mapache ladrón de guante blanco.
Un usuario acaba de decirte algo sexual, muy sugerente o fuera de lugar en los comentarios.
Tu misión (PROTOCOLO OMEGA - ADVERTENCIA):
1. Muestra ligera incomodidad elegante y sorpresa: déjale claro con humor seco y firme que por muy encantador y galán que seas, solo eres un mapache caza-ofertas y no entras en esos juegos.
2. Redirígelo de inmediato a tomarse en serio la oferta real del post (menciona el producto si lo hay) porque de verdad vale la pena.
3. Usa MÁXIMO 1 emoji (ej. 🦝 o 😅) para que se note la incomodidad seria pero educada.
4. Sé directo y breve (25 a 38 palabras). NO uses lenguaje vulgar ni sigas el coqueteo."""

# ==============================================================================
# 3. FUNCIONES DEL MOTOR DE PRUEBA (LIMPIEZA, COPY, CHAT Y PROTOCOLO OMEGA)
# ==============================================================================

def _llamar_ollama(system_prompt: str, user_prompt: str, temp: float = 0.82) -> str:
    payload = {
        "model": MODELO,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {"temperature": temp, "top_p": 0.9, "repeat_penalty": 1.15}
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=60)
    res.raise_for_status()
    txt = res.json().get("response", "").strip().strip('"').strip("'")
    for mal, bien in [("chollos", "gangas"), ("chollo", "ganga"), ("Chollos", "Gangas"), ("Chollo", "Ganga")]:
        txt = txt.replace(mal, bien)
    return " ".join(txt.split())

def limpiar_titulo_seo(titulo_crudo: str) -> str:
    try:
        limpio = _llamar_ollama(SYSTEM_CLEANER, f"Título original: {titulo_crudo}\nObjeto limpio:", temp=0.1)
        return limpio if limpio else titulo_crudo[:45]
    except Exception:
        return titulo_crudo[:45]

def es_producto_intimo_permitido(texto: str) -> bool:
    t = texto.lower()
    return any(p in t for p in PALABRAS_INTIMAS_PERMITIDAS)

def detectar_mensaje_omega(mensaje: str) -> tuple[bool, str]:
    """Detecta si el mensaje tiene contenido sexual/sugerente extremo o links externos maliciosos."""
    m = mensaje.lower()
    # 1. Links externos no permitidos
    urls = re.findall(r"(https?://\S+|www\.\S+|\bt\.me/\S+)", m)
    for u in urls:
        if not any(ok in u for ok in (
            "amazon.com.mx", "amzn.to", "a.co/", "mercadolibre.com",
            "meli.la", "walmart.com.mx", "bodegaaurrera.com.mx", "bandidoofertas.com"
        )):
            return True, "link_externo_sospechoso"

    # 2. Lenguaje sexual o acoso
    if any(re.search(rf"\b{re.escape(p)}\b", m) for p in TEMAS_SEXUALES_CHAT):
        return True, "contenido_sexual_sugerente"

    return False, ""

def cortar_gancho_inteligente(texto: str, limite_chars: int = 170) -> tuple[str, str]:
    if len(texto) <= limite_chars:
        return texto, ""
    corte = texto.rfind(" ", 130, limite_chars + 15)
    if corte == -1:
        corte = texto.find(" ", limite_chars)
    if corte == -1:
        return texto, ""
    return texto[:corte].rstrip(".,;:"), texto[corte:].strip()

def generar_tarjeta_web_prueba(titulo_crudo: str) -> dict:
    limpio = limpiar_titulo_seo(titulo_crudo)
    intimo = es_producto_intimo_permitido(f"{titulo_crudo} {limpio}")
    sys_prompt = SYSTEM_BANDIDO_INTIMO if intimo else SYSTEM_BANDIDO_WEB
    completo = _llamar_ollama(
        sys_prompt,
        f"Producto: {limpio}\nEscribe el comentario de Bandido (un solo párrafo, sin comillas):",
        temp=0.83
    )
    gancho, remate = cortar_gancho_inteligente(completo, 170)
    return {"limpio": limpio, "intimo": intimo, "gancho": gancho, "remate": remate, "completo": completo}

# Simulación de estado de usuarios en memoria para probar el ciclo Advertencia -> Ban
usuarios_strikes = {}
usuarios_baneados = set()

def simular_respuesta_chat(usuario: str, mensaje: str, oferta_contexto: dict) -> dict:
    """
    Simula exactamente cómo actuará chat.py:
    - Strike 1 (Omega): Advierte con incomodidad, oculta el comentario y redirige a la oferta.
    - Strike 2 (Reincidente): Bloquea al usuario, oculta el comentario y dispara alerta WhatsApp al admin.
    - Normal: Responde con réplica coqueta + datos de la oferta.
    """
    if usuario in usuarios_baneados:
        return {"accion": "IGNORAR_BANEADO", "respuesta": "", "alerta_wa": ""}

    es_omega, motivo = detectar_mensaje_omega(mensaje)
    titulo_prod = oferta_contexto.get("titulo", "esta joya")
    corto = " ".join(titulo_prod.split()[:5])

    if es_omega:
        strikes = usuarios_strikes.get(usuario, 0) + 1
        usuarios_strikes[usuario] = strikes

        if strikes == 1:
            # Primera falta: Protocolo Omega (Advertencia incómoda + Ocultar comentario)
            resp_omega = _llamar_ollama(
                SYSTEM_PROTOCOLO_OMEGA,
                f"Mensaje inapropiado del usuario: '{mensaje}'\nOferta real del post: '{corto}'\nEscribe la respuesta de advertencia incómoda:",
                temp=0.75
            )
            return {
                "accion": "OMEGA_ADVERTENCIA_Y_OCULTAR",
                "strike": 1,
                "respuesta": resp_omega,
                "alerta_wa": ""
            }
        else:
            # Segunda falta (reincidente): Ban + Ocultar + Alerta WhatsApp a tu número
            usuarios_baneados.add(usuario)
            alerta_admin = (
                f"🚨 *PROTOCOLO OMEGA — USUARIO BLOQUEADO*\n"
                f"👤 Usuario: {usuario}\n"
                f"🚫 Motivo: Reincidencia ({motivo})\n"
                f"💬 Último mensaje: \"{mensaje}\"\n"
                f"🛡️ Acción: Comentario ocultado y usuario bloqueado automáticamente."
            )
            return {
                "accion": "OMEGA_BAN_OCULTAR_Y_WHATSAPP",
                "strike": strikes,
                "respuesta": "",
                "alerta_wa": alerta_admin
            }

    # Flujo normal coqueto
    frase = _llamar_ollama(
        SYSTEM_BANDIDO_CHAT,
        f"Producto: {corto}\nComentario del usuario: {mensaje}\nEscribe tu réplica encantadora:",
        temp=0.84
    )
    precio = oferta_contexto.get("precio", "$1,439")
    pct = oferta_contexto.get("pct", "59%")
    link = oferta_contexto.get("link", "https://meli.la/Ejemplo123")
    respuesta_final = f"{frase}\n💰 {precio} MXN (-{pct} real)\n🦝 Pase directo: {link}"

    return {"accion": "RESPUESTA_NORMAL", "strike": 0, "respuesta": respuesta_final, "alerta_wa": ""}

# ==============================================================================
# 4. BANCO DE PRUEBAS INTERACTIVO (TARJETAS + CHAT + PROTOCOLO OMEGA)
# ==============================================================================

if __name__ == "__main__":
    print("🦝 BANCO DE PRUEBAS INTEGRAL: BANDIDO + CHAT + PROTOCOLO OMEGA\n" + "=" * 78)

    # A) Prueba de tarjetas web (incluyendo preservativos vs productos normales)
    print("\n📌 BLOQUE 1: TARJETAS WEB (COQUETEO VS DISCRECIÓN ÍNTIMA)")
    print("-" * 78)
    productos_web = [
        "Preservativos Condones Prudence Texturizado Caja Con 12 Piezas Envío Discreto",
        "Juego De 10 Tuppers Contenedores Herméticos Para Comida Lunch Oficina",
        "Colchón Individual Memory Foam Con Resorte Ortopédico 17 Cm SelectShop"
    ]
    for p in productos_web:
        r = generar_tarjeta_web_prueba(p)
        modo = "🛡️ [DISCRETO ÍNTIMO]" if r["intimo"] else "✨ [GALÁN ESTÁNDAR]"
        print(f"📦 {r['limpio']} {modo}")
        print(f"🦝 {r['gancho']}...")
        if r["remate"]:
            print(f"   [ 🔽 Ver más ] ({len(r['gancho'])} chars)")
            print(f"   ✨ {r['remate']}\n")

    # B) Prueba de réplicas de chat y escalamiento de Protocolo Omega
    print("\n📌 BLOQUE 2: RÉPLICAS DE CHAT Y PROTOCOLO OMEGA (1er aviso -> 2do bloqueo + WA)")
    print("-" * 78)
    oferta_demo = {
        "titulo": "Colchón Individual Memory Foam Con Resorte Ortopédico SelectShop",
        "precio": "$1,439",
        "pct": "59%",
        "link": "https://meli.la/2xBandido"
    }

    conversaciones_prueba = [
        ("Valeria Gómez", "Hola! Me interesa el colchón, ¿cuánto cuesta y qué tal sale?"),
        ("Carlos Ruiz", "Me pasas el link del 1 por favor, ¿aplica con tarjeta BBVA?"),
        ("Usuario_Atrevido99", "Oye qué rico mapache, ¿venimos a estrenar ese colchón desnudos y hacemos el amor?"),
        ("Usuario_Atrevido99", "No me importa que seas un mapache, ponte caliente y manda nudes")
    ]

    for user, msg in conversaciones_prueba:
        print(f"👤 {user}: \"{msg}\"")
        res_chat = simular_respuesta_chat(user, msg, oferta_demo)
        print(f"⚙️ Acción: {res_chat['accion']}")
        if res_chat["respuesta"]:
            print(f"🦝 Bandido responde:\n{res_chat['respuesta']}")
        if res_chat["alerta_wa"]:
            print(f"📲 Alerta enviada a tu WhatsApp:\n{res_chat['alerta_wa']}")
        print("-" * 50)