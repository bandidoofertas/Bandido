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
from calc import auditar_numeros, calcular_tarjeta, limpiar_monto
from hist import verificar_historial
from browser_queue import adquirir_perfil_navegador

BASE_DIR = Path(__file__).resolve().parent
PROF_WALMART = BASE_DIR / "prof_walmart"
PROF_AURRERA = BASE_DIR / "prof_aurrera"

_ULTIMOS_REMATES = deque(maxlen=12)

CODIGOS_CAT_VALIDOS = {
    "TMP", "VID", "AUD", "CEL", "COM", "TEC", "HOG", "ROP", "ROP-M", "ROP-H", "ROP-U", "PER", "HER"
}

REMATES_RESPALDO = [
    "córrele antes de que otro cómplice se nos adelante 😏💎👉",
    "guardemos este secreto entre tú y yo antes de que suba de precio 🤫✨👉",
    "yo ya hice el robo perfecto, ahora te toca caer en la tentación 😉🔥👉",
    "te lo dejé servido en bandeja de plata antes de que cambien la etiqueta 🌙👉",
    "qué peligro tú y yo juntos con este botín... aprovéchalo antes de que vuele 🦝✨👉",
    "ya te conseguí el descuento real, ahora ven por tu recompensa 😏👉"
]

EJEMPLOS_PROMPT_COQUETO = [
    "'Con ese ojo clínico me vas a terminar robando el antifaz tú a mí... me colé a la bodega y rescaté este botín antes de que corrigieran el precio 😏🦝'",
    "'Sé que dijiste que este mes no ibas a gastar, pero lo dejé servido en bandeja de plata... ¿quién soy yo para juzgar tus debilidades? 😉✨'",
    "'Me jugué el pellejo burlando las etiquetas infladas de la tienda solo para traerte esta joya. Tú no viste nada, yo no estuve aquí 🦝🕶️'",
    "'Iban a cobrarte precio lleno, pero intervine a tiempo como todo un caballero nocturno. Dime si nos llevamos este botín antes de que amanezca 🌙💎'"
]

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
        "fc 25", "fc 26", "fifa", "call of duty", "resident evil", "elden ring", "silla gamer",
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
        "escritorio", "comedor", "lavadora", "secadora", "refrigerador", "refri", "estufa",
        "parrilla", "campana extractora", "plancha", "vaporizador", "dispensador de agua",
        "filtro de agua", "rotoplas", "detergente", "suavizante"
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
    "rog ally", "zelda", "pokemon", "pokémon", "iphone", "galaxy s24", "galaxy s25",
    "ipad", "macbook", "rtx 40", "rtx 50", "ryzen 7", "ryzen 9", "airpods",
    "sony wh-1000xm", "bose quietcomfort", "dyson", "ninja creami", "stanley",
    "kindle", "starlink", "dji", "gopro", "lego", "fender", "yamaha"
]

PALABRAS_EXPLICITAS_PROHIBIDAS = [
    # Sex shop / explícito
    "lubricante intimo", "lubricante íntimo", "vibrador", "dildo", "consolador",
    "masturbador", "sex shop", "sexshop", "erotico", "erótico", "erotica", "erótica",
    "lenceria sexy", "lencería sexy", "fetiche", "bdsm", "esposas eroticas",
    "retardante sexual", "potenciador sexual", "viagra", "sildenafil",
    "juguete sexual", "juguetes sexuales", "solo adultos",
    # Manga / Novelas visuales / Libros +18 o ecchi
    "monster girl", "renai sample", "homunculus", "hentai", "ecchi",
    "doujinshi", "waifu", "harem", "novela visual", "visual novel",
    "manga adultos", "comic adultos", "cómic adultos", "nsfw", "18+", "+18",
    "fakku", "denpa", "j18", "seven seas ghost ship", "ghost ship"
]

LISTA_BLANCA_FALSOS_POSITIVOS = [
    "cafetera", "prensa francesa", "french press", "aceite de oliva", "crema batida", "masajeador muscular"
]

MENSAJE_MODERACION_CHAT = (
    "Tranquilo, solo soy un mapache 🦝. Yo solo cazo descuentos reales y seguros para todos; "
    "no abro enlaces externos ni respondo ni sigo ese tipo de temas."
)


def elegir_remate_respaldo() -> str:
    disponibles = [f for f in REMATES_RESPALDO if f not in _ULTIMOS_REMATES] or REMATES_RESPALDO
    elegido = random.choice(disponibles)
    _ULTIMOS_REMATES.append(elegido)
    return elegido


def limpiar_prohibidas(texto: str) -> str:
    for mal, bien in [("chollos", "gangas"), ("chollo", "ganga"), ("Chollos", "Gangas"), ("Chollo", "Ganga")]:
        texto = texto.replace(mal, bien)
    return texto


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
        if any(p in u_low for p in ("meli.la", "matt_word=", "bandidoofertas", "fbclid=", "tag=")):
            continue
        if any(dom in u_low for dom in ("amazon.com.mx", "amzn.to", "a.co/")):
            return ("amazon", u_clean)
        if any(dom in u_low for dom in ("mercadolibre.com.mx", "articulo.mercadolibre.com.mx")):
            return ("mercadolibre", u_clean)
        if "walmart.com.mx" in u_low:
            return ("walmart", u_clean)
        if "bodegaaurrera.com.mx" in u_low:
            return ("aurrera", u_clean)
    return ("", "")


def es_mensaje_chat_inapropiado(mensaje: str) -> bool:
    m = mensaje.lower()
    urls = re.findall(r"(https?://\S+|www\.\S+|\bt\.me/\S+)", m)
    for u in urls:
        if not any(ok in u for ok in (
            "amazon.com.mx", "amzn.to", "a.co/",
            "mercadolibre.com", "meli.la",
            "walmart.com.mx", "bodegaaurrera.com.mx",
            "bandidoofertas.com"
        )):
            return True

    temas_sexuales = [
        "sexo", "sexual", "porno", "pornografia", "pornografía", "xxx", "nudes", "pack",
        "desnuda", "desnudo", "coger", "cojer", "follar", "caliente", "cachondo", "cachonda",
        "orgasmo", "masturbar", "pene", "vagina", "chichis", "nalgas", "erotico", "erótico",
        "vibrador", "dildo"
    ]
    return any(re.search(rf"\b{re.escape(p)}\b", m) for p in temas_sexuales)


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
                                const m = document.body.innerText.match(/https:\\/\\/meli\\.la\\/[A-Za-z0-9]+/);
                                return m ? m[0] : null;
                            }""")
                            break
                    resultado["url_afiliado"] = url_af if (url_af and "meli.la/" in url_af) else link_ml_respaldo_chat(resultado["url_final"])

                else:
                    datos = await page.evaluate("""() => {
                        const titulo = (document.querySelector('h1[itemprop="name"], h1')?.innerText || '').trim();
                        const precios = [...(document.body.innerText || '').matchAll(/\\$\\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\\.[0-9]{2})?)/g)].map(m => m[1]);
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
    ejemplo_dinamico = random.choice(EJEMPLOS_PROMPT_COQUETO)
    if es_humo:
        prompt = (
            "Eres Bandido, un mapache ladrón nocturno caballeroso, pícaro, galán y encantador en México 🦝🌙.\n"
            f"Un usuario te pidió auditar '{corto}' en {tienda_label} (${p_of_num:,.0f} MXN), "
            f"pero tu filtro antihumo detectó que NO conviene porque {motivo}.\n"
            "Escribe una respuesta corta, juguetona y encantadora (25 a 38 palabras): dile con picardía de galán bandido "
            "que lo revisaste con lupa para proteger su cartera, que ese precio es puro humo y mejor se deje consentir "
            "con las joyas reales de tu guarida.\n"
            "REGLAS: menciona el producto y el precio, usa 2 emojis, PROHIBIDO decir 'chollo' o 'chollos', NO uses lenguaje íntimo/sexual ni pongas links."
        )
    else:
        prompt = (
            "Eres Bandido, un mapache ladrón nocturno caballeroso, pícaro, galán y encantador en México 🦝🌙.\n"
            f"Un usuario te pidió auditar '{corto}' en {tienda_label} (${p_of_num:,.0f} MXN, -{pct}% de descuento real) "
            "y SÍ pasó tu filtro antihumo.\n"
            "Escribe una respuesta corta, juguetona, encantadora y muy vendedora (25 a 38 palabras): halaga su buen ojo clínico, "
            f"presume el -{pct}% real y el precio de ${p_of_num:,.0f} MXN con tu estilo teatral de ladrón de guante blanco "
            f"(inspírate en este tono: {ejemplo_dinamico}).\n"
            "REGLAS: menciona el producto, el porcentaje y el precio real, usa 2 emojis, PROHIBIDO decir 'chollo' o 'chollos', NO uses lenguaje íntimo/sexual ni pongas links."
        )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_VENDEDOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.85, "num_predict": 120}
            },
            timeout=60
        )
        if r.status_code == 200:
            txt = limpiar_prohibidas(r.json().get("response", "").strip().strip('"').strip("'"))
            txt = re.sub(r"\s+", " ", txt)
            if len(txt) > 20 and "lo siento" not in txt.lower() and "no puedo" not in txt.lower():
                return txt
    except Exception as e:
        print(f"⚠️ [OLLAMA VENDEDOR AUDITORIA]: {e}")

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
    corto = " ".join(titulo.split()[:6]) if titulo else "ese botín"
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
            f"{cuerpo_coqueto}\n"
            f"Igual te dejo el enlace por si te gana el antojo: {link_af} (o caza ofertas reales en {WORKER_URL} 🦝)"
        )

    return f"{cuerpo_coqueto}\n🦝 Pase directo a {tienda_label}: {link_af}"


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
    corto = " ".join(titulo.split()[:5])
    remate = elegir_remate_respaldo()
    cat_base = subcat.split("-")[0]
    plantillas = {
        "VID": f"🎮 Me robé este {corto} antes de que le suban el precio; {remate}",
        "AUD": f"🎧 Me colé a la bodega por este {corto} con descuentazo real; {remate}",
        "HOG": f"🏠 Mira qué joya acabo de extraer para consentir tu casa: {corto}; {remate}",
        "CEL": f"📱 Rescaté este {corto} burlando las etiquetas infladas de la tienda; {remate}",
        "COM": f"💻 Qué botín acabo de sacar: {corto} auditado y sin humo; {remate}",
        "TEC": f"🛸 Me jugué el antifaz por esta tecnología: {corto}; {remate}",
        "ROP": f"👟 Rescaté este {corto} con estilo y buen descuento; {remate}",
        "PER": f"✨ Para consentirte como mereces, me robé este {corto}; {remate}",
        "TMP": f"🎄 Joya de temporada rescatada a tiempo: {corto}; {remate}",
        "HER": f"🛠️ Botín pesado para manos expertas: {corto} a precio de atraco; {remate}"
    }
    return plantillas.get(cat_base, f"💎 Nadie más vio este {corto} escondido con este descuentazo; {remate}")


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


def seducir_tarjeta(titulo: str, tienda: str, subcat: str, pct: int) -> str:
    ejemplo_dinamico = random.choice(EJEMPLOS_PROMPT_COQUETO)
    info_pct = f" con -{pct}% real" if pct > 0 else ""
    prompt = (
        "Eres Bandido, un mapache ladrón nocturno caballeroso, pícaro, galán y encantador en México 🦝🌙.\n"
        f"Escribe una frase corta, juguetona y encantadora (20 a 32 palabras) sobre ESTE producto{info_pct}.\n"
        f"Usa un tono de ladrón de guante blanco que presume el robo del descuento o halaga el buen gusto del comprador "
        f"(inspírate en: {ejemplo_dinamico}).\n"
        "REGLAS: menciona el producto real, usa 2 emojis, PROHIBIDO decir 'chollo' o 'chollos', "
        "NO uses lenguaje íntimo/sexual ni pongas precios ni links.\n\n"
        f"Producto: {titulo}\nTienda: {tienda}"
    )
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_VENDEDOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.85, "num_predict": 110}
            },
            timeout=60
        )
        if r.status_code == 200:
            txt = limpiar_prohibidas(r.json().get("response", "").strip().strip('"').strip("'"))
            if (
                len(txt) > 18
                and "precio validado" not in txt.lower()
                and "lo siento" not in txt.lower()
                and "no puedo" not in txt.lower()
            ):
                return txt
    except Exception:
        pass
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
        "especial", "busca"
    }
    limpio = re.sub(r"[^\w\sáéíóúñ]", " ", mensaje_usuario.lower())
    palabras = [p for p in limpio.split() if len(p) > 2 and p not in stopwords]
    if not palabras:
        return True
    tit = str(oferta.get("titulo", "")).lower()
    return any(re.search(rf"\b{re.escape(p)}\b", tit) for p in palabras)


def vender(mensaje_usuario: str, oferta: dict | None, es_alternativa_d1: bool = False) -> str:
    tienda_link, url_usuario = extraer_url_tienda(mensaje_usuario)
    if tienda_link and url_usuario:
        return auditar_enlace_usuario(tienda_link, url_usuario)

    if es_mensaje_chat_inapropiado(mensaje_usuario):
        return MENSAJE_MODERACION_CHAT

    if oferta and not _oferta_coincide_con_pedido(mensaje_usuario, oferta):
        oferta = None

    if not oferta:
        return (
            f"🦝💔 Ese botín específico no lo tengo ahorita en mi guarida (o esa oferta ya voló), "
            f"pero pásate por mi web en vivo donde subo gangas auditadas cada 15 minutos: {WORKER_URL} 🌙✨"
        )

    link = oferta.get("url_afiliado") or WORKER_URL
    titulo = oferta.get("titulo", "esta joya")
    corto = " ".join(titulo.split()[:5])
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

    nums = auditar_numeros(oferta)
    p_of = nums["precio_oferta"]
    pct = nums["pct_real"]
    dato_precio = f"💰 ${p_of:,.0f} MXN" + (f" (-{pct}% real)" if pct > 0 else "") if p_of > 0 else ""

    calc = calcular_tarjeta(oferta, mensaje_usuario)
    dato_banco = f" | 💳 {calc['detalle']}" if calc["tiene_banco"] else ""

    intro_alt = (
        "Ese del post ya voló, pero me escabullí en mi catálogo web y rescaté esta joya parecida: "
        if es_alternativa_d1
        else ""
    )

    ejemplo_dinamico = random.choice(EJEMPLOS_PROMPT_COQUETO)
    prompt = (
        "Eres Bandido, un mapache ladrón nocturno caballeroso, pícaro, galán y encantador en México 🦝🌙.\n"
        f"Un usuario comentó sobre este producto: '{corto}'.\n"
        "Escribe una respuesta corta, juguetona, encantadora y muy vendedora (22 a 34 palabras) presumiendo el robo "
        f"de este descuento con humor y picardía teatral (inspírate sin copiar literal en: {ejemplo_dinamico}).\n"
        "REGLAS: menciona el producto real, usa 2 emojis, PROHIBIDO saludar con 'Hola amigo', "
        "PROHIBIDO decir 'chollo' o 'chollos', NO uses lenguaje íntimo/sexual ni pongas precios ni links.\n\n"
        f"Producto: {corto}\nMensaje del usuario: {mensaje_usuario}"
    )

    frase_coqueta = ""
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_VENDEDOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.85, "num_predict": 110}
            },
            timeout=60
        )
        if r.status_code == 200:
            txt = limpiar_prohibidas(r.json().get("response", "").strip().strip('"').strip("'"))
            txt = re.sub(r"\s+", " ", txt)
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
        frase_coqueta = respaldo_coqueto(titulo, subcat)

    bloque_datos = f"\n{dato_precio}{dato_banco}" if (dato_precio or dato_banco) else ""
    return (
        f"{intro_alt}{frase_coqueta}{bloque_datos}\n"
        f"🦝 Pase directo en {tienda_nombre}: {link}"
    )