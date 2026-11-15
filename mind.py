import json
import re
import requests
from cfg import OLLAMA_URL, MODELO_AUDITOR, MODELO_VENDEDOR, CODIGOS_CAT, WORKER_URL
from calc import auditar_numeros, calcular_tarjeta
from hist import verificar_historial

# Mapa exacto de las 9 categorías de la web y grupos de WhatsApp
CATEGORIAS_EXACTAS = [
    ("B1", ["juego", "juegos", "videojuego", "videojuegos", "switch", "nintendo", "ps5", "ps4", "playstation", "xbox", "control", "dualsense", "consola", "gamer", "zelda", "pokemon", "capcom", "mario", "fifa"]),
    ("A1", ["audio", "audifono", "audifonos", "audífono", "audífonos", "bocina", "bocinas", "altavoz", "partybox", "speaker", "sonido", "microfono", "barra de sonido", "soundbar", "airpods", "earbuds", "iem", "kz", "jbl", "sony wh"]),
    ("C1", ["hogar", "casa", "pantalla", "tv", "television", "televisión", "smart tv", "fire tv", "freidora", "licuadora", "cafetera", "cocina", "bateria de cocina", "batería de cocina", "sarten", "sartén", "colchon", "colchón", "sabanas", "sábanas", "mueble", "aspiradora", "electrodomestico", "refri", "lavadora", "campana extractora"]),
    ("D1", ["celular", "celulares", "telefono", "teléfono", "smartphone", "iphone", "samsung", "galaxy", "xiaomi", "redmi", "poco", "motorola", "oppo", "realme", "funda", "cargador", "smartwatch", "reloj inteligente"]),
    ("E1", ["computadora", "compu", "laptop", "notebook", "pc", "mouse", "raton", "teclado", "monitor", "ssd", "ram", "tarjeta grafica", "rtx", "procesador", "tablet", "ipad", "impresora", "starlink"]),
    ("F1", ["ropa", "calzado", "tenis", "zapato", "playera", "sudadera", "chamarra", "deporte", "deportes", "gym", "gimnasio", "pesa", "pesas", "bicicleta", "correr", "running", "futbol", "proteina", "creatina", "nike", "adidas", "puma"]),
    ("G1", ["herramienta", "herramientas", "taladro", "rotomartillo", "hidrolavadora", "desarmador", "llave", "auto", "carro", "coche", "ferreteria", "esmeril", "sierra", "dewalt", "makita", "bosch", "truper"]),
    ("H1", ["despensa", "perfume", "fragancia", "juguete", "juguetes", "mochila", "alimento", "croquetas", "crema", "piel", "shampoo", "balsamo", "bálsamo", "pomada", "vitaminas", "suplemento"])
]

GRUPOS_WHATSAPP = {
    "hot": {
        "nombre": "🔥 Hot / VIP (Score 1-2 y Relámpago)",
        "link": "https://chat.whatsapp.com/J8aBxZpCAqa42PQekfaLKH",
        "keywords": ["hot", "vip", "todo", "todas", "mejores", "ganga", "gangas", "relampago", "caducar"]
    },
    "audio": {
        "nombre": "🎧 Audio",
        "link": "https://chat.whatsapp.com/J6oRlQxpNB26cGrWoe5K9F",
        "keywords": ["audio", "audifono", "audifonos", "bocina", "bocinas", "sonido", "microfono", "barra de sonido", "airpods", "earbuds", "iem", "kz"]
    },
    "videojuegos": {
        "nombre": "🎮 Videojuegos",
        "link": "https://chat.whatsapp.com/FXuacEhYReBKIbdFEK0jX7",
        "keywords": ["juego", "juegos", "videojuego", "videojuegos", "switch", "nintendo", "ps5", "playstation", "xbox", "control", "consola", "gamer", "zelda", "pokemon"]
    },
    "hogar": {
        "nombre": "🏠 Hogar",
        "link": "https://chat.whatsapp.com/FQQ6ElHrCwC6Vwxouz1KGd",
        "keywords": ["hogar", "casa", "pantalla", "tv", "television", "freidora", "licuadora", "cafetera", "cocina", "colchon", "mueble", "aspiradora", "electrodomestico", "refri", "lavadora"]
    },
    "celulares": {
        "nombre": "📱 Celulares",
        "link": "https://chat.whatsapp.com/KHfVnULyRbB6rN9LeW0MU5",
        "keywords": ["celular", "celulares", "telefono", "smartphone", "iphone", "samsung", "xiaomi", "motorola", "oppo", "funda", "cargador", "smartwatch", "reloj inteligente"]
    },
    "computacion": {
        "nombre": "💻 Computación",
        "link": "https://chat.whatsapp.com/B5pgd2kX8X47NEdkVEpbgL",
        "keywords": ["computadora", "compu", "laptop", "pc", "mouse", "mause", "raton", "teclado", "monitor", "ssd", "ram", "tarjeta grafica", "procesador", "tablet", "ipad", "impresora"]
    },
    "deportes": {
        "nombre": "👕 Ropa, Calzado y Deporte",
        "link": "https://chat.whatsapp.com/KcoSApUOZ29JrRgv1TQGYW",
        "keywords": ["ropa", "calzado", "deporte", "deportes", "tenis", "gym", "gimnasio", "pesa", "pesas", "bicicleta", "correr", "running", "futbol", "ropa deportiva", "proteina", "creatina"]
    },
    "herramientas": {
        "nombre": "🛠️ Herramientas",
        "link": "https://chat.whatsapp.com/FQqwJ0piUzI42aTiWBKinf",
        "keywords": ["herramienta", "herramientas", "taladro", "hidrolavadora", "desarmador", "llave", "auto", "carro", "coche", "ferreteria", "esmeril", "sierra", "caja de herramientas"]
    },
    "general": {
        "nombre": "✨ General",
        "link": "https://chat.whatsapp.com/Iqnl7mgHkeu2p6wlEBOrOj",
        "keywords": ["general", "despensa", "perfume", "juguete", "juguetes", "varios", "super", "mochila"]
    }
}

SALUDO_COQUETO_INICIAL = (
    "¡Hola, cómplice! 🦝✨ Qué gusto verte por acá en *Bandido Ofertas*.\n\n"
    "Yo me encargo de robarme los descuentos reales antes de que las tiendas los escondan... "
    "Dime, ¿qué se te antoja cazar hoy? 👀\n\n"
    "Escríbeme qué buscas (por ejemplo: *una laptop, un mouse, algo para el hogar, videojuegos, celulares...*) "
    "y te paso el pase directo a mi grupo VIP donde caen las ofertas al instante. 💸🔥"
)

def limpiar_prohibidas(texto: str) -> str:
    for mal, bien in [("chollos", "gangas"), ("chollo", "ganga"), ("Chollos", "Gangas"), ("Chollo", "Ganga")]:
        texto = texto.replace(mal, bien)
    return texto

def detectar_categoria_segura(titulo: str, cat_ollama: str = "") -> str:
    t = titulo.lower()
    for cod, palabras in CATEGORIAS_EXACTAS:
        if any(p in t for p in palabras):
            return cod
    if cat_ollama and cat_ollama in CODIGOS_CAT:
        return cat_ollama
    return "H1"

def ajustar_score_real(pct: int, nota_hist: str, p_of: float, p_or: float, score_ollama: int | None = None) -> int:
    """Distribuye niveles reales 1 a 5 para evitar que todo caiga en nivel 2."""
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
    prompt = (
        "Eres Bandido, un ladrón nocturno elegante, astuto y coqueto en México 🦝🌙.\n"
        "Escribe un comentario corto y seductor (22 a 34 palabras) sobre ESTE producto.\n"
        "Inventa una situación ficticia coqueta con el producto (ej. 'imagínate tú y yo estrenándolo... prometo no morder a menos que tú quieras 😏🔥').\n"
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
                "options": {"temperature": 0.9, "num_predict": 95}
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

    titulo = oferta_bruta.get("titulo", "")
    tienda = oferta_bruta.get("tienda", "")
    url_norm = oferta_bruta.get("url_normal", "")
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

    # Consulta al modelo auditor para validar categoría y descartar accesorios basura
    cat_ollama = ""
    score_ollama = None
    descartar_ia = False
    razon_ia = ""

    prompt_auditor = (
        "Eres un auditor estricto de ofertas en México. Responde SOLO con un JSON válido:\n"
        '{"descartar": false, "score": 3, "subcategoria": "H1", "razon": "motivo breve"}\n'
        f"Códigos permitidos de subcategoria: {', '.join(CODIGOS_CAT)}.\n"
        "Descarta (descartar: true) solo si es funda barata genérica, cable suelto o producto engañoso.\n"
        f"Producto: {titulo}\nTienda: {tienda}\nPrecio oferta: ${p_of} | Original: ${p_or} | Descuento: {pct}%"
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

def vender(mensaje_usuario: str, oferta: dict | None) -> str:
    if not oferta:
        return f"🦝🌙 ¡Ay, cómplice! Ese botín ya voló de mi guarida... pero pásate por aquí que acabo de esconder joyas frescas: {WORKER_URL} 😏💎"

    link = oferta.get("url_afiliado") or WORKER_URL
    titulo = oferta.get("titulo", "esta joya")
    calc = calcular_tarjeta(oferta, mensaje_usuario)

    dato_dinero = (
        f"Dale este dato exacto de su tarjeta: {calc['detalle']}"
        if calc["tiene_banco"]
        else "No mencionó banco; sedúcelo con una escena coqueta usando el producto."
    )

    prompt = (
        "Eres Bandido, un ladrón nocturno elegante, pícaro y seductor en México 🦝🌙.\n"
        "Coquetea con el usuario inventando una escena divertida con el producto (ej. 'imagínate tú y yo...', 'prometo no morder a menos que tú quieras 😏').\n"
        f"{dato_dinero}\n"
        "Reglas: máximo 55 palabras, usa emojis, PROHIBIDO decir 'chollo' o 'chollos', NO inventes precios.\n"
        f"Termina SIEMPRE con este link: {link}\n\n"
        f"Producto: {titulo}\nComentario: {mensaje_usuario}"
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_VENDEDOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.9, "num_predict": 140}
            },
            timeout=45
        )
        if r.status_code == 200:
            resp = limpiar_prohibidas(r.json().get("response", "").strip())
            if resp:
                if link not in resp:
                    resp += f"\n\n👉 Atrápalo aquí: {link}"
                return resp
    except Exception:
        pass

    extra = f" {calc['detalle']}" if calc["tiene_banco"] else ""
    return f"🦝🌙 ¡Qué buen ojo tienes!{extra} ¿Lo estrenamos esta noche o te vas a hacer del rogar? Prometo no morder 😏🔥\n{link}"