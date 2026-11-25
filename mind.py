import asyncio
from collections import deque
import json
import random
import re
import requests
from playwright.async_api import async_playwright
from cfg import (
    OLLAMA_URL, MODELO_AUDITOR, MODELO_VENDEDOR, CODIGOS_CAT,
    WORKER_URL, PROF_ML, PROF_AMZ, ML_WORD, ML_TOOL, AMZ_TAG
)
from calc import auditar_numeros, calcular_tarjeta, limpiar_monto
from hist import verificar_historial

_ULTIMOS_REMATES = deque(maxlen=3)

REMATES_COQUETOS = [
    ("morder", "prometo no morder a menos que tú quieras 😏👉"),
    ("convencer", "¿te atreves a atraparlo o tengo que convencerte de otra forma? 😏👉"),
    ("estrenar", "¿lo estrenamos juntos esta noche o te vas a hacer del rogar? 🔥👉"),
    ("bandeja", "te lo dejé servido en bandeja de plata antes de que amanezca 🌙👉"),
    ("portarme", "prometo portarme bien si lo atrapas antes de que vuele 🦝✨👉"),
    ("motivos", "dime si te lo envuelvo para esta madrugada o prefieres que te dé más motivos 😉👉"),
    ("luna", "no digas que no te consentí hoy bajo la luna 🌙🔥👉"),
    ("complice", "córrele antes de que otro cómplice se nos adelante 😏💎👉"),
    ("secreto", "guardemos este secreto entre tú y yo antes de que suba de precio 🤫✨👉"),
    ("escapada", "¿nos escapamos esta noche a estrenarlo o lo vas a dejar ir? 🦝🔥👉")
]

EJEMPLOS_PROMPT_COQUETO = [
    "'Imagínate tú y yo estrenándolo esta noche... prometo no morder a menos que tú quieras 😏🔥'",
    "'Te presumo cómo nos veríamos con él esta madrugada, aunque dudo que te resistas 🌙✨'",
    "'Me escabullí entre las sombras solo para traértelo a ti... dime si nos escapamos a probarlo 😉🔥'",
    "'Qué peligro tú y yo juntos con este botín esta noche, prometo portarme bien 🦝💫'"
]

CATEGORIAS_EXACTAS = [
    ("B1", ["juego", "juegos", "videojuego", "videojuegos", "switch", "nintendo", "ps5", "ps4", "playstation", "xbox", "control", "dualsense", "consola", "gamer", "zelda", "pokemon", "capcom", "mario", "fifa"]),
    ("A1", ["audio", "audifono", "audifonos", "audífono", "audífonos", "bocina", "bocinas", "altavoz", "partybox", "speaker", "sonido", "microfono", "barra de sonido", "soundbar", "airpods", "earbuds", "iem", "kz", "jbl", "sony wh"]),
    ("C1", ["hogar", "casa", "pantalla", "tv", "television", "televisión", "smart tv", "fire tv", "freidora", "licuadora", "cafetera", "cocina", "bateria de cocina", "batería de cocina", "sarten", "sartén", "colchon", "colchón", "sabanas", "sábanas", "mueble", "silla", "escritorio", "aspiradora", "electrodomestico", "refri", "lavadora", "campana extractora"]),
    ("D1", ["celular", "celulares", "telefono", "teléfono", "smartphone", "iphone", "samsung", "galaxy", "xiaomi", "redmi", "poco", "motorola", "oppo", "realme", "funda", "cargador", "smartwatch", "reloj inteligente"]),
    ("E1", ["computadora", "compu", "laptop", "notebook", "pc", "mouse", "raton", "teclado", "monitor", "ssd", "ram", "tarjeta grafica", "rtx", "procesador", "tablet", "ipad", "impresora", "starlink"]),
    ("F1", ["ropa", "calzado", "tenis", "zapato", "playera", "sudadera", "chamarra", "deporte", "deportes", "gym", "gimnasio", "pesa", "pesas", "bicicleta", "correr", "running", "futbol", "proteina", "creatina", "nike", "adidas", "puma"]),
    ("G1", ["herramienta", "herramientas", "taladro", "rotomartillo", "hidrolavadora", "desarmador", "llave", "auto", "carro", "coche", "ferreteria", "esmeril", "sierra", "dewalt", "makita", "bosch", "truper"]),
    ("H1", ["despensa", "perfume", "fragancia", "juguete", "juguetes", "mochila", "alimento", "croquetas", "crema", "piel", "shampoo", "balsamo", "bálsamo", "pomada", "vitaminas", "suplemento"])
]

PALABRAS_ADULTO_PROHIBIDAS = [
    "condon", "condón", "condones", "preservativo", "preservativos",
    "trojan", "durex", "prudence", "sico", "lubricante intimo", "lubricante íntimo",
    "vibrador", "dildo", "consolador", "masturbador", "sex shop", "sexshop",
    "erotico", "erótico", "erotica", "erótica", "lenceria sexy", "lencería sexy",
    "fetiche", "bdsm", "esposas eroticas", "retardante sexual", "potenciador sexual",
    "viagra", "sildenafil", "juguete sexual", "juguetes sexuales", "adultos +18", "solo adultos"
]

MENSAJE_MODERACION_CHAT = (
    "Tranquilo, solo soy un mapache 🦝. Yo solo cazo descuentos reales y seguros para todos; "
    "no abro enlaces externos ni respondo ni sigo ese tipo de temas."
)

SALUDO_COQUETO_INICIAL = (
    "¡Hola, cómplice! 🦝✨ Qué gusto verte por acá en *Bandido Ofertas*.\n\n"
    "Yo me encargo de robarme los descuentos reales antes de que las tiendas los escondan... "
    "Dime, ¿qué se te antoja cazar hoy? 👀\n\n"
    "Escríbeme qué buscas (por ejemplo: *una laptop, un mouse, algo para el hogar, videojuegos, celulares...*) "
    "y te paso el pase directo a mi grupo VIP donde caen las ofertas al instante. 💸🔥"
)


def elegir_remate_ponderado(texto_previo: str = "") -> str:
    prev_low = texto_previo.lower()
    pesos = []
    for clave, frase in REMATES_COQUETOS:
        peso = 10
        if clave in prev_low:
            peso = 1
        elif frase in _ULTIMOS_REMATES:
            peso = 2
        pesos.append(peso)

    elegido = random.choices([f for _, f in REMATES_COQUETOS], weights=pesos, k=1)[0]
    _ULTIMOS_REMATES.append(elegido)
    return elegido


def limpiar_prohibidas(texto: str) -> str:
    for mal, bien in [("chollos", "gangas"), ("chollo", "ganga"), ("Chollos", "Gangas"), ("Chollo", "Ganga")]:
        texto = texto.replace(mal, bien)
    return texto


def es_contenido_adulto(texto: str) -> bool:
    t = texto.lower()
    return any(p in t for p in PALABRAS_ADULTO_PROHIBIDAS)


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
    return ("", "")


def es_mensaje_chat_inapropiado(mensaje: str) -> bool:
    m = mensaje.lower()
    urls = re.findall(r"(https?://\S+|www\.\S+|\bt\.me/\S+)", m)
    for u in urls:
        if not any(ok in u for ok in ("amazon.com.mx", "amzn.to", "a.co/", "mercadolibre.com", "meli.la", "bandidoofertas.com")):
            return True

    temas_sexuales = [
        "sexo", "sexual", "porno", "pornografia", "pornografía", "xxx", "nudes", "pack",
        "desnuda", "desnudo", "coger", "cojer", "follar", "caliente", "cachondo", "cachonda",
        "orgasmo", "masturbar", "pene", "vagina", "chichis", "nalgas", "erotico", "erótico",
        "condon", "condón", "preservativo", "vibrador", "dildo"
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
    perfil = PROF_AMZ if tienda == "amazon" else PROF_ML
    resultado = {"titulo": "", "p_of": "", "p_or": "", "url_final": url_usuario, "url_afiliado": ""}

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(perfil),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-position=-2400,0"],
            viewport={"width": 1366, "height": 900},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto(url_usuario, timeout=35000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
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
            else:
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
                        await page.wait_for_timeout(1500)
                        url_af = await page.evaluate("""() => {
                            for (const inp of document.querySelectorAll('input, textarea')) {
                                if (inp.value && inp.value.includes('meli.la/')) return inp.value.trim();
                            }
                            const m = document.body.innerText.match(/https:\\/\\/meli\\.la\\/[A-Za-z0-9]+/);
                            return m ? m[0] : null;
                        }""")
                        break
                resultado["url_afiliado"] = url_af if (url_af and "meli.la/" in url_af) else link_ml_respaldo_chat(resultado["url_final"])
        except Exception as e:
            print(f"⚠️ [AUDITOR LINK NAV ERROR]: {e}")
        finally:
            await ctx.close()

    return resultado


def auditar_enlace_usuario(tienda: str, url_usuario: str) -> str:
    try:
        datos = asyncio.run(_inspeccionar_con_navegador(tienda, url_usuario))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        datos = loop.run_until_complete(_inspeccionar_con_navegador(tienda, url_usuario))
        loop.close()

    titulo = datos.get("titulo", "")
    corto = " ".join(titulo.split()[:6]) if titulo else "ese producto"
    p_of_num = limpiar_monto(datos.get("p_of", ""))
    p_or_num = limpiar_monto(datos.get("p_or", ""))
    url_final = datos.get("url_final") or url_usuario
    remate = elegir_remate_ponderado()

    if p_of_num <= 0:
        if tienda == "mercadolibre":
            link_af = datos.get("url_afiliado") or link_ml_respaldo_chat(url_final)
            return (
                f"🦝🌙 Ya te saqué el pase directo de afiliado para {corto} en Mercado Libre, {remate} {link_af}"
            )
        return (
            f"🦝🔍 Abrí el enlace en Amazon ({corto}) pero el vendedor tiene el precio oculto o sin stock disponible ahorita. "
            f"Si quieres ver ofertas reales que ya pasaron mi filtro antihumo hoy, pásate por mi guarida: {WORKER_URL} 🌙✨"
        )

    nums = auditar_numeros({
        "precio_oferta": p_of_num,
        "precio_original": p_or_num,
        "descuento": ""
    })
    tienda_label = "Amazon México" if tienda == "amazon" else "Mercado Libre México"
    hist = verificar_historial(url_final, p_of_num, tienda_label)

    es_humo = nums["anomalia"] or hist["es_humo"] or nums["pct_real"] < 15

    if tienda == "amazon":
        if es_humo:
            motivo = hist["nota"] or nums["motivo"] or f"solo trae {nums['pct_real']}% de descuento real"
            return (
                f"🦝🚨 ¡Alto ahí, cómplice! Pasé {corto} (${p_of_num:,.0f}) por mi filtro antihumo y NO conviene ({motivo}). "
                f"Mejor no caigas en la trampa y revisa los descuentos reales que ya cacé hoy en mi web: {WORKER_URL} 😏🔥"
            )
        return (
            f"🦝✅ ¡Ojo clínico tienes! Pasé {corto} por mi filtro antihumo y SÍ es una buena oferta (-{nums['pct_real']}% real, en ${p_of_num:,.0f} MXN). "
            f"Atrapalo antes de que Amazon lo suba... y descubre más joyas auditadas en {WORKER_URL} 🌙💎"
        )

    link_af = datos.get("url_afiliado") or link_ml_respaldo_chat(url_final)
    if es_humo:
        motivo = hist["nota"] or nums["motivo"] or f"apenas tiene {nums['pct_real']}% de descuento real"
        return (
            f"🦝🚨 Cuidado cómplice, pasé {corto} (${p_of_num:,.0f}) por mi filtro antihumo y huele a precio inflado ({motivo}). "
            f"Igual aquí tienes mi enlace directo por si decides llevártelo: {link_af} — o caza gangas reales en {WORKER_URL} 😏🔥"
        )

    return (
        f"🦝✅ ¡Botín aprobado por mi filtro antihumo! Ese {corto} sí es una gran oferta (-{nums['pct_real']}% real, en ${p_of_num:,.0f} MXN). "
        f"Lo dejé listo para ti en Mercado Libre, {remate} {link_af}"
    )


def detectar_categoria_segura(titulo: str, cat_ollama: str = "") -> str:
    t = titulo.lower()
    for cod, palabras in CATEGORIAS_EXACTAS:
        if any(p in t for p in palabras):
            return cod
    if cat_ollama and cat_ollama in CODIGOS_CAT:
        return cat_ollama
    return "H1"


def ajustar_score_real(pct: int, nota_hist: str, p_of: float, p_or: float, score_ollama: int | None = None) -> int:
    es_minimo = "mínimo histórico" in nota_hist.lower()
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
    plantillas = {
        "B1": f"🎮 Me robé este {corto} antes de que suba... imagínate tú y yo jugando toda la noche, prometo no hacer trampa a menos que tú quieras 😏🔥",
        "A1": f"🎧 Escucha esto: acabo de rescatar {corto}. Ponte los audífonos y deja que te susurre al oído las mejores gangas de la noche 🌙✨",
        "C1": f"🏠 Mira qué botín traje para tu casa: {corto}... ¿lo estrenamos juntos esta noche o te vas a hacer del rogar? Prometo portarme bien 😏🔥",
        "D1": f"📱 Me escabullí entre las sombras por este {corto}... ideal para que me escribas a medianoche cuando quieras cazar más tesoros 🦝💫",
        "E1": f"💻 Qué joya acabo de extraer: {corto}. Imagínate trabajando de día y escapándote conmigo de noche a buscar descuentos reales 😏⚡",
        "F1": f"👟 Rescaté este {corto} con un golpe maestro... perfecto para que salgamos a entrenar juntos, aunque dudo que me alcances 🦝🔥",
        "G1": f"🛠️ Botín pesado para manos expertas: {corto}. ¿Armamos algo juntos esta noche o prefieres que yo haga todo el trabajo? 😏🔧",
        "H1": f"🌙 Nadie más vio este {corto} escondido a este precio... tómalo antes de que amanezca, prometo no morder a menos que tú quieras 🦝✨"
    }
    return plantillas.get(subcat, plantillas["H1"])


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
    prompt = (
        "Eres Bandido, un ladrón nocturno elegante, astuto y coqueto en México 🦝🌙.\n"
        "Escribe un comentario corto y seductor (22 a 34 palabras) sobre ESTE producto.\n"
        f"Inventa una situación ficticia coqueta con el producto (ej. {ejemplo_dinamico}).\n"
        "Reglas: menciona el producto real, usa 2 emojis, PROHIBIDO decir 'chollo' o 'chollos', NO pongas precios ni links.\n\n"
        f"Producto: {titulo}\nTienda: {tienda} (-{pct}%)"
    )
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_VENDEDOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.92, "num_predict": 95}
            },
            timeout=45
        )
        if r.status_code == 200:
            txt = limpiar_prohibidas(r.json().get("response", "").strip().strip('"').strip("'"))
            if len(txt) > 18 and "precio validado" not in txt.lower():
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
            "subcategoria": "H2",
            "razonamiento": "Descartada y eliminada por filtro +18 / salud sexual (apto para todo público).",
            "copy_web": "",
            "numeros": {"precio_oferta": 0, "precio_original": 0, "pct_real": 0, "anomalia": True}
        }

    nums = auditar_numeros(oferta_bruta)
    if nums["anomalia"]:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": "H2",
            "razonamiento": nums["motivo"],
            "copy_web": "",
            "numeros": nums
        }

    tienda = oferta_bruta.get("tienda", "")
    p_of = nums["precio_oferta"]
    p_or = nums["precio_original"]
    pct = nums["pct_real"]

    hist = verificar_historial(url_norm, p_of, tienda)
    if hist["es_humo"]:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": "H2",
            "razonamiento": hist["nota"],
            "copy_web": "",
            "numeros": nums
        }

    cat_ollama = ""
    score_ollama = None
    descartar_ia = False
    razon_ia = ""

    prompt_auditor = (
        "Eres un auditor estricto de ofertas en México. Responde SOLO con un JSON válido:\n"
        '{"descartar": false, "score": 3, "subcategoria": "H1", "razon": "motivo breve"}\n'
        f"Códigos permitidos de subcategoria: {', '.join(CODIGOS_CAT)}.\n"
        "Descarta (descartar: true) si es producto para adultos (+18), preservativos, sex shop, funda barata genérica o cable suelto.\n"
        f"Producto: {titulo}\nTienda: {tienda}\nPrecio oferta: ${p_of} | Original:${p_or} | Descuento: {pct}%"
    )
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_AUDITOR,
                "prompt": prompt_auditor,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 110}
            },
            timeout=35
        )
        if r.status_code == 200:
            data_ia = _extraer_json(r.json().get("response", ""))
            if data_ia:
                descartar_ia = bool(data_ia.get("descartar", False))
                cat_ollama = str(data_ia.get("subcategoria", "")).upper().strip()
                razon_ia = limpiar_prohibidas(str(data_ia.get("razon", "")))
                if str(data_ia.get("score", "")).isdigit():
                    score_ollama = int(data_ia["score"])
    except Exception:
        pass

    subcat = detectar_categoria_segura(titulo, cat_ollama)
    score = ajustar_score_real(pct, hist["nota"], p_of, p_or, score_ollama)

    if descartar_ia and pct < 25:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": subcat,
            "razonamiento": razon_ia or "Descartada por auditoría de relevancia.",
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
    # 1. Enlaces pegados: si es Mercado Libre -> web a secas (no disponible); si es Amazon -> auditar
    tienda_link, url_usuario = extraer_url_tienda(mensaje_usuario)
    if tienda_link == "mercadolibre":
        return (
            f"???? Ese enlace espec?fico de Mercado Libre no est? disponible actualmente en mi guarida, "
            f"pero revisa mi web en vivo donde subo gangas auditadas cada 15 minutos: {WORKER_URL} ???"
        )
    if tienda_link == "amazon" and url_usuario:
        return auditar_enlace_usuario(tienda_link, url_usuario)

    if es_mensaje_chat_inapropiado(mensaje_usuario):
        return MENSAJE_MODERACION_CHAT

    if oferta and not _oferta_coincide_con_pedido(mensaje_usuario, oferta):
        oferta = None

    if not oferta:
        return (
            f"🦝💔 Ese botín específico no lo tengo ahorita en mi guarida (o tristemente esa oferta ya expiró), "
            f"pero revisa mi web en vivo donde subo gangas auditadas cada 15 minutos para que no se te escape ninguna: {WORKER_URL} 🌙✨"
        )

    link = oferta.get("url_afiliado") or WORKER_URL
    titulo = oferta.get("titulo", "esta joya")
    corto = " ".join(titulo.split()[:5])
    tienda_raw = str(oferta.get("tienda", "")).lower()
    tienda_nombre = "Amazon México" if "amazon" in tienda_raw or "amzn" in link.lower() else "Mercado Libre"
    subcat = oferta.get("subcategoria") or detectar_categoria_segura(titulo)

    calc = calcular_tarjeta(oferta, mensaje_usuario)
    dato_banco = f" (Ojo con tu tarjeta: {calc['detalle']})" if calc["tiene_banco"] else ""

    intro_alt = (
        "Ese del post ya voló, pero me escabullí en mi catálogo web y rescaté esta joya parecida con descuentazo: "
        if es_alternativa_d1
        else ""
    )

    ejemplo_dinamico = random.choice(EJEMPLOS_PROMPT_COQUETO)
    prompt = (
        "Eres Bandido, un ladrón nocturno elegante, astuto, tierno y coqueto en México 🦝🌙.\n"
        f"Un usuario te escribió sobre este producto: '{corto}'.\n"
        "Escribe un comentario corto, personal y muy seductor (24 a 36 palabras) inventando una situación ficticia íntima y coqueta "
        f"con el usuario usando o presumiendo este {corto}.\n"
        f"Inspírate en este estilo (sin copiarlo literal): {ejemplo_dinamico}.\n"
        "REGLAS: menciona el producto real, usa 2 emojis, PROHIBIDO saludar con 'Hola amigo', PROHIBIDO decir 'chollo' o 'chollos', NO pongas precios ni links.\n\n"
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
                "options": {"temperature": 0.94, "num_predict": 95}
            },
            timeout=45
        )
        if r.status_code == 200:
            txt = limpiar_prohibidas(r.json().get("response", "").strip().strip('"').strip("'"))
            txt = re.sub(r"\s+", " ", txt)
            if len(txt) > 18 and "hola, amigo" not in txt.lower() and "hola amigo" not in txt.lower():
                frase_coqueta = txt
    except Exception:
        pass

    if not frase_coqueta:
        frase_coqueta = respaldo_coqueto(titulo, subcat)

    remate = elegir_remate_ponderado(frase_coqueta)

    return (
        f"{intro_alt}{frase_coqueta}{dato_banco} "
        f"Lo dejé escondido en {tienda_nombre}, {remate} {link}"
    )

