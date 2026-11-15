import json
import random
import requests
from cfg import OLLAMA_URL, MODELO_AUDITOR, MODELO_VENDEDOR, CODIGOS_CAT, WORKER_URL
from calc import auditar_numeros, calcular_tarjeta

ESTILOS = [
    "ladrón nocturno elegante y pícaro que presume el botín que acaba de conseguir",
    "cómplice callejero astuto que te pasa el dato secreto antes de que suba de precio",
    "galán magnético y juguetón que te reta a estrenar esa joya hoy mismo"
]

def limpiar_prohibidas(texto: str) -> str:
    return (
        texto.replace("chollos", "gangas")
             .replace("chollo", "ganga")
             .replace("Chollos", "Gangas")
             .replace("Chollo", "Ganga")
    )

def auditar(oferta_bruta: dict) -> dict:
    """CEREBRO 1: Auditor financiero frío (temperatura 0.1, JSON estricto)."""
    nums = auditar_numeros(oferta_bruta)
    if nums["anomalia"]:
        return {
            "descartar": True,
            "score": 5,
            "subcategoria": "H2",
            "razonamiento": nums["motivo"],
            "numeros": nums
        }

    titulo = oferta_bruta.get("titulo", "")
    tienda = oferta_bruta.get("tienda", "")
    p_of = nums["precio_oferta"]
    p_or = nums["precio_original"]
    pct = nums["pct_real"]

    prompt = (
        "Eres un auditor de precios de comercio electrónico en México.\n"
        "Evalúa esta oferta y responde SOLO con un JSON válido:\n"
        "Escala de score (1 es la mejor oferta, 5 es la peor):\n"
        "1 = Oferta histórica real (descuento fuerte y producto deseable)\n"
        "2 = Muy buena oferta real\n"
        "3 = Oferta decente / precio competitivo\n"
        "4 = Descuento flojo\n"
        "5 = Humo, accesorio engañoso o sobreprecio\n\n"
        "Categorías válidas: A1-A2 (Audio), B1-B4 (Videojuegos), C1-C3 (Hogar), "
        "D1-D2 (Celulares), E1-E3 (Computación), F1-F2 (Deportes), G1-G2 (Herramientas), H1-H2 (General).\n\n"
        f"Producto: {titulo}\n"
        f"Tienda: {tienda}\n"
        f"Precio oferta: ${p_of:,.2f} MXN | Precio antes: ${p_or:,.2f} MXN | Descuento real: {pct}%\n\n"
        'Formato exacto: {"score": 2, "descartar": false, "subcategoria": "E1", "razonamiento": "frase corta de máximo 18 palabras"}'
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_AUDITOR,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 120}
            },
            timeout=30
        )
        if r.status_code == 200:
            data = json.loads(r.json().get("response", "{}"))
            score = int(data.get("score", 3))
            if not (1 <= score <= 5):
                score = 3
            subcat = str(data.get("subcategoria", "H2")).strip().upper()
            if subcat not in CODIGOS_CAT:
                subcat = "H2"
            descartar = bool(data.get("descartar", False)) or score == 5
            razon = limpiar_prohibidas(str(data.get("razonamiento", "Oferta validada.")))
            return {
                "descartar": descartar,
                "score": score,
                "subcategoria": subcat,
                "razonamiento": razon,
                "numeros": nums
            }
    except Exception as e:
        print(f"⚠️ [MIND AUDITOR ERROR]: {e}")

    # Respaldo matemático si Ollama tarda o falla
    score_fb = 1 if pct >= 35 else (2 if pct >= 22 else (3 if pct >= 12 else 4))
    return {
        "descartar": False,
        "score": score_fb,
        "subcategoria": "H2",
        "razonamiento": f"Ahorro real del {pct}% verificado en {tienda}.",
        "numeros": nums
    }

def vender(mensaje_usuario: str, oferta: dict | None) -> str:
    """CEREBRO 2: Vendedor pícaro y seductor (escala alineada 1=Mejor)."""
    if not oferta:
        return (
            f"🦝💨 ¡Ay, cómplice! Ese tesoro ya voló de mis manos... "
            f"pero date una vuelta por mi guarida que acabo de meter mercancía fresca:\n{WORKER_URL} 😏💎"
        )

    link = oferta.get("url_afiliado") or WORKER_URL
    titulo = oferta.get("titulo", "esta joya")
    score = int(oferta.get("score", 3))

    if score <= 2:
        veredicto = "Joyita verificada a precio mínimo real 🔥."
    elif score == 3:
        veredicto = "Buen precio directo, y con tarjeta bancaria queda todavía más sabroso."
    else:
        veredicto = "Descuento ligero, conviene solo si aplicas bonificación de tu banco."

    pide_precio = any(w in mensaje_usuario.lower() for w in [
        "cuanto", "cuánto", "precio", "cuesta", "pago", "tarjeta",
        "banco", "meses", "msi", "bbva", "banamex", "santander", "hsbc", "banorte", "nu", "mercado pago"
    ])

    if pide_precio:
        calc = calcular_tarjeta(oferta, mensaje_usuario)
        regla_dinero = f"El usuario preguntó por precio/banco. Menciona este monto exacto: ${calc['precio_final']:,.0f} MXN ({calc['detalle']})."
    else:
        regla_dinero = "NO menciones precios ni números en pesos; enfócate en el deseo y la experiencia de tener el producto."

    estilo = random.choice(ESTILOS)
    prompt = (
        "Eres Bandido, un mapache astuto, seductor y el mejor cazador de ofertas de México 🦝🔥.\n"
        f"Personalidad en este turno: {estilo}.\n"
        f"Regla financiera: {regla_dinero}\n"
        "Reglas estrictas:\n"
        "- Máximo 55 palabras, directo, magnético y sin sonar a robot.\n"
        "- PROHIBIDO usar la palabra 'chollo' o 'chollos'.\n"
        "- PROHIBIDO inventar precios o especificaciones técnicas.\n"
        f"- Termina SIEMPRE incluyendo este enlace exacto: {link}\n\n"
        f"Producto: {titulo}\n"
        f"Nota interna: {veredicto}\n"
        f"Comentario del usuario: {mensaje_usuario}"
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_VENDEDOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.8, "num_predict": 130}
            },
            timeout=35
        )
        if r.status_code == 200:
            resp = limpiar_prohibidas(r.json().get("response", "").strip())
            if resp:
                if link not in resp:
                    resp += f"\n\n👉 Atrápalo aquí: {link}"
                return resp
    except Exception as e:
        print(f"⚠️ [MIND VENDEDOR ERROR]: {e}")

    return f"🦝🔥 ¡Qué buen ojo tienes! {veredicto}\nÉchale el guante antes de que vuele:\n{link} 😏✨"