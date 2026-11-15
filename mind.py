import json
import requests
from cfg import OLLAMA_URL, MODELO_AUDITOR, MODELO_VENDEDOR, CODIGOS_CAT, WORKER_URL
from calc import auditar_numeros, calcular_tarjeta
from hist import verificar_historial

REGLAS_CATEGORIA = [
    ("B1", ["nintendo", "switch", "xbox", "playstation", "ps5", "ps4", "videojuego", "control gamer", "dualsense", "capcom", "zelda", "mario", "fifa", "ea sports"]),
    ("A1", ["audifonos", "audífonos", "bocina", "altavoz", "partybox", "soundbar", "barra de sonido", "jbl", "sony wh", "airpods", "earbuds"]),
    ("C1", ["cafetera", "licuadora", "freidora", "sarten", "sartén", "bateria de cocina", "batería de cocina", "campana extractora", "horno", "microondas", "colchon", "colchón", "sabanas", "sábanas", "aspiradora", "fire tv", "pantalla", "television", "televisión", "smart tv"]),
    ("D1", ["celular", "smartphone", "iphone", "samsung galaxy", "motorola", "xiaomi", "redmi", "poco", "oppo", "realme"]),
    ("E1", ["laptop", "notebook", "monitor", "teclado", "mouse", "ssd", "memoria ram", "tarjeta grafica", "rtx", "impresora", "tablet", "ipad"]),
    ("F1", ["tenis", "calzado", "playera", "sudadera", "mochila", "bicicleta", "mancuernas", "gimnasio", "nike", "adidas", "puma"]),
    ("G1", ["taladro", "rotomartillo", "esmeriladora", "llave de impacto", "herramienta", "dewalt", "makita", "bosch", "truper"])
]

def limpiar_prohibidas(texto: str) -> str:
    for mal, bien in [("chollos", "gangas"), ("chollo", "ganga"), ("Chollos", "Gangas"), ("Chollo", "Ganga")]:
        texto = texto.replace(mal, bien)
    return texto

def detectar_categoria_segura(titulo: str) -> str:
    t = titulo.lower()
    for cod, palabras in REGLAS_CATEGORIA:
        if any(p in t for p in palabras):
            return cod
    return ""

def seducir_tarjeta(titulo: str, tienda: str, nota_hist: str, pct: int) -> str:
    """Crea una fantasía única, nocturna y coqueta adaptada al producto exacto."""
    prompt = (
        "Eres Bandido, un ladrón nocturno elegante, pícaro y seductor que roba las mejores ofertas reales de México 🦝🌙.\n"
        "Escribe un comentario corto y original (25 a 38 palabras) específicamente sobre ESTE producto.\n"
        "Inventa una escena coqueta y juguetona usando el objeto real (por ejemplo, si es un colchón: 'imagínate tú y yo estrenando este colchón... prometo portarme bien, a menos que tú quieras lo contrario 😏🔥'; si es una tele o bocina, arma la escena con música o película).\n"
        "REGLAS ESTRICTAS:\n"
        "- Menciona el tipo de producto real para que se note que es único.\n"
        "- Tono coqueto, travieso, cómplice y con 2 o 3 emojis.\n"
        "- PROHIBIDO usar frases robóticas como 'oferta competitiva' o 'producto deseable'.\n"
        "- PROHIBIDO decir 'chollo' o 'chollos'.\n"
        "- NO pongas precios ni links.\n\n"
        f"Producto exacto: {titulo}\n"
        f"Tienda: {tienda} (-{pct}%)"
    )
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_VENDEDOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.92, "num_predict": 110}
            },
            timeout=30
        )
        if r.status_code == 200:
            txt = limpiar_prohibidas(r.json().get("response", "").strip().strip('"').strip("'"))
            if len(txt) > 20 and "competitiva" not in txt.lower():
                return txt
    except Exception:
        pass
    nombre_corto = " ".join(titulo.split()[:4])
    return f"🌙 Me escabullí en {tienda} solo para robarte este {nombre_corto}... ¿lo estrenamos esta noche tú y yo? Prometo no morder a menos que tú quieras 😏🔥"

def auditar(oferta_bruta: dict) -> dict:
    nums = auditar_numeros(oferta_bruta)
    if nums["anomalia"]:
        return {"descartar": True, "score": 5, "subcategoria": "H2", "razonamiento": nums["motivo"], "copy_web": "", "numeros": nums}

    titulo = oferta_bruta.get("titulo", "")
    tienda = oferta_bruta.get("tienda", "")
    url_norm = oferta_bruta.get("url_normal", "")
    p_of = nums["precio_oferta"]
    p_or = nums["precio_original"]
    pct = nums["pct_real"]

    hist = verificar_historial(url_norm, p_of, tienda)
    if hist["es_humo"]:
        return {"descartar": True, "score": 5, "subcategoria": "H2", "razonamiento": hist["nota"], "copy_web": "", "numeros": nums}

    cat_fija = detectar_categoria_segura(titulo)

    prompt = (
        "Eres un auditor financiero en México. Evalúa esta oferta real y responde SOLO JSON:\n"
        "score: 1 (ganga histórica), 2 (muy buena), 3 (decente), 4 (floja), 5 (basura).\n"
        "subcategoria: A1 (Audio), B1 (Videojuegos), C1 (Hogar), D1 (Celulares), E1 (Computación), F1 (Deportes/Ropa), G1 (Herramientas), H1 (General).\n"
        f"Producto: {titulo}\nTienda: {tienda}\nOferta: ${p_of:,.0f} | Antes: ${p_or:,.0f} (-{pct}%)\nHistorial: {hist['nota']}\n"
        'JSON: {"score": 2, "descartar": false, "subcategoria": "H1"}'
    )

    score = 2 if pct >= 25 else 3
    subcat = cat_fija or "H1"
    descartar = False

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODELO_AUDITOR, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.1, "num_predict": 80}},
            timeout=25
        )
        if r.status_code == 200:
            data = json.loads(r.json().get("response", "{}"))
            s = int(data.get("score", score))
            if 1 <= s <= 5:
                score = s
            if not cat_fija:
                sc = str(data.get("subcategoria", "H1")).strip().upper()
                if sc in CODIGOS_CAT:
                    subcat = sc
            descartar = bool(data.get("descartar", False)) or score == 5
    except Exception:
        pass

    if descartar:
        return {"descartar": True, "score": 5, "subcategoria": subcat, "razonamiento": "Descartada por auditoría.", "copy_web": "", "numeros": nums}

    copy_web = seducir_tarjeta(titulo, tienda, hist["nota"], pct)

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

    if calc["tiene_banco"]:
        dato_dinero = f"El usuario preguntó por su tarjeta. Dale este dato exacto: {calc['detalle']}"
    else:
        dato_dinero = "No mencionó banco; enfócate en seducirlo con una escena coqueta usando el producto."

    prompt = (
        "Eres Bandido, un ladrón nocturno elegante, pícaro y seductor que caza ofertas reales en México 🦝🌙.\n"
        "Habla en primera persona, coquetea con el usuario inventando una escena divertida con el producto (ej. 'imagínate tú y yo...', 'prometo no morder a menos que tú quieras 😏').\n"
        f"Instrucción financiera: {dato_dinero}\n"
        "Reglas: máximo 55 palabras, usa emojis, PROHIBIDO decir 'chollo' o 'chollos', NO inventes precios ni cupones.\n"
        f"Termina SIEMPRE con este link exacto: {link}\n\n"
        f"Producto: {titulo}\n"
        f"Comentario del usuario: {mensaje_usuario}"
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODELO_VENDEDOR, "prompt": prompt, "stream": False, "options": {"temperature": 0.9, "num_predict": 140}},
            timeout=30
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