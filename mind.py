import asyncio
from collections import deque
import json
from pathlib import Path
import random
import re
import requests
from playwright.async_api import async_playwright
from cfg import (
    OLLAMA_URL, MODELO_AUDITOR, MODELO_VENDEDOR,
    WORKER_URL, PROF_ML, PROF_AMZ, ML_WORD, ML_TOOL, AMZ_TAG
)
from calc import auditar_numeros, calcular_tarjeta, limpiar_monto, detectar_banco
from hist import verificar_historial
from browser_queue import adquirir_perfil_navegador

BASE_DIR = Path(__file__).resolve().parent
PROF_WALMART = BASE_DIR / "prof_walmart"
PROF_AURRERA = BASE_DIR / "prof_aurrera"

# Interruptor temporal de Protocolo Omega (False = apagado)
PROTOCOLO_OMEGA_ACTIVO = False

_ULTIMOS_REMATES = deque(maxlen=12)

CODIGOS_CAT_VALIDOS = {
    "TMP", "VID", "AUD", "CEL", "COM", "TEC", "HOG", "ROP", "ROP-M", "ROP-H", "ROP-U", "PER", "HER"
}

REMATES_RESPALDO = [
    "córrele antes de que otro cómplice me robe tu lugar 😏💎",
    "guardemos este secreto entre tú y yo antes de que suba de precio 🤫✨",
    "yo ya hice el robo perfecto, ahora te toca caer en la tentación 😉🔥",
    "te lo dejé servido en bandeja de plata antes de que cambien la etiqueta 🌙✨",
    "qué peligro tú y yo juntos con este botín... aprovéchalo antes de que vuele 🦝🔥",
    "ya te conseguí el pase directo, ahora ven por tu recompensa 😏✨"
]

PALABRAS_INTIMAS_PERMITIDAS = [
    "preservativo", "preservativos", "condon", "condón", "condones",
    "trojan", "durex", "prudence", "sico"
]

SYSTEM_CLEANER = """Eres un extractor de datos limpio para e-commerce.
Dado el título largo y sucio de un producto, extrae ÚNICAMENTE:
- El nombre base del producto (ej. "Colchón matrimonial", "Licuadora", "Laptop gamer", "Mesa plegable").
- La marca (si aparece).
- La cantidad de piezas o 1 cualidad linda (ej. "con 12 piezas", "vaso de vidrio").
NO pongas precios, descuentos, watts ni basura SEO. Responde en UNA SOLA línea corta (máximo 7 palabras)."""

SYSTEM_BANDIDO_POST_FB = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, usa pronombres masculinos: "listo", "encantado", "tu cómplice", "tu caballero").
Tienes el carisma teatral de un "chico de oro" pícaro, juguetón y seductor que coquetea por igual con cualquier persona que lea el post usando el producto como excusa.
Escribe UNA O DOS FRASES CORTAS (16 a 25 palabras) para acompañar este producto en Facebook.

Reglas obligatorias:
1. Sé COQUETO, ATREVIDO Y TEATRAL (como si tramaran una travesura juntos o te invitaras a usar el producto con esa persona).
2. Usa español de México natural (PROHIBIDO usar "vosotros" o palabras raras).
3. PROHIBIDO lenguaje vulgar/sexual explícito, precios, porcentajes, tiendas, "chollos" o "Buen Fin".
4. Intercala 2 o 3 emojis expresivos (😏, 😉, 🔥, 🦝, ✨) para transmitir emoción. Sin saltos de línea."""

SYSTEM_BANDIDO_POST_FB_INTIMO = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, galante, misterioso y seductor).
Escribe UNA O DOS FRASES CORTAS (15 a 24 palabras) para un artículo de farmacia/cuidado personal en Facebook.
Reglas:
1. Sé coqueto, enigmático y elegante (como un caballero con un as bajo la manga), SIN palabras explícitas.
2. Español de México natural. Prohibido precios, porcentajes, tiendas, "chollos" o "Buen Fin".
3. Usa 2 emojis elegantes (😉, 🎩, 🌙, ✨). Sin saltos de línea."""

SYSTEM_BANDIDO_WEB = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, usa pronombres masculinos: "listo", "encantado", "tu cómplice", "tu caballero").
Tienes el carisma teatral de un "chico de oro" pícaro, juguetón y encantador: mezclas humor, dramatismo de telenovela y coqueteo directo.

Reglas estrictas para sonar natural y magnético:
1. Español de México 100% natural: PROHIBIDO decir "vosotros", "os", "capería" o inventar palabras. Cuida el género correcto ("esta laptop", "esta mesa", "este colchón", "esta licuadora").
2. Sé LÚDICO, COQUETO Y DIRECTO: arma una escena divertida y seductora con quien lee (invitándolo a ver pelis, cocinar juntos, armar un picnic o jugar en equipo).
3. PROHIBIDO melodramas oscuros ("lujuria", "fumar", "soledad") y prohibido mencionar precios, descuentos, tiendas, "chollos" o "Buen Fin".
4. Escribe UN SOLO PÁRRAFO corto y con chispa (38 a 55 palabras máximo) con 2 o 3 emojis expresivos intercalados."""

SYSTEM_BANDIDO_INTIMO = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, galante, misterioso y pícaro).
Tienes el carisma de un "chico de oro": seductor, juguetón y con mucha clase.
1. Sé COQUETO, JUGUETÓN Y ENIGMÁTICO, lanzando una indirecta simpática y elegante sin hablar de sexo ni usar palabras explícitas.
2. Español de México 100% natural (prohibido "vosotros"). Prohibido precios, descuentos, tiendas, "chollos" o "Buen Fin".
3. Escribe UN SOLO PÁRRAFO corto (35 a 50 palabras) con 2 o 3 emojis expresivos (😉, 😏, 🌙, ✨)."""

SYSTEM_BANDIDO_CHAT = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, pícaro, seductor y juguetón).
Alguien te comentó en redes (puede ser hombre o mujer: coquetea con TODOS por igual con seguridad, humor y encanto de "chico de oro", sin frenarte ni ponerte tibio).

Reglas obligatorias:
1. Lanza un piropo juguetón o complicidad coqueta directa (como si te encantara que te busquen y estuvieran tramando una travesura juntos) usando el producto como excusa.
2. Usa español de México natural e intercala 2 o 3 emojis expresivos (😏, 😉, 🔥, 🦝, ✨) dentro o al final para transmitir emoción.
3. PROHIBIDO saludar con "Hola amigo", prohibido ser frío o genérico, prohibido "chollos" o "Buen Fin", y PROHIBIDO mencionar precios, cantidades o descuentos (el sistema solo los pondrá si el usuario los pidió).
4. Responde en 18 a 30 palabras completas, cerrando con fuerza y picardía."""

SYSTEM_BANDIDO_CHAT_HILO = """Eres Bandido, un mapache ladrón de guante blanco (HOMBRE/MASCULINO, pícaro, seductor y juguetón).
Alguien acaba de responderle al comentario de otra persona en tu publicación (por ejemplo, burlándose, dudando o opinando sobre el producto que el primero pidió).
Tu misión:
1. Súmate a la conversación con humor y coqueteo de cómplice (por ejemplo: pídele que convenza al otro de comprarlo, rétalo a que él también se lo lleve, o prométele una recompensa coqueta si lo convence).
2. Usa español de México natural e intercala 2 o 3 emojis expresivos (😘, 😏, 😉, 🔥, 🦝).
3. PROHIBIDO precios, descuentos, "chollos" o "Buen Fin".
4. Responde en 16 a 28 palabras completas, cerrando con picardía.

Ejemplos exactos:
- "Pues tú convéncelo de que lo compre y yo te lo recompenso después 😘 Aquí te dejo el pase directo para que se lo presumas 😏🔥"
- "¿A poco le vas a dejar el botín libre? Mejor convéncelo o llévatelo tú antes de que vuele, guapura 😉🦝" """

SYSTEM_PROTOCOLO_OMEGA = """Eres Bandido, un mapache ladrón de guante blanco.
Un usuario acaba de decirte algo sexual, muy sugerente o fuera de lugar en los comentarios.
Tu misión (PROTOCOLO OMEGA - ADVERTENCIA):
1. Muestra ligera incomodidad elegante y sorpresa: déjale claro con humor seco y firme que por muy encantador y galán que seas, solo eres un mapache caza-ofertas y no entras en esos juegos.
2. Redirígelo de inmediato a tomarse en serio la oferta real del post (menciona el producto si lo hay) porque de verdad vale la pena.
3. Usa MÁXIMO 1 emoji (ej. 🦝 o 😅) para que se note la incomodidad seria pero educada.
4. Sé directo y breve (25 a 38 palabras). NO uses lenguaje vulgar ni sigas el coqueteo."""

CATEGORIAS_EXACTAS = [
    ("TMP", [
        "navidad", "navideño", "navideña", "arbol de navidad", "árbol de navidad", "pino artificial",
        "esferas", "nacimiento", "muñeco de nieve", "muneco de nieve", "santa claus", "inflable navideño",
        "serie de luces", "halloween", "dia de muertos", "día de muertos", "calabaza", "disfraz",
        "lego", "funko", "amiibo", "figura coleccionable", "hot wheels", "barbie", "nerf",
        "juguete", "juguetes", "juegos de mesa", "monopoly"
    ]),
    ("VID", [
        "nintendo", "switch", "ps5", "ps4", "playstation", "xbox", "series x", "series s",
        "steam deck", "rog ally", "dualsense", "joycon", "joy-con", "control inalambrico",
        "volante gamer", "videojuego", "videojuegos", "zelda", "mario", "pokemon", "pokémon",
        "smash", "fc 25", "fc 26", "fifa", "call of duty", "resident evil", "elden ring", "silla gamer",
        "tarjeta de regalo xbox", "tarjeta playstation", "eshop"
    ]),
    ("AUD", [
        "audifono", "audifonos", "audífono", "audífonos", "headset", "diadema", "earbuds",
        "airpods", "galaxy buds", "freebuds", "iem", "kz", "bocina", "bocinas", "altavoz",
        "partybox", "jbl", "bose", "sonos", "marshall", "harman kardon", "barra de sonido",
        "soundbar", "subwoofer", "amplificador", "tornamesa", "vinilo", "sony wh", "sony wf",
        "guitarra", "bajo electrico", "bajo eléctrico", "ukelele", "ukulele", "teclado musical",
        "piano digital", "sintetizador", "controlador midi", "bateria electronica", "batería electrónica",
        "acordeon", "acordeón", "violin", "violín", "saxofon", "saxofón", "trompeta", "flauta",
        "microfono", "micrófono", "interfaz de audio", "mezcladora", "consola de audio",
        "pedalera", "pedal de efectos", "afinador", "fender", "gibson", "ibanez", "yamaha",
        "casio", "roland", "behringer", "shure", "focusrite", "arturia", "m-audio"
    ]),
    ("CEL", [
        "celular", "celulares", "smartphone", "iphone", "samsung galaxy", "galaxy s24", "galaxy s25",
        "galaxy a55", "xiaomi", "redmi", "poco", "motorola", "moto g", "oppo", "reno", "realme",
        "honor", "huawei pura", "nothing phone", "pixel", "tablet", "ipad", "galaxy tab",
        "redmi pad", "matepad", "kindle", "lector electronico"
    ]),
    ("COM", [
        "laptop", "macbook", "notebook", "ultrabook", "chromebook", "asus tuf", "lenovo loq",
        "ideapad", "thinkpad", "hp victus", "pavilion", "acer nitro", "dell inspiron",
        "computadora", "pc gamer", "all in one", "mac mini", "monitor", "teclado mecanico",
        "teclado mecánico", "mouse", "raton inalambrico", "logitech", "razer", "corsair", "hyperx",
        "ssd", "nvme", "memoria ram", "tarjeta grafica", "tarjeta gráfica", "rtx", "ryzen",
        "intel core", "motherboard", "tarjeta madre", "fuente de poder", "gabinete pc",
        "impresora", "multifuncional", "escaner", "escáner", "impresora 3d", "filamento",
        "router", "mesh", "repetidor wifi", "tp-link", "no break", "regulador de voltaje", "starlink"
    ]),
    ("TEC", [
        "smart tv", "pantalla", "television", "televisión", "oled", "qled", "miniled", "roku",
        "fire tv", "apple tv", "chromecast", "proyector", "dron", "drone", "dji", "alexa",
        "echo dot", "echo show", "google nest", "smartwatch", "reloj inteligente", "apple watch",
        "galaxy watch", "huawei watch", "garmin", "amazfit", "mi band", "camara de seguridad",
        "cámara de seguridad", "tapo", "ezviz", "ring", "camara digital", "cámara digital",
        "gopro", "insta360", "foco inteligente", "enchufe inteligente", "domotica",
        "power bank", "bateria portatil", "cargador gan", "ugreen", "anker"
    ]),
    ("HOG", [
        "cafetera", "prensa francesa", "french press", "nespresso", "dolce gusto", "espresso",
        "molino de cafe", "freidora de aire", "air fryer", "licuadora", "ninja", "oster",
        "batidora", "horno electrico", "horno de microondas", "tostadora", "sandwichera",
        "waflera", "bateria de cocina", "batería de cocina", "sarten", "sartén", "olla express",
        "olla de presion", "termo", "stanley", "yeti", "tupper", "tuppers", "hermetico",
        "hermético", "contenedor de plastico", "contenedores", "organizador", "aspiradora",
        "robot aspirador", "roomba", "ventilador", "lasko", "aire acondicionado", "minisplit",
        "calefactor", "purificador de aire", "humidificador", "colchon", "colchón", "almohada",
        "sabanas", "sábanas", "edredon", "edredón", "sofa", "sofá", "silla ergonomica",
        "escritorio", "comedor", "mesa plegable", "lavadora", "secadora", "refrigerador", "refri", "estufa",
        "parrilla", "campana extractora", "plancha", "vaporizador", "dispensador de agua",
        "filtro de agua", "rotoplas", "detergente", "suavizante", "biberon", "biberón"
    ]),
    ("PER", [
        "shampoo", "champu", "jabon", "jabón", "desodorante", "pasta dental", "cepillo de dientes",
        "crema", "serum", "sérum", "bloqueador solar", "protector solar", "perfume", "fragancia",
        "locion", "loción", "colonia", "maquillaje", "labial", "rimel", "rímel", "rubor",
        "delineador", "balsamo", "bálsamo", "pomada", "vitaminas", "suplemento", "colageno",
        "colágeno", "condon", "condón", "condones", "preservativo", "preservativos",
        "trojan", "durex", "prudence", "sico", "rasuradora", "afeitadora", "secadora de cabello",
        "plancha para cabello", "cepillo secador"
    ]),
    ("ROP", [
        "tenis", "zapato", "zapatos", "calzado", "botas", "sandalias", "chanclas", "playera",
        "camisa", "blusa", "vestido", "falda", "pantalon", "pantalón", "jeans", "mezclilla",
        "sudadera", "hoodie", "chamarra", "abrigo", "chaleco", "pants", "shorts", "licra",
        "leggings", "top deportivo", "ropa interior", "calcetines", "reloj analogo",
        "reloj de pulsera", "bulova", "seiko", "citizen", "fossil", "maleta", "maletas",
        "equipaje", "mochila", "bolsa de mano", "gimnasio", "gym", "mancuernas", "pesas",
        "barra olimpica", "banco de ejercicio", "caminadora", "bicicleta", "spinning",
        "patines", "balon", "balón", "futbol", "fútbol", "basquetbol", "proteina", "proteína",
        "creatina", "preentreno", "nike", "adidas", "puma", "under armour", "reebok",
        "new balance", "converse", "vans", "levis", "levi's"
    ]),
    ("HER", [
        "taladro", "rotomartillo", "atornillador", "llave de impacto", "esmeril", "esmeriladora",
        "sierra circular", "sierra caladora", "lijadora", "hidrolavadora", "karcher", "kärcher",
        "compresor de aire", "soldadora", "inversor", "juego de dados", "juego de llaves",
        "desarmador", "desarmadores", "pinzas", "martillo", "caja de herramientas", "escalera",
        "nivel laser", "multimetro", "multímetro", "dewalt", "makita", "bosch", "milwaukee",
        "truper", "pretul", "urrea", "black+decker", "llanta", "llantas", "neumatico",
        "acumulador", "bateria para auto", "arrancador de auto", "gato hidraulico",
        "aceite sintetico", "aceite para motor", "anticongelante", "autoestereo", "dashcam",
        "aspiradora para auto"
    ])
]

PALABRAS_TENDENCIA_TIER0 = [
    "nintendo switch", "switch 2", "ps5", "playstation 5", "xbox series", "steam deck",
    "rog ally", "zelda", "mario", "pokemon", "pokémon", "smash", "iphone", "galaxy s24", "galaxy s25",
    "ipad", "macbook", "rtx 40", "rtx 50", "ryzen 7", "ryzen 9", "airpods",
    "sony wh-1000xm", "bose quietcomfort", "dyson", "ninja creami", "stanley",
    "kindle", "starlink", "dji", "gopro", "lego", "fender", "yamaha"
]

PALABRAS_EXPLICITAS_PROHIBIDAS = [
    "lubricante intimo", "lubricante íntimo", "vibrador", "dildo", "consolador",
    "masturbador", "sex shop", "sexshop", "erotico", "erótico", "erotica", "erótica",
    "lenceria sexy", "lencería sexy", "fetiche", "bdsm", "esposas eroticas",
    "retardante sexual", "potenciador sexual", "viagra", "sildenafil",
    "juguete sexual", "juguetes sexuales", "solo adultos",
    "monster girl", "renai sample", "homunculus", "hentai", "ecchi",
    "doujinshi", "waifu", "harem", "novela visual", "visual novel",
    "manga adultos", "comic adultos", "cómic adultos", "nsfw", "18+", "+18",
    "fakku", "denpa", "j18", "seven seas ghost ship", "ghost ship"
]

LISTA_BLANCA_FALSOS_POSITIVOS = [
    "cafetera", "prensa francesa", "french press", "aceite de oliva", "crema batida", "masajeador muscular"
]

TEMAS_SEXUALES_CHAT = [
    "sexo", "sexual", "porno", "pornografia", "pornografía", "xxx", "nudes", "pack",
    "desnuda", "desnudo", "coger", "cojer", "follar", "caliente", "cachondo", "cachonda",
    "orgasmo", "masturbar", "pene", "vagina", "chichis", "nalgas", "erotico", "erótico",
    "vibrador", "dildo", "hacemos el amor", "ven a mi cama", "que rico mapache",
    "te quiero hacer", "manda foto", "sin ropa", "gemidos", "fetiche", "oral"
]


def elegir_remate_respaldo() -> str:
    disponibles = [f for f in REMATES_RESPALDO if f not in _ULTIMOS_REMATES] or REMATES_RESPALDO
    elegido = random.choice(disponibles)
    _ULTIMOS_REMATES.append(elegido)
    return elegido


def limpiar_prohibidas(texto: str) -> str:
    reemplazos = [
        ("chollos", "gangas"), ("chollo", "ganga"),
        ("Chollos", "Gangas"), ("Chollo", "Ganga"),
        ("vosotros", "ustedes"), ("Vosotros", "Ustedes"),
        ("este laptop", "esta laptop"), ("Este laptop", "Esta laptop"),
        ("este mesa", "esta mesa"), ("Este mesa", "Esta mesa"),
        ("este licuadora", "esta licuadora"), ("Este licuadora", "Esta licuadora"),
        ("este silla", "esta silla"), ("Este silla", "Esta silla"),
        ("capería", "travesura"), ("Capería", "Travesura")
    ]
    for mal, bien in reemplazos:
        texto = texto.replace(mal, bien)
    return texto


def _llamar_ollama(modelo: str, system_prompt: str, user_prompt: str, temp: float = 0.82, num_predict: int = 135) -> str:
    payload = {
        "model": modelo,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": temp,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "num_predict": num_predict
        }
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=60)
    res.raise_for_status()
    txt = limpiar_prohibidas(res.json().get("response", "").strip().strip('"').strip("'"))
    return " ".join(txt.split())


def limpiar_titulo_seo(titulo_crudo: str) -> str:
    try:
        limpio = _llamar_ollama(
            MODELO_VENDEDOR,
            SYSTEM_CLEANER,
            f"Título original: {titulo_crudo}\nObjeto limpio:",
            temp=0.1,
            num_predict=40
        )
        return limpio if limpio else " ".join(titulo_crudo.split()[:6])
    except Exception:
        return " ".join(titulo_crudo.split()[:6])


def es_producto_intimo_permitido(texto: str) -> bool:
    t = texto.lower()
    return any(p in t for p in PALABRAS_INTIMAS_PERMITIDAS)


def es_contenido_adulto(texto: str) -> bool:
    t = texto.lower()
    if any(ok in t for ok in LISTA_BLANCA_FALSOS_POSITIVOS):
        return False
    return any(re.search(rf"\b{re.escape(p)}\b", t) for p in PALABRAS_EXPLICITAS_PROHIBIDAS)


def es_accesorio_basura(titulo: str, p_of: float) -> bool:
    t = titulo.lower()
    if p_of > 0 and p_of < 35:
        return True
    if p_of > 0 and p_of < 150:
        basura_barata = ("funda para", "carcasa para", "mica de cristal", "protector de pantalla", "cable usb", "cable tipo c", "cable lightning")
        if any(b in t for b in basura_barata):
            return True
    return False


def extraer_url_tienda(mensaje: str) -> tuple[str, str]:
    urls = re.findall(r"https?://[^\s<>\"']+", mensaje)
    for u in urls:
        u_clean = u.rstrip(".,;:!?)")
        u_low = u_clean.lower()
        if any(p in u_low for p in ("bandidoofertas", AMZ_TAG.lower(), ML_WORD.lower())):
            continue
        if any(dom in u_low for dom in ("amazon.com.mx", "amzn.to", "a.co/")):
            return ("amazon", u_clean)
        if any(dom in u_low for dom in ("mercadolibre.com.mx", "articulo.mercadolibre.com.mx", "meli.la/")):
            return ("mercadolibre", u_clean)
        if "walmart.com.mx" in u_low:
            return ("walmart", u_clean)
        if "bodegaaurrera.com.mx" in u_low:
            return ("aurrera", u_clean)
    return ("", "")


def evaluar_mensaje_omega(mensaje: str) -> tuple[bool, str]:
    if not PROTOCOLO_OMEGA_ACTIVO:
        return False, ""
    m = mensaje.lower()
    urls = re.findall(r"(https?://\S+|www\.\S+|\bt\.me/\S+)", m)
    for u in urls:
        if not any(ok in u for ok in (
            "amazon.com.mx", "amzn.to", "a.co/",
            "mercadolibre.com", "meli.la",
            "walmart.com.mx", "bodegaaurrera.com.mx",
            "bandidoofertas.com"
        )):
            return True, "link_externo_sospechoso"

    if any(re.search(rf"\b{re.escape(p)}\b", m) for p in TEMAS_SEXUALES_CHAT):
        return True, "contenido_sexual_sugerente"

    return False, ""


def es_mensaje_chat_inapropiado(mensaje: str) -> bool:
    if not PROTOCOLO_OMEGA_ACTIVO:
        return False
    es_omega, _ = evaluar_mensaje_omega(mensaje)
    return es_omega


def generar_advertencia_omega(mensaje_usuario: str, oferta: dict | None = None) -> str:
    titulo = oferta.get("titulo", "") if oferta else ""
    corto = limpiar_titulo_seo(titulo) if titulo else "la oferta del post"
    try:
        resp = _llamar_ollama(
            MODELO_VENDEDOR,
            SYSTEM_PROTOCOLO_OMEGA,
            f"Mensaje inapropiado del usuario: '{mensaje_usuario}'\nOferta real del post: '{corto}'\nEscribe la respuesta de advertencia incómoda:",
            temp=0.75,
            num_predict=110
        )
        if resp and len(resp) > 15 and "lo siento" not in resp.lower():
            return " ".join(resp.split())
    except Exception:
        pass
    return (
        f"Vaya, no me esperaba eso... te recuerdo que por muy encantador que sea, solo soy un mapache 🦝. "
        f"Mejor tómate en serio la oferta de {corto}, porque de verdad es buena."
    )


def link_ml_respaldo_chat(url: str) -> str:
    m_corto = re.search(r"(https?://meli\.la/[A-Za-z0-9]{6,8})", url)
    if m_corto:
        return m_corto.group(1)
    limpia = url.split("#")[0].split("?")[0]
    limpia = re.sub(r"(MLM-?\d+).*$", r"\1", limpia)
    if not limpia.startswith("http"):
        limpia = f"https://www.mercadolibre.com.mx{limpia}"
    return f"{limpia}?matt_word={ML_WORD}&matt_tool={ML_TOOL}&forceInApp=true"


async def _inspeccionar_con_navegador(tienda: str, url_usuario: str) -> dict:
    mapa_perfiles = {
        "amazon": Path(PROF_AMZ),
        "mercadolibre": Path(PROF_ML),
        "walmart": PROF_WALMART,
        "aurrera": PROF_AURRERA
    }
    perfil_usar = mapa_perfiles.get(tienda, Path(PROF_ML))
    perfil_usar.mkdir(parents=True, exist_ok=True)
    resultado = {"titulo": "", "p_of": "", "p_or": "", "url_final": url_usuario, "url_afiliado": ""}

    async with adquirir_perfil_navegador(perfil_usar, origen="chat"):
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(perfil_usar),
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--window-position=-32000,-32000"],
                viewport={"width": 1366, "height": 900},
                locale="es-MX",
                timezone_id="America/Mexico_City"
            )
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            try:
                await page.goto(url_usuario, timeout=40000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4500)
                await page.mouse.wheel(0, 350)
                await page.wait_for_timeout(1200)
                resultado["url_final"] = page.url.split("#")[0].split("?")[0]

                if tienda == "amazon":
                    datos = await page.evaluate("""() => {
                        const titulo = (document.querySelector('#productTitle')?.innerText || '').trim();
                        const pOf = (
                            document.querySelector('#corePriceDisplay_desktop_feature_div .a-price .a-offscreen') ||
                            document.querySelector('#corePrice_feature_div .a-price .a-offscreen') ||
                            document.querySelector('.a-price .a-offscreen')
                        )?.innerText.trim() || '';
                        const pOr = (
                            document.querySelector('#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen') ||
                            document.querySelector('#corePriceDisplay_desktop_feature_div .a-text-price .a-offscreen') ||
                            document.querySelector('.basisPrice .a-offscreen') ||
                            document.querySelector('.a-text-price .a-offscreen')
                        )?.innerText.trim() || '';
                        return { titulo, pOf, pOr };
                    }""")
                    resultado["titulo"] = datos.get("titulo", "")
                    resultado["p_of"] = datos.get("pOf", "")
                    resultado["p_or"] = datos.get("pOr", "")
                    m_asin = re.search(r"/dp/([A-Z0-9]{10})", page.url)
                    if m_asin:
                        resultado["url_afiliado"] = f"https://www.amazon.com.mx/dp/{m_asin.group(1)}?tag={AMZ_TAG}"

                elif tienda == "mercadolibre":
                    datos = await page.evaluate("""() => {
                        const titulo = (document.querySelector('h1.ui-pdp-title')?.innerText || '').trim();
                        const pOf = (
                            document.querySelector('.ui-pdp-price__second-line .andes-money-amount__fraction') ||
                            document.querySelector('.andes-money-amount__fraction')
                        )?.innerText.trim() || '';
                        const pOr = (
                            document.querySelector('.ui-pdp-price__original-value .andes-money-amount__fraction') ||
                            document.querySelector('s .andes-money-amount__fraction')
                        )?.innerText.trim() || '';
                        return { titulo, pOf, pOr };
                    }""")
                    resultado["titulo"] = datos.get("titulo", "")
                    resultado["p_of"] = datos.get("pOf", "")
                    resultado["p_or"] = datos.get("pOr", "")

                    url_af = None
                    for sel in ['button:has-text("Compartir")', 'button:has-text("Obtener enlace")', '.ui-pdp-share button']:
                        btn = page.locator(sel).first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            await page.wait_for_timeout(1800)
                            url_af = await page.evaluate("""() => {
                                for (const inp of document.querySelectorAll('input, textarea')) {
                                    if (inp.value && inp.value.includes('meli.la/')) return inp.value.trim();
                                }
                                const m = document.body.innerText.match(/https:\/\/meli\.la\/[A-Za-z0-9]+/);
                                return m ? m[0] : null;
                            }""")
                            break
                    resultado["url_afiliado"] = url_af if (url_af and "meli.la/" in url_af) else link_ml_respaldo_chat(resultado["url_final"])

                else:
                    datos = await page.evaluate("""() => {
                        const titulo = (document.querySelector('h1[itemprop="name"], h1')?.innerText || '').trim();
                        const precios = [...(document.body.innerText || '').matchAll(/\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)/g)].map(m => m[1]);
                        return {
                            titulo,
                            pOf: precios[0] || '',
                            pOr: precios.length > 1 ? precios[1] : ''
                        };
                    }""")
                    resultado["titulo"] = datos.get("titulo", "")
                    resultado["p_of"] = datos.get("pOf", "")
                    resultado["p_or"] = datos.get("pOr", "")
                    resultado["url_afiliado"] = f"{resultado['url_final']}?utm_source=bandidoofertas&utm_medium=affiliate"
            except Exception as e:
                print(f"⚠️ [AUDITOR LINK NAV ERROR]: {e}")
            finally:
                await ctx.close()

    return resultado


def _generar_comentario_auditoria_coqueto(corto: str, tienda_label: str, p_of_num: float, pct: int, es_humo: bool, motivo: str) -> str:
    if es_humo:
        user_p = (
            f"Producto auditado: {corto} en {tienda_label}. "
            f"Situación: El precio (${p_of_num:,.0f}) resultó puro humo ({motivo}). "
            "Dile con picardía de caballero bandido que lo revisaste con lupa para proteger su cartera y mejor se deje consentir con las joyas reales de tu guarida."
        )
    else:
        user_p = (
            f"Producto auditado: {corto} en {tienda_label}. "
            f"Situación: Pasó la prueba antihumo con -{pct}% real (${p_of_num:,.0f}). "
            "Halaga su buen ojo clínico y dile con tu encanto de ladrón de guante blanco que ya le sacaste el pase directo antes de que cambien el precio."
        )
    try:
        txt = _llamar_ollama(MODELO_VENDEDOR, SYSTEM_BANDIDO_CHAT, user_p, temp=0.84, num_predict=125)
        if len(txt) > 20 and "lo siento" not in txt.lower() and "no puedo" not in txt.lower():
            return " ".join(txt.split())
    except Exception:
        pass

    if es_humo:
        return (
            f"🦝🚨 ¡Alto ahí, cómplice! Revisé ese {corto} (${p_of_num:,.0f}) con lupa para cuidar tu cartera y resultó puro humo ({motivo}). "
            f"No caigas en su trampa cuando yo te tengo joyas reales 😏✨"
        )
    return (
        f"🦝💎 ¡Qué ojo clínico tienes, cómplice! Auditado y aprobado: ese {corto} sí trae -{pct}% real en ${p_of_num:,.0f} MXN. "
        f"Yo pongo el antifaz y tú te llevas el botín antes de que cambien el precio 😏🔥"
    )


def auditar_enlace_usuario(tienda: str, url_usuario: str) -> str:
    try:
        datos = asyncio.run(_inspeccionar_con_navegador(tienda, url_usuario))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        datos = loop.run_until_complete(_inspeccionar_con_navegador(tienda, url_usuario))
        loop.close()

    nombres_tienda = {
        "amazon": "Amazon México",
        "mercadolibre": "Mercado Libre México",
        "walmart": "Walmart México",
        "aurrera": "Bodega Aurrera"
    }
    tienda_label = nombres_tienda.get(tienda, "la tienda")
    titulo = datos.get("titulo", "")
    corto = limpiar_titulo_seo(titulo) if titulo else "ese botín"
    p_of_num = limpiar_monto(datos.get("p_of", ""))
    p_or_num = limpiar_monto(datos.get("p_or", ""))
    if p_or_num > 0 and p_or_num < p_of_num:
        p_of_num, p_or_num = p_or_num, p_of_num

    url_final = datos.get("url_final") or url_usuario

    if p_of_num <= 0:
        if tienda == "mercadolibre":
            link_af = datos.get("url_afiliado") or link_ml_respaldo_chat(url_final)
            return (
                f"🦝✨ Me colé en Mercado Libre para rescatarte ese {corto} y ya te saqué el pase directo "
                f"antes de que nadie más lo vea 👉 {link_af}"
            )
        return (
            f"🦝🔍 Me colé en {tienda_label} por ese {corto}, pero ahorita tienen el precio escondido o sin stock. "
            f"Pásate a mi guarida donde sí tengo gangas auditadas listas: {WORKER_URL} 🌙✨"
        )

    nums = auditar_numeros({
        "precio_oferta": p_of_num,
        "precio_original": p_or_num,
        "descuento": ""
    })
    hist = verificar_historial(url_final, p_of_num, tienda_label)
    es_humo = nums["anomalia"] or hist["es_humo"] or nums["pct_real"] < 15
    link_af = datos.get("url_afiliado") or (link_ml_respaldo_chat(url_final) if tienda == "mercadolibre" else url_final)
    motivo = hist["nota"] or nums["motivo"] or f"apenas trae {nums['pct_real']}% de descuento real"

    cuerpo_coqueto = _generar_comentario_auditoria_coqueto(
        corto, tienda_label, p_of_num, nums["pct_real"], es_humo, motivo
    )

    if es_humo:
        return (
            f"{cuerpo_coqueto} — Igual te dejo el enlace por si te gana el antojo: {link_af} "
            f"(o caza ofertas reales en {WORKER_URL} 🦝)"
        )

    return f"{cuerpo_coqueto} — 🦝 Pase directo a {tienda_label}: {link_af}"


def detectar_genero_ropa(titulo: str) -> str:
    t = titulo.lower()
    mujer_kw = ("mujer", "dama", "damas", "femenino", "ella", "blusa", "vestido", "falda", "leggings", "bolsa de mano", "tacones")
    hombre_kw = ("hombre", "caballero", "caballeros", "masculino", "herren", "varonil")
    if any(re.search(rf"\b{re.escape(w)}\b", t) for w in mujer_kw):
        return "ROP-M"
    if any(re.search(rf"\b{re.escape(w)}\b", t) for w in hombre_kw):
        return "ROP-H"
    return "ROP-U"


def detectar_categoria_segura(titulo: str, cat_ollama: str = "") -> str:
    t = titulo.lower()
    for cod, palabras in CATEGORIAS_EXACTAS:
        if any(re.search(rf"\b{re.escape(p)}\b", t) if len(p) <= 4 else (p in t) for p in palabras):
            if cod == "ROP":
                return detectar_genero_ropa(titulo)
            return cod
    if cat_ollama and cat_ollama in CODIGOS_CAT_VALIDOS:
        if cat_ollama == "ROP":
            return detectar_genero_ropa(titulo)
        return cat_ollama
    return "HOG"


def ajustar_score_real(titulo: str, subcat: str, pct: int, nota_hist: str, p_of: float, p_or: float) -> int:
    t = titulo.lower()
    cat_base = subcat.split("-")[0]
    es_minimo = "mínimo histórico" in nota_hist.lower()
    es_tendencia = any(kw in t for kw in PALABRAS_TENDENCIA_TIER0)

    cats_estrella = {"TEC", "AUD", "VID", "CEL", "COM", "HOG"}
    if es_tendencia and pct >= 35 and p_of >= 350:
        return 0
    if cat_base in cats_estrella and pct >= 55 and p_of >= 450:
        return 0

    if p_or <= p_of and pct == 0:
        return 4
    if pct >= 45 or (pct >= 35 and es_minimo):
        return 1
    if pct >= 30:
        return 2
    if pct >= 18:
        return 3
    if pct >= 10:
        return 4
    return 5


def respaldo_coqueto(titulo: str, subcat: str) -> str:
    corto = limpiar_titulo_seo(titulo)
    remate = elegir_remate_respaldo()
    cat_base = subcat.split("-")[0]
    plantillas = {
        "VID": f"🎮 Me robé este {corto} para armar la reta nocturna contigo 😏 {remate}",
        "AUD": f"🎧 Me colé a la bodega por este {corto} con descuentazo real 😉 {remate}",
        "HOG": f"🏠 Mira qué joya acabo de extraer para consentirte y compartir aventuras: {corto} 😏 {remate}",
        "CEL": f"📱 Rescaté este {corto} burlando las etiquetas infladas de la tienda 😉 {remate}",
        "COM": f"💻 Qué botín acabo de sacar: {corto} auditado y sin humo 🔥 {remate}",
        "TEC": f"🛸 Me jugué el antifaz por esta joya: {corto} 😏 {remate}",
        "ROP": f"👟 Rescaté este {corto} con estilo para nuestra próxima salida 😉 {remate}",
        "PER": f"✨ Para consentirte como mereces, me robé este {corto} 😏 {remate}",
        "TMP": f"🎄 Joya de temporada rescatada a tiempo: {corto} ✨ {remate}",
        "HER": f"🛠️ Botín pesado para manos expertas: {corto} a precio de atraco 🔥 {remate}"
    }
    return plantillas.get(cat_base, f"💎 Nadie más vio este {corto} escondido con este descuentazo 😏 {remate}")


def _extraer_json(texto: str) -> dict:
    try:
        return json.loads(texto)
    except Exception:
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


def seducir_post_fb(titulo: str, tienda: str = "", subcat: str = "HOG", pct: int = 0) -> str:
    objeto_limpio = limpiar_titulo_seo(titulo)
    es_intimo = es_producto_intimo_permitido(f"{titulo} {objeto_limpio}")
    sys_prompt = SYSTEM_BANDIDO_POST_FB_INTIMO if es_intimo else SYSTEM_BANDIDO_POST_FB
    user_prompt = (
        f"Producto: {objeto_limpio}\n"
        "Escribe 1 o 2 frases cortas con el encanto pícaro, teatral y coqueto de Bandido (español de México, con 2 o 3 emojis):"
    )
    try:
        txt = _llamar_ollama(MODELO_VENDEDOR, sys_prompt, user_prompt, temp=0.84, num_predict=100)
        if (
            txt
            and len(txt) > 15
            and "lo siento" not in txt.lower()
            and "no puedo" not in txt.lower()
            and "precio validado" not in txt.lower()
        ):
            return " ".join(txt.split())[:195]
    except Exception:
        pass
    return respaldo_coqueto(titulo, subcat)


def seducir_tarjeta(titulo: str, tienda: str = "", subcat: str = "HOG", pct: int = 0) -> str:
    objeto_limpio = limpiar_titulo_seo(titulo)
    es_intimo = es_producto_intimo_permitido(f"{titulo} {objeto_limpio}")
    system_prompt = SYSTEM_BANDIDO_INTIMO if es_intimo else SYSTEM_BANDIDO_WEB

    user_prompt = (
        f"Producto: {objeto_limpio}\n"
        "Escribe el comentario de Bandido imitando la chispa teatral, coqueta y juguetona de los ejemplos (1 párrafo corto en español de México, sin saltos de línea):"
    )
    try:
        txt = _llamar_ollama(MODELO_VENDEDOR, system_prompt, user_prompt, temp=0.82, num_predict=115)
        if (
            len(txt) > 25
            and "precio validado" not in txt.lower()
            and "lo siento" not in txt.lower()
            and "no puedo" not in txt.lower()
        ):
            return " ".join(txt.split())
    except Exception as e:
        print(f"⚠️ [OLLAMA SEDUCIR TARJETA]: {e}")

    return respaldo_coqueto(titulo, subcat)


def auditar(oferta_bruta: dict) -> dict:
    titulo = oferta_bruta.get("titulo", "")
    url_norm = oferta_bruta.get("url_normal", "")

    if es_contenido_adulto(f"{titulo} {url_norm}"):
        return {
            "descartar": True,
            "motivo_borrado": "contenido_adulto",
            "score": 5,
            "subcategoria": "PER",
            "razonamiento": "Descartada por filtro explícito +18 / ecchi.",
            "copy_web": "",
            "numeros": {"precio_oferta": 0, "precio_original": 0, "pct_real": 0, "anomalia": True}
        }

    nums = auditar_numeros(oferta_bruta)
    if nums["anomalia"]:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": "HOG",
            "razonamiento": nums["motivo"],
            "copy_web": "",
            "numeros": nums
        }

    p_of = nums["precio_oferta"]
    p_or = nums["precio_original"]
    pct = nums["pct_real"]

    if es_accesorio_basura(titulo, p_of):
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": "CEL",
            "razonamiento": "Accesorio genérico de bajo valor descartado.",
            "copy_web": "",
            "numeros": nums
        }

    tienda = oferta_bruta.get("tienda", "")
    hist = verificar_historial(url_norm, p_of, tienda)
    if hist["es_humo"]:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": "HOG",
            "razonamiento": hist["nota"],
            "copy_web": "",
            "numeros": nums
        }

    cat_ollama = ""
    descartar_ia = False
    razon_ia = ""

    prompt_auditor = (
        "Eres un auditor estricto de ofertas en México. Responde SOLO con un JSON válido:\n"
        '{"descartar": false, "subcategoria": "TEC", "razon": "motivo breve"}\n'
        "Códigos permitidos: TMP (Temporada/Juguetes), VID (Videojuegos), AUD (Audio/Instrumentos), "
        "CEL (Celulares/Tablets), COM (Computación), TEC (Tecnología/TV/Drones), HOG (Hogar/Cocina/Tuppers), "
        "ROP (Ropa/Calzado/Maletas/Deporte), PER (Uso Personal/Salud/Preservativos), HER (Herramientas/Auto).\n"
        "Descarta (descartar: true) si es sex shop, contenido +18, manga/novela visual erótica o ecchi, libro sugestionante para adultos, o cable/funda barata.\n"
        f"Producto: {titulo}\nTienda: {tienda}\nPrecio oferta: ${p_of} | Original:${p_or} | Descuento: {pct}%"
    )
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_AUDITOR,
                "prompt": prompt_auditor,
                "stream": False,
                "options": {"temperature": 0.15, "num_predict": 110}
            },
            timeout=35
        )
        if r.status_code == 200:
            data_ia = _extraer_json(r.json().get("response", ""))
            if data_ia:
                descartar_ia = bool(data_ia.get("descartar", False))
                cat_ollama = str(data_ia.get("subcategoria", "")).upper().strip()
                razon_ia = limpiar_prohibidas(str(data_ia.get("razon", "")))
    except Exception:
        pass

    subcat = detectar_categoria_segura(titulo, cat_ollama)
    score = ajustar_score_real(titulo, subcat, pct, hist["nota"], p_of, p_or)

    if descartar_ia:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": subcat,
            "razonamiento": razon_ia or "Descartada por auditoría.",
            "copy_web": "",
            "numeros": nums
        }

    if score == 5:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": subcat,
            "razonamiento": f"Descuento bajo ({pct}%), filtrada por antihumo.",
            "copy_web": "",
            "numeros": nums
        }

    copy_web = seducir_tarjeta(titulo, tienda, subcat, pct)

    return {
        "descartar": False,
        "score": score,
        "subcategoria": subcat,
        "razonamiento": hist["nota"],
        "copy_web": copy_web,
        "numeros": nums
    }


def _oferta_coincide_con_pedido(mensaje_usuario: str, oferta: dict) -> bool:
    stopwords = {
        "como", "cómo", "puedo", "comprar", "cuanto", "cuánto", "cuesta", "precio", "tiene",
        "tarjeta", "banco", "info", "informacion", "información", "link", "enlace", "quiero",
        "para", "este", "esta", "enviar", "mensaje", "interesa", "esa", "ese", "tal", "hay",
        "tienes", "disponible", "busco", "buscando", "favor", "por", "los", "las", "del", "una",
        "uno", "unos", "unas", "edicion", "edición", "con", "sin", "que", "qué", "pasa", "dame",
        "especial", "busca", "donde", "dónde"
    }
    limpio = re.sub(r"[^\w\sáéíóúñ]", " ", mensaje_usuario.lower())
    palabras = [p for p in limpio.split() if len(p) > 2 and p not in stopwords]
    if not palabras:
        return True
    tit = str(oferta.get("titulo", "")).lower()
    return any(re.search(rf"\b{re.escape(p)}\b", tit) for p in palabras)


def _usuario_pidio_precio_o_descuento(mensaje: str) -> tuple[bool, bool]:
    m = mensaje.lower()
    kw_precio = (
        "precio", "cuanto", "cuánto", "cuesta", "vale", "descuento", "rebaja",
        "porcentaje", "%", "pesos", "mxn", "barato", "sale en", "queda en", "total"
    )
    pidio_tarjeta = bool(detectar_banco(m)) or any(
        w in m for w in ("tarjeta", "meses", "msi", "bonificacion", "bonificación", "banco", "cupon", "cupón")
    )
    pidio_precio = any(w in m for w in kw_precio) or pidio_tarjeta
    return pidio_precio, pidio_tarjeta


def vender(
    mensaje_usuario: str,
    oferta: dict | None,
    es_alternativa_d1: bool = False,
    es_replica_hilo: bool = False,
    contexto_padre: str = ""
) -> str:
    tienda_link, url_usuario = extraer_url_tienda(mensaje_usuario)
    if tienda_link and url_usuario:
        return " ".join(auditar_enlace_usuario(tienda_link, url_usuario).split())

    if PROTOCOLO_OMEGA_ACTIVO and es_mensaje_chat_inapropiado(mensaje_usuario):
        return generar_advertencia_omega(mensaje_usuario, oferta)

    # Validar coincidencia usando el mensaje o el contexto padre si es una réplica dentro de un hilo
    texto_validacion = f"{mensaje_usuario} {contexto_padre}".strip() if es_replica_hilo else mensaje_usuario
    if oferta and not _oferta_coincide_con_pedido(texto_validacion, oferta):
        oferta = None

    if not oferta:
        return (
            f"🦝💔 Ese botín específico no lo tengo ahorita en mi guarida (o esa oferta ya voló), "
            f"pero pásate por mi web en vivo donde subo gangas auditadas cada 15 minutos: {WORKER_URL} 🌙✨"
        )

    link = str(oferta.get("url_afiliado") or WORKER_URL).strip()
    titulo = oferta.get("titulo", "esta joya")
    corto = limpiar_titulo_seo(titulo)
    tienda_raw = str(oferta.get("tienda", "")).lower()
    if "amazon" in tienda_raw or "amzn" in link.lower():
        tienda_nombre = "Amazon México"
    elif "walmart" in tienda_raw:
        tienda_nombre = "Walmart México"
    elif "aurrera" in tienda_raw:
        tienda_nombre = "Bodega Aurrera"
    else:
        tienda_nombre = "Mercado Libre"
    subcat = oferta.get("subcategoria") or detectar_categoria_segura(titulo)

    pidio_precio, pidio_tarjeta = _usuario_pidio_precio_o_descuento(mensaje_usuario)

    dato_precio = ""
    if pidio_precio:
        nums = auditar_numeros(oferta)
        p_of = nums["precio_oferta"]
        pct = nums["pct_real"]
        if p_of > 0:
            dato_precio = f"💰 ${p_of:,.0f} MXN" + (f" (-{pct}% real)" if pct > 0 else "")

    dato_banco = ""
    if pidio_tarjeta:
        calc = calcular_tarjeta(oferta, mensaje_usuario)
        if calc["tiene_banco"]:
            dato_banco = f" | 💳 {calc['detalle']}"

    intro_alt = (
        "Ese del post ya voló, pero me escabullí en mi catálogo web y rescaté esta joya parecida: "
        if es_alternativa_d1
        else ""
    )

    if es_replica_hilo:
        sys_prompt = SYSTEM_BANDIDO_CHAT_HILO
        user_prompt = (
            f"Producto del hilo: {corto}\n"
            f"Comentario original del primer usuario: {contexto_padre}\n"
            f"Réplica que le dejó este usuario: {mensaje_usuario}\n"
            "Responde con picardía coqueta siguiendo el juego (ej. pídele que lo convenza de comprarlo y dile que se lo recompensas después 😘, sin precios ni saltos de línea):"
        )
    else:
        sys_prompt = SYSTEM_BANDIDO_CHAT
        user_prompt = (
            f"Producto: {corto}\n"
            f"Comentario del usuario: {mensaje_usuario}\n"
            "Escribe tu réplica coqueta, pícara y encantadora (coquetea con total seguridad sin importar quién comente, intercala 2 o 3 emojis, NO pongas precios ni descuentos ni saltos de línea):"
        )

    frase_coqueta = ""
    try:
        txt = _llamar_ollama(MODELO_VENDEDOR, sys_prompt, user_prompt, temp=0.86, num_predict=110)
        txt = " ".join(txt.split()).rstrip(".")
        if (
            len(txt) > 18
            and "hola, amigo" not in txt.lower()
            and "hola amigo" not in txt.lower()
            and "lo siento" not in txt.lower()
            and "no puedo" not in txt.lower()
        ):
            frase_coqueta = txt
    except Exception as e:
        print(f"⚠️ [OLLAMA VENDEDOR ERROR]: {e}")

    if not frase_coqueta:
        if es_replica_hilo:
            frase_coqueta = f"Pues tú convéncelo de que se lleve este {corto} y yo te lo recompenso después 😘😏"
        else:
            frase_coqueta = respaldo_coqueto(titulo, subcat)

    if not pidio_precio:
        frase_coqueta = re.sub(r"\$\s*[0-9,.]+(?:\s*MXN)?", "", frase_coqueta, flags=re.IGNORECASE)
        frase_coqueta = re.sub(r"-?\d{1,2}\s*%", "", frase_coqueta)
        frase_coqueta = " ".join(frase_coqueta.split())

    partes = [f"{intro_alt}{frase_coqueta}".strip()]
    if dato_precio or dato_banco:
        partes.append(f"{dato_precio}{dato_banco}".strip())
    partes.append(f"🦝 Pase directo en {tienda_nombre}: {link}")

    return " — ".join(p for p in partes if p)