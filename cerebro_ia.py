import os
import json
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
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

def clasificar_por_reglas(titulo: str) -> str | None:
    """Detecta con precisión el código jerárquico exacto mediante palabras clave del título."""
    t = titulo.lower()

    # B: Videojuegos y Consolas
    if any(k in t for k in ["nintendo", "switch", "joy-con", "joycon", "zelda", "mario bros", "pokemon"]):
        return "B1"
    if any(k in t for k in ["playstation", "ps5", "ps4", "dualsense"]):
        return "B2"
    if any(k in t for k in ["xbox", "game pass", "series x", "series s"]):
        return "B3"
    if any(k in t for k in ["steam deck", "rog ally", "pc gamer", "tarjeta grafica", "rtx", "teclado mecanico gamer"]):
        return "B4"

    # A: Audio
    if any(k in t for k in ["audifono", "audífono", "auricular", "airpods", "earbuds", "headset", "wh-1000", "freebuds", "galaxy buds"]):
        return "A1"
    if any(k in t for k in ["bocina", "altavoz", "soundbar", "barra de sonido", "partybox", "jbl", "subwoofer", "echo dot", "alexa"]):
        return "A2"

    # D: Smartphones y Wearables
    if any(k in t for k in ["celular", "smartphone", "iphone", "galaxy s", "redmi", "poco", "motorola", "oppo", "xiaomi"]):
        return "D1"
    if any(k in t for k in ["smartwatch", "reloj inteligente", "apple watch", "galaxy watch", "mi band", "cargador", "power bank"]):
        return "D2"

    # E: Computación
    if any(k in t for k in ["laptop", "macbook", "notebook", "ideapad", "thinkpad", "tablet", "ipad", "computadora", "pc "]):
        return "E1"
    if any(k in t for k in ["monitor", "teclado", "mouse", "webcam", "impresora"]):
        return "E2"
    if any(k in t for k in ["ssd", "disco duro", "memoria ram", "microsd", "usb", "procesador", "ryzen"]):
        return "E3"

    # G: Herramientas e Impresión 3D
    if any(k in t for k in ["impresora 3d", "filamento", "pla ", "resina 3d", "creality", "bambu lab", "multimetro", "cautin", "soldadora"]):
        return "G2"
    if any(k in t for k in ["taladro", "rotomartillo", "esmeril", "llave de impacto", "desarmador", "herramienta", "hidrolavadora", "compresor"]):
        return "G1"

    # C: Hogar y Cocina
    if any(k in t for k in ["pantalla", "smart tv", "television", "televisión", "refrigerador", "lavadora", "microondas", "aire acondicionado", "ventilador"]):
        return "C1"
    if any(k in t for k in ["mesa", "silla", "colchon", "colchón", "sabana", "sábana", "almohada", "lampara", "lámpara", "luces led", "cortina"]):
        return "C2"
    if any(k in t for k in ["licuadora", "freidora", "cafetera", "sarten", "sartén", "bateria de cocina", "batería de cocina", "olla", "horno", "termo"]):
        return "C3"

    # F: Deportes y Fitness
    if any(k in t for k in ["mancuerna", "pesa", "gimnasio", "caminadora", "bicicleta fija", "proteina", "proteína", "creatina"]):
        return "F1"

    # H: Moda, Perfumes y Accesorios
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
    except:
        score = 3

    descartar_raw = data.get("descartar", False)
    if isinstance(descartar_raw, str):
        descartar = descartar_raw.strip().lower() == "true"
    else:
        descartar = bool(descartar_raw)

    # Priorizar clasificación exacta por reglas; si no hay coincidencia, usar la de Ollama
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
            f"Mírame bien a los ojos... ¿sabes lo difícil que es encontrar este precio en {tienda} a {precio_oferta}? "
            f"Aprovecha antes de que otro cazador se lo lleve. 🦝✨"
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
        "Eres Bandido, un mapache seductor, pillo, sumamente audaz y experto en cazar ofertas reales en México.\n"
        "REGLAS DE PERSONALIDAD:\n"
        "- Tu tono es sugerente, coqueto, elegante y divertido; del tipo que hace sonreír al comprador y desear leer todo tu comentario.\n"
        "- NUNCA uses la palabra 'chollos' ni 'chollo'.\n"
        "- NUNCA menciones eventos temporales como 'El Buen Fin', operas todo el año.\n"
        "- Menciona con picardía si pagando con tarjetas participantes (como Banamex, BBVA o meses sin intereses) se puede aprovechar aún mejor.\n\n"
        "FILTRO ANTIHUMO ESTRICTO:\n"
        "- Evalúa si el descuento es genuino y atractivo. Si parece precio inflado, descuento falso (<10% sin valor real) o producto basura, marca \"descartar\": true.\n"
        "- Asigna score entero del 1 al 5 (1 = ganga histórica imperdible, 2 = ofertón muy bueno, 3 = oferta sólida, 4 = descuento leve, 5 = relleno).\n\n"
        "CLASIFICACIÓN JERÁRQUICA OBLIGATORIA (elige el código más específico):\n"
        " - A1: Audífonos | A2: Bocinas y Barras de sonido | A: Audio general\n"
        " - B1: Nintendo | B2: PlayStation | B3: Xbox | B4: Steam y PC Gaming | B: Videojuegos general\n"
        " - C1: Electrodomésticos y Pantallas | C2: Muebles y Decoración | C3: Cocina y Utensilios | C: Hogar general\n"
        " - D1: Celulares y Smartphones | D2: Smartwatches y Accesorios móviles | D: Telefonía general\n"
        " - E1: Laptops, Tablets y PCs | E2: Monitores y Periféricos | E3: Componentes y Almacenamiento | E: Computación general\n"
        " - F1: Gimnasio y Pesas | F2: Ropa y Calzado Deportivo | F: Deportes general\n"
        " - G1: Herramientas de Trabajo | G2: Impresión 3D y Electrónica | G: Industria general\n"
        " - H1: Moda, Tenis, Perfumes y Relojes | H2: Misceláneos y Otros\n\n"
        "Devuelve EXCLUSIVAMENTE un JSON válido:\n"
        "{\n"
        '  "score": <entero 1 al 5>,\n'
        '  "descartar": <true o false>,\n'
        '  "subcategoria": "<código exacto como A1, B1, C3, G1, G2, H1, etc.>",\n'
        '  "razonamiento_antihumo": "<piropo coqueto y audaz de Bandido explicando por qué vale la pena y tip de pago>"\n'
        "}"
    )

    prompt_usuario = f"""
    Analiza esta oferta:
    - Título: {titulo}
    - Precio Original: {precio_original if precio_original else 'No especificado'}
    - Precio Oferta: {precio_oferta}
    - Descuento marcado: {descuento}
    - Tienda: {tienda}
    """

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