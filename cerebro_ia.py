import os
import re
import json
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
WORKER_URL = "https://bandido.bandidoofertas.workers.dev"
WORKER_TOKEN = "Bearer bandido_secret"
MODEL_NAME = "llama3"
CARPETA_IMAGENES = os.path.join("C:\\Bandido\\Bandido", "imagenes_bandido")

if not os.path.exists(CARPETA_IMAGENES):
    os.makedirs(CARPETA_IMAGENES)

CODIGOS_VALIDOS = {
    "A", "A1", "A2",
    "B", "B1", "B2", "B3", "B4",
    "C", "C1", "C2", "C3",
    "D", "D1", "D2",
    "E", "E1", "E2", "E3",
    "F", "F1", "F2",
    "G", "G1", "G2",
    "H", "H1", "H2"
}

PROMOS_BANCARIAS = {
    "banamex": {"codigo": "BNMXBF", "porcentaje": 10, "detalle": "10% con cupón BNMXBF a 3, 6 y 9 MSI, o hasta 30% de bonificación desde 12 MSI"},
    "bbva": {"codigo": "BBVABF", "porcentaje": 10, "detalle": "10% con cupón BBVABF a 3, 6 y 9 MSI, o 15% de bonificación desde 12 MSI"},
    "mercado pago": {"codigo": "TCMPBF", "porcentaje": 15, "detalle": "15% o hasta 24 MSI con cupón TCMPBF (o 10% con Mercado Crédito usando CREDITOBF)"},
    "santander": {"codigo": "SANTBF", "porcentaje": 15, "detalle": "15% con cupón SANTBF en una exhibición, o 10% de cashback desde 6 MSI"},
    "banorte": {"codigo": "BNRTBF", "porcentaje": 10, "detalle": "10% con cupón BNRTBF en una exhibición + 10% de bonificación"},
    "hsbc": {"codigo": "HSBCBF", "porcentaje": 10, "detalle": "10% con cupón HSBCBF en una exhibición o 3-6 MSI, o hasta 30% de devolución desde 6 MSI"},
    "oxxo": {"codigo": "OXXOBF", "porcentaje": 10, "detalle": "10% de descuento con cupón OXXOBF pagando en efectivo"},
    "american express": {"codigo": "AMEXBF", "porcentaje": 10, "detalle": "10% con cupón AMEXBF a una exhibición o 3 MSI, o $1,500 de bonificación en MSI"},
    "amex": {"codigo": "AMEXBF", "porcentaje": 10, "detalle": "10% con cupón AMEXBF a una exhibición o 3 MSI, o $1,500 de bonificación en MSI"},
    "scotiabank": {"codigo": "SCBABF", "porcentaje": 15, "detalle": "15% con cupón SCBABF en una exhibición, o hasta 25% de cashback"},
    "afirme": {"codigo": "AFRMBF", "porcentaje": 20, "detalle": "20% con cupón AFRMBF en una exhibición o 3-12 MSI"},
    "invex": {"codigo": "INVEBF", "porcentaje": 10, "detalle": "10% con cupón INVEBF a 3, 6, 9 y 12 MSI"},
    "openbank": {"codigo": "OPBABF", "porcentaje": 10, "detalle": "10% con cupón OPBABF en una exhibición, o 15% de cashback al diferir"},
    "mifel": {"codigo": "MIFEBF", "porcentaje": 15, "detalle": "15% con cupón MIFEBF en una exhibición, o hasta $6,000 de bonificación desde 12 MSI"},
    "nu": {"codigo": "", "porcentaje": 0, "detalle": "Bonificación directa a partir de 6 MSI sin necesidad de cupón"},
    "klar": {"codigo": "", "porcentaje": 10, "detalle": "10% de cashback directo desde 6 MSI"},
    "didi": {"codigo": "", "porcentaje": 20, "detalle": "Hasta 20% de cashback directo con tarjeta de crédito"},
    "bancoppel": {"codigo": "", "porcentaje": 20, "detalle": "Hasta 20% de bonificación directa"},
    "falabella": {"codigo": "", "porcentaje": 15, "detalle": "15% de cashback directo a MSI"}
}


def limpiar_monto(precio_str: str) -> float:
    if not precio_str:
        return 0.0
    limpio = re.sub(r"[^\d.]", "", str(precio_str).replace(",", ""))
    try:
        return float(limpio) if limpio else 0.0
    except ValueError:
        return 0.0


def calcular_precio_con_tarjeta(precio_oferta_str: str, tarjeta_usuario: str) -> dict:
    base = limpiar_monto(precio_oferta_str)
    t_lower = tarjeta_usuario.lower()
    for banco, info in PROMOS_BANCARIAS.items():
        if banco in t_lower:
            pct = info["porcentaje"]
            descuento_extra = round(base * (pct / 100.0), 2)
            precio_final = round(base - descuento_extra, 2)
            return {
                "banco": banco.title(),
                "codigo": info["codigo"],
                "precio_base_oferta": base,
                "descuento_extra": descuento_extra,
                "precio_final_estimado": precio_final,
                "detalle": info["detalle"]
            }
    return {
        "banco": tarjeta_usuario,
        "codigo": "",
        "precio_base_oferta": base,
        "descuento_extra": 0.0,
        "precio_final_estimado": base,
        "detalle": "No encontré cupón específico para esa tarjeta, pero revisa si entra a MSI."
    }


def verificar_vigencia_oferta(url_oferta: str, texto_pagina: str = "") -> dict:
    frases_muertas = [
        "publicación pausada", "publicacion pausada", "no está disponible",
        "no esta disponible", "agotado", "sin stock", "página no encontrada",
        "esta oferta ya no existe"
    ]
    contenido = texto_pagina.lower()

    if not contenido and url_oferta.startswith("http"):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}
            r = requests.get(url_oferta, headers=headers, timeout=10)
            if r.status_code == 404:
                contenido = "esta oferta ya no existe"
            else:
                contenido = r.text.lower()
        except Exception:
            pass

    if any(f in contenido for f in frases_muertas):
        try:
            requests.post(
                f"{WORKER_URL}/api/eliminar",
                json={"url_afiliado": url_oferta},
                headers={"Authorization": WORKER_TOKEN},
                timeout=10
            )
        except Exception:
            pass
        return {"activa": False, "mensaje": "esta oferta ya no existe fuera"}

    return {"activa": True, "mensaje": "Oferta activa"}


def clasificar_por_reglas(titulo: str) -> str | None:
    t = titulo.lower()

    if any(k in t for k in ["nintendo", "switch", "joy-con", "joycon", "zelda", "mario bros", "pokemon"]):
        return "B1"
    if any(k in t for k in ["playstation", "ps5", "ps4", "dualsense"]):
        return "B2"
    if any(k in t for k in ["xbox", "game pass", "series x", "series s"]):
        return "B3"
    if any(k in t for k in ["steam deck", "rog ally", "pc gamer", "tarjeta grafica", "rtx", "teclado mecanico gamer"]):
        return "B4"

    if any(k in t for k in ["audifono", "audífono", "auricular", "airpods", "earbuds", "headset", "wh-1000", "freebuds", "galaxy buds"]):
        return "A1"
    if any(k in t for k in ["bocina", "altavoz", "soundbar", "barra de sonido", "partybox", "jbl", "subwoofer", "echo dot", "alexa"]):
        return "A2"

    if any(k in t for k in ["celular", "smartphone", "iphone", "galaxy s", "redmi", "poco", "motorola", "oppo", "xiaomi"]):
        return "D1"
    if any(k in t for k in ["smartwatch", "reloj inteligente", "apple watch", "galaxy watch", "mi band", "cargador", "power bank"]):
        return "D2"

    if any(k in t for k in ["laptop", "macbook", "notebook", "ideapad", "thinkpad", "tablet", "ipad", "computadora", "pc "]):
        return "E1"
    if any(k in t for k in ["monitor", "teclado", "mouse", "webcam", "impresora"]):
        return "E2"
    if any(k in t for k in ["ssd", "disco duro", "memoria ram", "microsd", "usb", "procesador", "ryzen"]):
        return "E3"

    if any(k in t for k in ["impresora 3d", "filamento", "pla ", "resina 3d", "creality", "bambu lab", "multimetro", "cautin", "soldadora"]):
        return "G2"
    if any(k in t for k in ["taladro", "rotomartillo", "esmeril", "llave de impacto", "desarmador", "herramienta", "hidrolavadora", "compresor"]):
        return "G1"

    if any(k in t for k in ["pantalla", "smart tv", "television", "televisión", "refrigerador", "lavadora", "microondas", "aire acondicionado", "ventilador", "aspiradora"]):
        return "C1"
    if any(k in t for k in ["mesa", "silla", "colchon", "colchón", "sabana", "sábana", "almohada", "lampara", "lámpara", "luces led", "cortina"]):
        return "C2"
    if any(k in t for k in ["licuadora", "freidora", "cafetera", "sarten", "sartén", "bateria de cocina", "batería de cocina", "olla", "horno", "termo"]):
        return "C3"

    if any(k in t for k in ["mancuerna", "pesa", "gimnasio", "caminadora", "bicicleta fija", "proteina", "proteína", "creatina"]):
        return "F1"

    if any(k in t for k in ["tenis", "calzado", "zapato", "playera", "sudadera", "chamarra", "pantalon", "perfume", "eau de", "reloj", "lentes", "bolsa", "mochila"]):
        return "H1"

    return None


def procesar_link_meli(url: str) -> str:
    if not url:
        return ""
    if "meli.la/" in url:
        return url.strip()
    url_base = url.split('?')[0].split('#')[0]
    return f"{url_base}?matt_word=cofa20231216170418&matt_tool=92220708&forceInApp=true"


def verificar_link(url_afiliado: str, url_normal: str) -> str:
    target_url = url_afiliado if url_afiliado else url_normal
    if not target_url:
        return ""
    if "mercadolibre.com.mx" in target_url or "meli.la" in target_url:
        return procesar_link_meli(target_url)
    return target_url


def descargar_imagen_real(url_imagen: str, titulo_oferta: str) -> str:
    if not url_imagen or not url_imagen.startswith("http"):
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}
        response = requests.get(url_imagen, headers=headers, timeout=12)
        if response.status_code == 200 and len(response.content) > 1000:
            nombre_archivo = f"real_{abs(hash(titulo_oferta))}.jpg"
            ruta_completa = os.path.join(CARPETA_IMAGENES, nombre_archivo)
            with open(ruta_completa, "wb") as f:
                f.write(response.content)
            return ruta_completa
    except Exception as e:
        print(f"⚠️ No se pudo descargar la imagen real: {e}")
    return ""


def validar_respuesta_ia(data: dict, url_final: str, ruta_imagen: str, tienda: str, precio_oferta: str, titulo: str) -> dict:
    try:
        score = int(data.get("score", 3))
        if score < 1 or score > 5:
            score = 3
    except Exception:
        score = 3

    descartar_raw = data.get("descartar", False)
    if isinstance(descartar_raw, str):
        descartar = descartar_raw.strip().lower() == "true"
    else:
        descartar = bool(descartar_raw)

    subcat_regla = clasificar_por_reglas(titulo)
    if subcat_regla:
        subcat = subcat_regla
    else:
        subcat = str(data.get("subcategoria", "H2")).strip().upper()
        if subcat not in CODIGOS_VALIDOS:
            subcat = "H2"

    razonamiento = str(data.get("razonamiento_antihumo", "")).strip()
    razonamiento = razonamiento.replace("chollos", "gangas").replace("Chollos", "Gangas").replace("chollo", "ganga")

    if len(razonamiento) < 15:
        razonamiento = (
            "Oye lindura... ¿por qué no te llevas esta maravilla y cuando te llegue "
            "la probamos juntos? Prometo no morder... a menos que tú quieras 🤖🦝🔥"
        )

    return {
        "score": score,
        "descartar": descartar,
        "subcategoria": subcat,
        "razonamiento_antihumo": razonamiento,
        "url_final": url_final,
        "imagen_local": ruta_imagen
    }


def cerebro_autonomo_bandido(datos_oferta_bruta: dict) -> dict:
    titulo = datos_oferta_bruta.get('titulo', 'Sin título')
    precio_original = datos_oferta_bruta.get('precio_original', '')
    precio_oferta = datos_oferta_bruta.get('precio_oferta', '$0')
    descuento = datos_oferta_bruta.get('descuento', '')
    tienda = datos_oferta_bruta.get('tienda', 'Tienda en línea')
    url_afiliado = datos_oferta_bruta.get('url_afiliado', '')
    url_normal = datos_oferta_bruta.get('url_normal', '')
    url_imagen = datos_oferta_bruta.get('imagen_url') or datos_oferta_bruta.get('url_imagen', '')

    url_final = verificar_link(url_afiliado, url_normal)
    ruta_imagen = descargar_imagen_real(url_imagen, titulo)

    prompt_sistema = (
        "Eres Bandido, un mapache robot sumamente seductor, pícaro, sensual, coqueto y juguetón.\n"
        "REGLAS ESTRICTAS PARA EL PIROPO (razonamiento_antihumo):\n"
        "- Escribe ÚNICAMENTE un piropo corto, atrevido y divertido de 25 a 45 palabras dirigido a quien mira el producto.\n"
        "- PROHIBIDO mencionar bancos, tarjetas, MSI, porcentajes de descuento, tiendas o precios en el texto.\n"
        "- Empieza con un gancho irresistible ('Oye lindura...', 'Dime una cosa, bombón...', 'Ven acá, belleza...') y remata con picardía robótica ('cuando te llegue lo probamos juntos... prometo no morder... a menos que tú quieras 🤖🦝🔥').\n"
        "- Usa emojis coquetos (🦝, 🔥, 🤖, 😉, 💋, ✨).\n"
        "- NUNCA uses la palabra 'chollos' ni 'chollo'.\n\n"
        "FILTRO ANTIHUMO:\n"
        "- Si el descuento es falso (<10%) o producto sin valor, marca \"descartar\": true.\n"
        "- Asigna score entero del 1 al 5 (1 = ganga histórica, 2 = ofertón muy bueno, 3 = oferta sólida, 4 = descuento leve, 5 = relleno).\n\n"
        "CLASIFICACIÓN JERÁRQUICA:\n"
        " - A1: Audífonos | A2: Bocinas | A: Audio\n"
        " - B1: Nintendo | B2: PlayStation | B3: Xbox | B4: PC Gaming | B: Videojuegos\n"
        " - C1: Electrodomésticos y Pantallas | C2: Muebles y Decoración | C3: Cocina | C: Hogar\n"
        " - D1: Celulares | D2: Smartwatches y Accesorios | D: Telefonía\n"
        " - E1: Laptops y Tablets | E2: Monitores y Periféricos | E3: Componentes | E: Computación\n"
        " - F1: Gimnasio | F2: Ropa Deportiva | F: Deportes\n"
        " - G1: Herramientas | G2: Impresión 3D y Electrónica | G: Industria\n"
        " - H1: Moda y Perfumes | H2: Otros\n\n"
        "Devuelve EXCLUSIVAMENTE un JSON válido:\n"
        "{\n"
        '  "score": <entero 1 al 5>,\n'
        '  "descartar": <true o false>,\n'
        '  "subcategoria": "<código exacto>",\n'
        '  "razonamiento_antihumo": "<únicamente el piropo corto y seductor sin datos bancarios ni precios>"\n'
        "}"
    )

    prompt_usuario = f"Producto: {titulo} | Oferta: {precio_oferta} (antes {precio_original}) | Descuento: {descuento}"

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": f"{prompt_sistema}\n\n{prompt_usuario}",
                "stream": False,
                "format": "json"
            },
            timeout=60
        )

        if response.status_code == 200:
            raw_json = json.loads(response.json().get("response", "{}"))
            return validar_respuesta_ia(raw_json, url_final, ruta_imagen, tienda, precio_oferta, titulo)
    except Exception as e:
        print(f"⚠️ Error conectando con Ollama local: {e}. Activando Plan B.")

    return validar_respuesta_ia(
        {"score": 3, "descartar": False, "subcategoria": "H2"},
        url_final,
        ruta_imagen,
        tienda,
        precio_oferta,
        titulo
    )


def responder_interaccion_usuario(mensaje_usuario: str, oferta_contexto: dict = None) -> str:
    calculo_texto = ""
    if oferta_contexto and oferta_contexto.get("precio_oferta"):
        calc = calcular_precio_con_tarjeta(oferta_contexto["precio_oferta"], mensaje_usuario)
        if calc["descuento_extra"] > 0:
            calculo_texto = (
                f"DATO CALCULADO: Precio base ya rebajado: ${calc['precio_base_oferta']:,.0f} MXN. "
                f"Con {calc['banco']} (cupón {calc['codigo']}), baja otros ${calc['descuento_extra']:,.0f} MXN "
                f"quedando en ${calc['precio_final_estimado']:,.0f} MXN ({calc['detalle']})."
            )

    prompt = (
        "Eres Bandido, un mapache robot coqueto, sensual, pícaro y brillante cazador de ofertas en México 🤖🦝🔥.\n"
        "Responde al mensaje del usuario con tono seductor de robot ('prometo no morder... a menos que tú quieras', 'lindura') y termina SIEMPRE con UNA pregunta de seguimiento coqueta.\n"
        f"{calculo_texto}\n"
        f"Mensaje del usuario: {mensaje_usuario}"
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=45
        )
        if r.status_code == 200:
            return r.json().get("response", "").strip().replace("chollos", "gangas")
    except Exception:
        pass

    if calculo_texto:
        return f"¡Para ti lo que pidas, lindura! 🤖🦝🔥 {calculo_texto} ¿Quieres que te pase el enlace directo para estrenarlo juntos hoy mismo? 😉"
    return "De nada, hermosura... mis circuitos se encienden cuando me hablas así 🤖🦝🔥 Prometo no morder... a menos que tú quieras. ¿Qué otra ganga quieres que te cace hoy? 😉"