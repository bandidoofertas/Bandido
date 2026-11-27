import asyncio
from datetime import datetime
import hashlib
import json
import random
import re
import subprocess
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from cfg import PROF_FB_CHAT, WORKER_URL, get_db, init_db
from mind import (
    vender, extraer_url_tienda, evaluar_mensaje_omega, generar_advertencia_omega
)
from calc import detectar_banco
from browser_queue import adquirir_perfil_navegador

BASE_DIR = Path(__file__).resolve().parent
PROF_WHATSAPP = BASE_DIR / "prof_whatsapp"
ADMIN_WHATSAPP_NUM = "5615585886"

# Interruptor temporal de Protocolo Omega (False = apagado)
PROTOCOLO_OMEGA_ACTIVO = False

MODO_CHAT = "AUTO"
PAUSA_RAPIDO_SEG = 150
PAUSA_PASIVO_SEG = 780

POSTS_JSON = BASE_DIR / "posts_activos.json"
API_D1_OFERTAS = f"{WORKER_URL.rstrip('/')}/api/ofertas"

SINONIMOS_PRODUCTO = {
    "reloj": ["reloj", "smartwatch", "watch", "band", "pulsera", "bulova", "huawei"],
    "audifonos": ["audifonos", "audífonos", "earbuds", "airpods", "headset", "diadema", "iem", "kz"],
    "bocina": ["bocina", "altavoz", "speaker", "partybox", "soundbar", "barra"],
    "instrumento": ["guitarra", "bajo", "teclado", "piano", "sintetizador", "ukelele", "bateria", "microfono"],
    "laptop": ["laptop", "computadora", "compu", "notebook", "macbook", "pc"],
    "celular": ["celular", "telefono", "teléfono", "smartphone", "iphone", "samsung", "xiaomi", "oppo", "motorola", "tablet", "ipad"],
    "tele": ["tele", "television", "televisión", "pantalla", "tv", "smart tv", "dron", "alexa"],
    "juego": ["juego", "videojuego", "videojuegos", "consola", "switch", "nintendo", "ps5", "ps4", "playstation", "xbox", "dualsense", "joycon", "zelda", "mario", "pokemon", "smash"],
    "taladro": ["taladro", "rotomartillo", "herramienta", "desarmador", "llave", "hidrolavadora"],
    "freidora": ["freidora", "air fryer", "horno", "cafetera", "licuadora", "tupper"],
    "silla": ["silla", "ejecutiva", "ergonomica", "ergonómica", "gamer", "escritorio", "sillon", "sillón"],
    "tenis": ["tenis", "zapato", "zapatos", "calzado", "nike", "adidas", "puma", "correr", "running", "maleta"],
    "personal": ["shampoo", "jabon", "crema", "serum", "perfume", "condon", "condones", "preservativo"]
}

STOPWORDS_CHAT = {
    "como", "cómo", "puedo", "comprar", "cuanto", "cuánto", "cuesta", "precio", "tiene",
    "tarjeta", "banco", "info", "informacion", "información", "link", "enlace", "quiero",
    "para", "este", "esta", "enviar", "mensaje", "interesa", "esa", "ese", "tal", "hay",
    "tienes", "disponible", "busco", "buscando", "favor", "por", "los", "las", "del", "una",
    "uno", "unos", "unas", "edicion", "edición", "con", "sin", "que", "qué", "pasa", "dame",
    "especial", "busca", "tengo", "aplica", "bonificacion", "bonificación", "donde", "dónde"
}

NOMBRES_MUJER_COMUNES = {
    "maria", "maría", "dora", "ana", "laura", "patricia", "carmen", "rosa", "guadalupe",
    "sofia", "sofía", "andrea", "fernanda", "daniela", "paola", "gabriela", "alejandra",
    "veronica", "verónica", "adriana", "monica", "mónica", "claudia", "silvia", "leticia",
    "martha", "marta", "elena", "lucia", "lucía", "valeria", "camila", "mariana", "karla",
    "jessica", "brenda", "diana", "rocio", "rocío", "irma", "blanca", "teresa", "alma",
    "norma", "yolanda", "beatriz", "alicia", "sandra", "lizbeth", "araceli", "esmeralda"
}

NOMBRES_HOMBRE_COMUNES = {
    "juan", "jose", "josé", "luis", "carlos", "jorge", "miguel", "jesus", "jesús",
    "alejandro", "francisco", "antonio", "pedro", "manuel", "roberto", "eduardo",
    "fernando", "ricardo", "daniel", "javier", "rafael", "david", "arturo", "sergio",
    "enrique", "mario", "oscar", "óscar", "raul", "raúl", "hector", "héctor", "alberto",
    "angel", "ángel", "ivan", "iván", "diego", "cesar", "césar", "fabian", "fabián"
}


def obtener_modo_activo() -> tuple[str, int]:
    modo = MODO_CHAT.upper().strip()
    if modo == "AUTO":
        ahora = datetime.now()
        m, d = ahora.month, ahora.day
        es_pico = (
            (m == 11 and 24 <= d <= 30) or
            (m == 12 and d <= 2) or
            (m == 12 and 18 <= d <= 24) or
            (m == 5 and 15 <= d <= 31) or
            (m == 7 and 8 <= d <= 22) or
            (d in (14, 15, 16, 29, 30, 31, 1))
        )
        modo = "RAPIDO" if es_pico else "PASIVO"

    if modo == "RAPIDO":
        espera = PAUSA_RAPIDO_SEG + random.randint(-30, 60)
        return "RAPIDO", max(110, espera)

    espera = PAUSA_PASIVO_SEG + random.randint(-60, 120)
    return "PASIVO", espera


def inferir_genero_usuario(autor: str, comentario: str) -> str:
    c = comentario.lower()
    if any(re.search(rf"\b{w}\b", c) for w in ("mujer", "dama", "ella", "femenino")):
        return "M"
    if any(re.search(rf"\b{w}\b", c) for w in ("hombre", "caballero", "varon", "varón", "masculino")):
        return "H"
    primer_nombre = (autor.strip().split()[0].lower() if autor.strip() else "")
    if primer_nombre in NOMBRES_MUJER_COMUNES:
        return "M"
    if primer_nombre in NOMBRES_HOMBRE_COMUNES:
        return "H"
    return "U"


def liberar_perfil_navegador(ruta_perfil: Path):
    try:
        cmd = (
            f"Get-CimInstance Win32_Process -Filter \"name = 'chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{ruta_perfil.name}*' }} | "
            f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=8)
        for lock in ruta_perfil.glob("Singleton*"):
            lock.unlink(missing_ok=True)
    except Exception:
        pass


def asegurar_tablas_chat():
    init_db()
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS respuestas_fb (
                cid TEXT PRIMARY KEY,
                url_post TEXT,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(respuestas_fb)").fetchall()]
        if "fecha" not in cols:
            conn.execute("ALTER TABLE respuestas_fb ADD COLUMN fecha DATETIME DEFAULT CURRENT_TIMESTAMP")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS historial_comentarios_fb (
                cid TEXT PRIMARY KEY,
                url_post TEXT,
                autor TEXT,
                comentario TEXT,
                respuesta TEXT,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts_comentados_web (
                url_post TEXT PRIMARY KEY,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios_omega (
                autor_norm TEXT PRIMARY KEY,
                autor_original TEXT,
                strikes INTEGER DEFAULT 0,
                baneado INTEGER DEFAULT 0,
                ultimo_motivo TEXT,
                ultimo_mensaje TEXT,
                url_post TEXT,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


def post_ya_tiene_comentario_web(url_post: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM posts_comentados_web WHERE url_post = ?", (url_post,)).fetchone()
        if row:
            return True
        m = re.search(r"(\d{15,20})", url_post)
        if m:
            row2 = conn.execute("SELECT 1 FROM posts_comentados_web WHERE url_post LIKE ?", (f"%{m.group(1)}%",)).fetchone()
            if row2:
                return True
    return False


def marcar_post_con_comentario_web(url_post: str):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO posts_comentados_web (url_post, fecha) VALUES (?, CURRENT_TIMESTAMP)",
            (url_post,)
        )


def obtener_estado_omega_usuario(autor: str) -> tuple[int, bool]:
    if not PROTOCOLO_OMEGA_ACTIVO:
        return 0, False
    autor_norm = re.sub(r"\s+", " ", autor.strip().lower())
    with get_db() as conn:
        row = conn.execute(
            "SELECT strikes, baneado FROM usuarios_omega WHERE autor_norm = ?",
            (autor_norm,)
        ).fetchone()
        if row:
            return int(row["strikes"] or 0), bool(row["baneado"])
    return 0, False


def registrar_strike_omega(autor: str, motivo: str, mensaje: str, url_post: str) -> tuple[int, bool]:
    autor_norm = re.sub(r"\s+", " ", autor.strip().lower())
    strikes_prev, _ = obtener_estado_omega_usuario(autor)
    nuevos_strikes = strikes_prev + 1
    baneado = 1 if nuevos_strikes >= 2 else 0
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO usuarios_omega (
                autor_norm, autor_original, strikes, baneado, ultimo_motivo, ultimo_mensaje, url_post, fecha
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (autor_norm, autor, nuevos_strikes, baneado, motivo, mensaje, url_post))
    return nuevos_strikes, bool(baneado)


async def notificar_omega_whatsapp(autor: str, url_post: str, motivo: str, mensaje: str):
    if not PROTOCOLO_OMEGA_ACTIVO or not PROF_WHATSAPP.exists():
        return False

    liberar_perfil_navegador(PROF_WHATSAPP)
    texto_alerta = (
        f"🚨 PROTOCOLO OMEGA — USUARIO BLOQUEADO\n"
        f"👤 Usuario: {autor}\n"
        f"🔗 Post: {url_post}\n"
        f"🚫 Motivo: {motivo}\n"
        f"💬 Mensaje: {mensaje[:120]}"
    )

    async with adquirir_perfil_navegador(PROF_WHATSAPP, origen="omega_wa"):
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(PROF_WHATSAPP),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--window-position=-32000,-32000"
                ],
                viewport={"width": 1280, "height": 850},
                locale="es-MX",
                timezone_id="America/Mexico_City"
            )
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            try:
                await page.goto("https://web.whatsapp.com", timeout=45000, wait_until="domcontentloaded")
                buscador = page.locator(
                    "div[contenteditable='true'][data-tab='3'], "
                    "div[role='textbox'][aria-label*='Buscar'], "
                    "div[contenteditable='true']"
                ).first
                await buscador.wait_for(state="visible", timeout=35000)
                await buscador.click()
                await page.wait_for_timeout(700)
                await page.keyboard.insert_text(ADMIN_WHATSAPP_NUM)
                await page.wait_for_timeout(2200)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1500)

                caja_msg = page.locator(
                    "footer div[contenteditable='true'][data-tab='10'], "
                    "footer div[contenteditable='true'][role='textbox'], "
                    "div[contenteditable='true'][aria-label*='Escribe un mensaje']"
                ).last
                await caja_msg.wait_for(state="visible", timeout=15000)
                await caja_msg.click()
                await page.wait_for_timeout(500)

                lineas = texto_alerta.split("\n")
                for i, linea in enumerate(lineas):
                    await page.keyboard.insert_text(linea)
                    if i < len(lineas) - 1:
                        await page.keyboard.down("Shift")
                        await page.keyboard.press("Enter")
                        await page.keyboard.up("Shift")
                        await page.wait_for_timeout(150)

                await page.wait_for_timeout(700)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(4000)
                return True
            except Exception as e:
                print(f"❌ [OMEGA WA ERROR]: {e}")
                return False
            finally:
                await ctx.close()


async def ocultar_comentario_fb(page, comment_id: str) -> bool:
    if not PROTOCOLO_OMEGA_ACTIVO:
        return False
    try:
        nodo_com = page.locator(f"[data-bandido-comment-id='{comment_id}']").first
        if await nodo_com.count() == 0:
            return False

        await nodo_com.scroll_into_view_if_needed()
        await nodo_com.hover()
        await page.wait_for_timeout(700)

        btn_menu = nodo_com.locator(
            "div[aria-label*='Ocultar o reportar'], "
            "div[aria-label*='Más opciones'], "
            "div[aria-label*='Acciones para este comentario'], "
            "div[role='button'][aria-haspopup='menu']"
        ).last

        if await btn_menu.count() == 0:
            return False

        await btn_menu.click(force=True)
        await page.wait_for_timeout(1200)

        opcion_ocultar = page.locator(
            "[role='menuitem']:has-text('Ocultar comentario'), "
            "span:has-text('Ocultar comentario')"
        ).first
        if await opcion_ocultar.count() > 0:
            await opcion_ocultar.click(force=True)
            await page.wait_for_timeout(1500)
            return True
    except Exception:
        pass
    return False


def es_autor_propio(autor: str, texto_bruto: str = "") -> bool:
    a = (autor or "").strip().lower()
    t = (texto_bruto or "").strip().lower()
    url_web = WORKER_URL.lower().replace("https://", "").replace("http://", "").rstrip("/")
    if not a:
        return True
    if "bandido ofertas" in a or a.startswith("bandido"):
        return True
    if "bandido ofertas" in t[:60] or t.startswith("🦝"):
        return True
    if url_web and url_web in t:
        return True
    if "pase directo en" in t or "catálogo en vivo" in t or "guarida en vivo" in t:
        return True
    return False


async def enviar_respuesta_con_mencion(page, btn_reply, autor: str, respuesta: str) -> str:
    if es_autor_propio(autor):
        print(f"🚨 [CHAT AUTO-TAG CANCELADO] Intento bloqueado antes de abrir caja: autor propio '{autor}'.")
        return "AUTO_TAG_CANCELADO"

    try:
        cajas_antes = await page.locator("div[role='textbox'][contenteditable='true']").count()

        await btn_reply.scroll_into_view_if_needed()
        await page.wait_for_timeout(random.randint(700, 1100))
        await btn_reply.click(force=True)
        await page.wait_for_timeout(random.randint(1800, 2500))

        caja_activa = page.locator("div[role='textbox'][contenteditable='true']:focus").first
        if await caja_activa.count() == 0:
            cajas_despues = page.locator("div[role='textbox'][contenteditable='true']")
            total_despues = await cajas_despues.count()
            if total_despues > cajas_antes:
                caja_activa = cajas_despues.nth(total_despues - 1)
            elif total_despues > 0:
                caja_activa = cajas_despues.last

        if await caja_activa.count() == 0:
            print(f"   ⚠️ [CHAT AVISO] No se abrió la caja de respuesta para {autor}.")
            return "ERROR"

        await caja_activa.scroll_into_view_if_needed()
        await caja_activa.click(force=True)
        await page.wait_for_timeout(600)

        info_caja = await caja_activa.evaluate("""(el) => {
            const txt = (el.innerText || el.textContent || '').trim();
            const aria = (el.getAttribute('aria-label') || '').trim();
            return { txt, aria };
        }""")

        txt_caja_low = (info_caja.get("txt") or "").lower()
        aria_caja_low = (info_caja.get("aria") or "").lower()

        if (
            "bandido ofertas" in txt_caja_low
            or "@bandido" in txt_caja_low
            or "respondiendo a bandido" in aria_caja_low
            or "responder a bandido" in aria_caja_low
        ):
            print(f"🚨 [CHAT AUTO-TAG CANCELADO] Facebook intentó etiquetar a 'Bandido Ofertas'. Respuesta cancelada.")
            await page.keyboard.press("Control+a")
            await page.wait_for_timeout(150)
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(200)
            await page.keyboard.press("Escape")
            return "AUTO_TAG_CANCELADO"

        texto_final = " ".join((respuesta or "").split()).strip()
        if not texto_final or "bandido ofertas" in texto_final[:40].lower():
            return "AUTO_TAG_CANCELADO"

        await page.keyboard.insert_text(texto_final)
        await page.wait_for_timeout(random.randint(1400, 2100))

        texto_pre_envio = ((await caja_activa.inner_text()) or "").lower()
        if "bandido ofertas" in texto_pre_envio or "@bandido" in texto_pre_envio:
            await page.keyboard.press("Control+a")
            await page.wait_for_timeout(150)
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(200)
            await page.keyboard.press("Escape")
            return "AUTO_TAG_CANCELADO"

        enviado_por_boton = False
        try:
            form_padre = caja_activa.locator("xpath=ancestor::form[1]")
            if await form_padre.count() > 0:
                btn_enviar = form_padre.locator(
                    "div[aria-label='Comentar'][role='button'], "
                    "div[aria-label='Responder'][role='button'], "
                    "div[aria-label='Enviar'][role='button'], "
                    "button[type='submit']"
                ).last
                if await btn_enviar.count() > 0 and await btn_enviar.is_visible():
                    await btn_enviar.click(force=True)
                    enviado_por_boton = True
        except Exception:
            pass

        if not enviado_por_boton:
            await caja_activa.focus()
            await page.wait_for_timeout(250)
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(4500)

        texto_restante = ""
        try:
            if await caja_activa.count() > 0:
                texto_restante = (await caja_activa.inner_text() or "").strip()
        except Exception:
            texto_restante = ""

        if texto_restante and texto_final[:20] in texto_restante:
            await caja_activa.click(force=True)
            await page.wait_for_timeout(300)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(4500)
            try:
                texto_restante = (await caja_activa.inner_text() or "").strip()
            except Exception:
                texto_restante = ""

        if texto_restante and texto_final[:20] in texto_restante:
            print(f"   ⚠️ [CHAT AVISO] Facebook retuvo el texto en la caja para {autor}; se reintentará.")
            return "ERROR"

        return "OK"
    except Exception as e:
        print(f"   ⚠️ [CHAT ENVÍO ERROR] Fallo al responder a {autor}: {e}")
        return "ERROR"


def consultar_catalogo_d1() -> list[dict]:
    try:
        r = requests.get(API_D1_OFERTAS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("ofertas", "results", "data", "items"):
                    if isinstance(data.get(key), list):
                        return data[key]
    except Exception as e:
        print(f"⚠️ [CHAT D1 ERROR] No se pudo consultar Cloudflare D1: {e}")
    return []


def es_url_post_valida(url: str) -> bool:
    if not isinstance(url, str):
        return False
    u = url.strip()
    if "\n" in u or "\r" in u or " " in u:
        return False
    if u in {"https://www.facebook.com", "https://www.facebook.com/", "http://www.facebook.com"}:
        return False
    return bool(re.match(r"^https?://(www\.|m\.)?facebook\.com/.+", u))


def leer_posts_activos() -> list[str]:
    if not POSTS_JSON.exists():
        return []
    try:
        data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []

        limpias = []
        for item in data:
            if es_url_post_valida(item):
                u = item.strip()
                if u not in limpias:
                    limpias.append(u)

        limpias = limpias[:12]
        if len(limpias) != len(data):
            POSTS_JSON.write_text(json.dumps(limpias, ensure_ascii=False, indent=2), encoding="utf-8")
        return limpias
    except Exception as e:
        print(f"⚠️ [CHAT JSON ERROR] No se pudo leer posts_activos.json: {e}")
    return []


def obtener_ofertas_por_url(url_post: str) -> list:
    with get_db() as conn:
        row = conn.execute("SELECT ofertas_json FROM posts_fb WHERE url_post = ?", (url_post,)).fetchone()
        if not row:
            m = re.search(r"(\d{15,20})", url_post)
            if m:
                row = conn.execute("SELECT ofertas_json FROM posts_fb WHERE url_post LIKE ?", (f"%{m.group(1)}%",)).fetchone()
        if row and row["ofertas_json"]:
            try:
                return json.loads(row["ofertas_json"])
            except Exception:
                pass
        return []


def calcular_cids(url_post: str, autor: str, mensaje: str) -> list[str]:
    norm_autor = re.sub(r"\s+", " ", autor.strip().lower())
    norm_msg = re.sub(r"\s+", " ", mensaje.strip().lower())
    cid_norm = hashlib.sha256(f"{url_post}|{norm_autor}|{norm_msg}".encode("utf-8")).hexdigest()
    cid_exact = hashlib.sha256(f"{url_post}|{autor}|{mensaje}".encode("utf-8")).hexdigest()
    return list({cid_norm, cid_exact})


def ya_respondido_db(cids: list[str]) -> bool:
    with get_db() as conn:
        for cid in cids:
            row = conn.execute(
                "SELECT 1 FROM respuestas_fb WHERE cid = ? AND (fecha IS NULL OR fecha > datetime('now', '-30 minutes'))",
                (cid,)
            ).fetchone()
            if row is not None:
                return True
    return False


def guardar_respuesta(cids: list[str], url_post: str, autor: str, comentario: str, respuesta: str):
    with get_db() as conn:
        for cid in cids:
            conn.execute(
                "INSERT OR REPLACE INTO respuestas_fb (cid, url_post, fecha) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (cid, url_post)
            )
        conn.execute(
            "INSERT OR REPLACE INTO historial_comentarios_fb (cid, url_post, autor, comentario, respuesta, fecha) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (cids[0], url_post, autor, comentario, respuesta)
        )


def extraer_palabras_clave_reales(texto: str) -> tuple[set[str], set[str]]:
    limpio = re.sub(r"[^\w\sáéíóúñ]", " ", texto.lower())
    base = {p for p in limpio.split() if len(p) > 2 and p not in STOPWORDS_CHAT}
    expandidas = set(base)
    for palabra in base:
        for grupo in SINONIMOS_PRODUCTO.values():
            if palabra in grupo:
                expandidas.update(grupo)
    return base, expandidas


def buscar_coincidencia_real(comentario: str, productos: list, es_post: bool = True, genero_usuario: str = "U") -> dict | None:
    if not productos:
        return None

    c_low = comentario.strip().lower()
    if es_post:
        if re.fullmatch(r"#?\s*([1-5])\s*[.,!]?", c_low):
            idx = int(re.sub(r"\D", "", c_low)) - 1
            if 0 <= idx < len(productos):
                return productos[idx]

        mapa_ord = {
            "1": 0, "primera": 0, "primero": 0, "uno": 0,
            "2": 1, "segunda": 1, "segundo": 1, "dos": 1,
            "3": 2, "tercera": 2, "tercero": 2, "tres": 2,
            "4": 3, "cuarta": 3, "cuarto": 3, "cuatro": 3,
            "5": 4, "quinta": 4, "quinto": 4, "cinco": 4
        }
        for clave, idx in mapa_ord.items():
            if clave.isdigit():
                patron_num = rf"(?:el|la|numero|n?mero|opcion|opci?n|producto|oferta|#)\s*{clave}\b"
            else:
                patron_num = rf"\b{clave}\b"
            if re.search(patron_num, c_low) and idx < len(productos):
                return productos[idx]

    base_usuario, palabras_usuario = extraer_palabras_clave_reales(c_low)

    if es_post and detectar_banco(c_low):
        palabras_sin_banco = {p for p in base_usuario if not detectar_banco(p)}
        if not palabras_sin_banco:
            return productos[0]

    if not base_usuario:
        return productos[0] if es_post and len(productos) == 1 else None

    mejor = None
    max_puntos = 0
    for prod in productos:
        tit = str(prod.get("titulo", "")).lower()
        if not tit:
            continue
        hits_exactos = sum(1 for p in base_usuario if re.search(rf"\b{re.escape(p)}\b", tit))
        if hits_exactos == 0:
            continue

        puntos = sum(
            (2 if p in base_usuario else 1)
            for p in palabras_usuario
            if re.search(rf"\b{re.escape(p)}\b", tit)
        )

        subcat = str(prod.get("subcategoria", "")).upper()
        if subcat.startswith("ROP-"):
            gen_prod = subcat.split("-")[1]
            if gen_prod == genero_usuario and genero_usuario in ("M", "H"):
                puntos += 3
            elif gen_prod in ("M", "H") and genero_usuario in ("M", "H") and gen_prod != genero_usuario:
                puntos -= 2

        if puntos > max_puntos:
            max_puntos = puntos
            mejor = prod

    return mejor if max_puntos >= 2 else None


def limpiar_mensaje_usuario(lineas: list[str], autor: str = "") -> str:
    ruido_ui = {
        "Me gusta", "Responder", "Compartir", "Autor", "Destacado",
        "Editar", "Ocultar", "Enviar mensaje", "Enviar mensa", "Ver traducción",
        "Fan destacado", "Seguir", "MELI.LA", "AMAZON.COM.MX",
        "BANDIDO.BANDIDOOFERTAS.WORKERS.DEV"
    }
    filtradas = []
    for l in lineas:
        s = l.strip()
        if not s or s in ruido_ui or s == autor:
            continue
        if "se eliminó el comentario" in s.lower():
            continue
        s = re.sub(r"^·?\s*\d+\s*(min|h|d|sem|s)\b\.?\s*", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\bEnviar mensa(je)?$", "", s, flags=re.IGNORECASE).strip()
        if s and s not in ruido_ui:
            filtradas.append(s)

    return " ".join(filtradas).strip()


async def publicar_comentario_web_inicial(page, url_post: str) -> bool:
    if post_ya_tiene_comentario_web(url_post):
        return False

    url_web_limpia = WORKER_URL.lower().replace("https://", "").replace("http://", "").rstrip("/")
    ya_en_dom = await page.evaluate(
        """(webHost) => {
            const nodos = Array.from(document.querySelectorAll('div[role="article"], div[aria-label^="Comentario de"]'));
            return nodos.some(el => {
                const txt = (el.innerText || '').toLowerCase();
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                return (aria.includes('bandido ofertas') || txt.includes('bandido ofertas')) && txt.includes(webHost);
            });
        }""",
        url_web_limpia
    )
    if ya_en_dom:
        marcar_post_con_comentario_web(url_post)
        return False

    textos_web = [
        f"🦝🔥 ¿Quieres ver todas las ofertas auditadas en tiempo real sin esperar? Entra directo a mi guarida en vivo: {WORKER_URL} (o comenta el NÚMERO que buscas aquí abajo 👇)",
        f"🦝💎 Catálogo completo actualizado cada 15 min con historial antihumo aquí: {WORKER_URL} — Si quieres el link directo de alguna de estas joyas, comenta su NÚMERO 👇",
        f"🦝✨ ¿Buscas más gangas verificadas o comparar precios antes de comprar? Revisa todas en vivo aquí: {WORKER_URL} (o dime qué número quieres 👇)"
    ]
    comentario_inicial = random.choice(textos_web)

    try:
        caja_principal = page.locator(
            "div[role='textbox'][aria-label*='Comenta como'], "
            "div[role='textbox'][aria-label*='Escribe un comentario'], "
            "div[role='textbox'][contenteditable='true']"
        ).first

        if await caja_principal.count() == 0:
            btn_comentar = page.locator("div[role='button'][aria-label='Comentar'], span:has-text('Comentar')").first
            if await btn_comentar.count() > 0:
                await btn_comentar.click(force=True)
                await page.wait_for_timeout(1500)
                caja_principal = page.locator("div[role='textbox'][contenteditable='true']").first

        if await caja_principal.count() > 0:
            await caja_principal.scroll_into_view_if_needed()
            await page.wait_for_timeout(800)
            await caja_principal.click(force=True)
            await page.wait_for_timeout(1200)
            await page.keyboard.insert_text(comentario_inicial)
            await page.wait_for_timeout(1600)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(4000)

            marcar_post_con_comentario_web(url_post)
            cids_propios = calcular_cids(url_post, "Bandido Ofertas", comentario_inicial)
            guardar_respuesta(cids_propios, url_post, "Bandido Ofertas", "[AUTO-WEB INICIAL]", comentario_inicial)
            print(f"🌐 [CHAT WEB-PIN] Comentario inicial con web publicado en {url_post}")
            return True
    except Exception as e:
        print(f"⚠️ [CHAT WEB-PIN AVISO] No se pudo dejar comentario inicial en {url_post}: {e}")
    return False


async def desplegar_todos_los_comentarios(page):
    try:
        btn_ver_com = page.locator("div[role='button']:has-text('comentario'), span:has-text('comentario')").first
        if await btn_ver_com.count() > 0 and await btn_ver_com.is_visible():
            txt = (await btn_ver_com.inner_text()).lower()
            if re.search(r"\b\d+\s+comentario", txt):
                await btn_ver_com.click(force=True)
                await page.wait_for_timeout(1800)

        filtro_rel = page.locator("span:has-text('Más relevantes'), div[role='button']:has-text('Más relevantes')").first
        if await filtro_rel.count() > 0 and await filtro_rel.is_visible():
            await filtro_rel.click(force=True)
            await page.wait_for_timeout(1200)
            todos_btn = page.locator("span:has-text('Todos los comentarios'), [role='menuitem']:has-text('Todos los comentarios')").first
            if await todos_btn.count() > 0:
                await todos_btn.click(force=True)
                await page.wait_for_timeout(2200)

        for _ in range(3):
            clicked = await page.evaluate(r"""() => {
                let count = 0;
                const candidatos = document.querySelectorAll('div[role="button"], span[role="button"], span');
                for (const el of candidatos) {
                    const txt = (el.innerText || '').trim().toLowerCase();
                    if (!txt || txt.length > 45) continue;
                    if (
                        /^ver\s+.*respuesta/.test(txt) ||
                        /^\d+\s+respuesta/.test(txt) ||
                        /^ver\s+más\s+comentario/.test(txt) ||
                        /^ver\s+comentarios\s+anteriores/.test(txt)
                    ) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            el.click();
                            count++;
                        }
                    }
                }
                return count;
            }""")
            if not clicked:
                break
            await page.wait_for_timeout(1500)
    except Exception:
        pass


async def extraer_comentarios_dom(page) -> list[dict]:
    return await page.evaluate(r"""() => {
        document.querySelectorAll('[data-bandido-reply-id]').forEach(el => el.removeAttribute('data-bandido-reply-id'));
        document.querySelectorAll('[data-bandido-comment-id]').forEach(el => el.removeAttribute('data-bandido-comment-id'));

        const sel = 'div[role="article"], div[aria-label^="Comentario de"], div[aria-label^="Respuesta de"]';
        const nodos = Array.from(document.querySelectorAll(sel));
        const resultados = [];
        const vistosTexto = new Set();
        let seq = 0;

        for (const el of nodos) {
            const aria = el.getAttribute('aria-label') || '';
            const ariaLow = aria.toLowerCase();

            if (/^(?:comentario|respuesta)\s+de\s+bandido/i.test(aria.trim())) continue;

            const botonesReply = Array.from(el.querySelectorAll('div[role="button"], span[role="button"]')).filter(b => {
                const t = (b.innerText || '').trim().toLowerCase();
                if (t !== 'responder') return false;
                return b.closest(sel) === el;
            });

            if (botonesReply.length === 0) continue;

            const dirs = Array.from(el.querySelectorAll('div[dir="auto"]')).filter(d => {
                if (d.closest(sel) !== el) return false;
                if (d.closest('a[target="_blank"]')) return false;
                return true;
            });
            const textoPropio = dirs.map(d => (d.innerText || '').trim()).filter(Boolean).join('\n');
            if (!textoPropio) continue;

            let autorAria = '';
            const mAria = aria.match(/^(?:Comentario|Respuesta)\s+de\s+(.+?)(?:\s+al?\s+|\s+hace\s+|$)/i);
            if (mAria) autorAria = mAria[1].trim();

            const lineas = textoPropio.split('\n').map(x => x.trim()).filter(Boolean);
            const autorFinal = autorAria || (lineas[0] || '');
            if (!autorFinal || autorFinal.toLowerCase().startsWith('bandido')) continue;
            if ((lineas[0] || '').toLowerCase().startsWith('bandido')) continue;

            const huella = (autorFinal + '|' + textoPropio).toLowerCase();
            if (vistosTexto.has(huella)) continue;
            vistosTexto.add(huella);

            // Detectar si es una respuesta a un comentario padre y rescatar el contexto del padre
            const esRespuestaHilo = ariaLow.startsWith('respuesta de') || Boolean(el.parentElement?.closest(sel));
            let contextoPadre = '';
            let autorPadre = '';
            const contenedorHilo = el.closest('li') || el.parentElement?.parentElement || el.parentElement;

            if (esRespuestaHilo && contenedorHilo) {
                const subBloques = Array.from(contenedorHilo.querySelectorAll(sel));
                const padreNodo = subBloques.find(sb => sb !== el && (sb.getAttribute('aria-label') || '').toLowerCase().startsWith('comentario de'));
                if (padreNodo) {
                    const ariaP = padreNodo.getAttribute('aria-label') || '';
                    const mP = ariaP.match(/^Comentario\s+de\s+(.+?)(?:\s+hace\s+|$)/i);
                    if (mP) autorPadre = mP[1].trim();
                    const dirsP = Array.from(padreNodo.querySelectorAll('div[dir="auto"]')).filter(d => d.closest(sel) === padreNodo);
                    contextoPadre = dirsP.map(d => (d.innerText || '').trim()).filter(Boolean).join(' ');
                }
            }

            let yaRespondidoDom = false;
            if (contenedorHilo) {
                const subBloques = Array.from(contenedorHilo.querySelectorAll(sel));
                for (const sb of subBloques) {
                    if (sb === el) continue;
                    const txtSb = (sb.innerText || '');
                    const ariaSb = (sb.getAttribute('aria-label') || '');
                    const esDeBandido = /^(?:comentario|respuesta)\s+de\s+bandido/i.test(ariaSb.trim()) || txtSb.startsWith('Bandido Ofertas');
                    if (esDeBandido) {
                        if (!esRespuestaHilo && ariaLow.startsWith('comentario de')) {
                            yaRespondidoDom = true;
                            break;
                        }
                        if (esRespuestaHilo && txtSb.includes(autorFinal)) {
                            yaRespondidoDom = true;
                            break;
                        }
                    }
                }
            }

            seq += 1;
            const replyId = 'reply_' + seq;
            const commentId = 'comment_' + seq;
            botonesReply[0].setAttribute('data-bandido-reply-id', replyId);
            el.setAttribute('data-bandido-comment-id', commentId);

            resultados.push({
                replyId,
                commentId,
                aria,
                autorFinal,
                textoPropio,
                esRespuestaHilo,
                autorPadre,
                contextoPadre,
                yaRespondidoDom
            });
        }
        return resultados;
    }""")


async def procesar_ronda_chat(page):
    asegurar_tablas_chat()
    urls_posts = leer_posts_activos()

    if not urls_posts:
        print("😴 [CHAT] Sin enlaces válidos en posts_activos.json en este momento.")
        return

    catalogo_d1 = await asyncio.to_thread(consultar_catalogo_d1)
    print(f"☁️ [CHAT D1] Catálogo cargado desde Cloudflare D1: {len(catalogo_d1)} ofertas activas.")

    for url_post in urls_posts:
        print(f"🔎 [CHAT] Revisando comentarios en: {url_post}")
        try:
            try:
                await page.goto(url_post, timeout=40000, wait_until="domcontentloaded")
            except Exception as nav_err:
                if "ERR_NETWORK_IO_SUSPENDED" in str(nav_err):
                    await page.wait_for_timeout(4000)
                    await page.goto(url_post, timeout=40000, wait_until="domcontentloaded")
                else:
                    raise

            await page.wait_for_timeout(random.randint(4000, 6000))

            url_actual = page.url.lower()
            if "facebook.com/login" in url_actual or "checkpoint" in url_actual:
                print("🔐 [CHAT ALERTA] Facebook requiere verificación manual. Ejecuta auth.py (opción 4) y pausa el bot unos minutos.")
                return

            await page.evaluate("window.scrollBy(0, 700)")
            await page.wait_for_timeout(random.randint(1500, 2200))

            await publicar_comentario_web_inicial(page, url_post)
            await desplegar_todos_los_comentarios(page)
        except Exception as e:
            print(f"⚠️ [CHAT NAV ERROR] {url_post}: {e}")
            continue

        productos_post = obtener_ofertas_por_url(url_post)
        items_dom = await extraer_comentarios_dom(page)
        if items_dom:
            print(f"   🧵 [CHAT] Comentarios/respuestas de usuarios detectados: {len(items_dom)}")

        for item in items_dom:
            autor = item["autorFinal"]
            if es_autor_propio(autor, item["textoPropio"]):
                continue

            lineas = [l.strip() for l in item["textoPropio"].splitlines() if l.strip()]
            cuerpo_lineas = lineas[1:] if (lineas and lineas[0].lower() == autor.lower()) else lineas
            mensaje_usuario = limpiar_mensaje_usuario(cuerpo_lineas, autor=autor)

            if len(mensaje_usuario) < 1 or es_autor_propio(autor, mensaje_usuario):
                continue

            cids = calcular_cids(url_post, autor, mensaje_usuario)
            strikes_actuales, ya_baneado = obtener_estado_omega_usuario(autor)

            if PROTOCOLO_OMEGA_ACTIVO and ya_baneado:
                if not ya_respondido_db(cids):
                    await ocultar_comentario_fb(page, item["commentId"])
                    guardar_respuesta(cids, url_post, autor, mensaje_usuario, "[OMEGA: Ignorado y ocultado por ban]")
                continue

            if ya_respondido_db(cids) or item.get("yaRespondidoDom"):
                if item.get("yaRespondidoDom") and not ya_respondido_db(cids):
                    guardar_respuesta(cids, url_post, autor, mensaje_usuario, "[Sincronizado desde DOM]")
                continue

            if PROTOCOLO_OMEGA_ACTIVO:
                es_omega, motivo_omega = evaluar_mensaje_omega(mensaje_usuario)
                if es_omega:
                    nuevo_strike, recien_baneado = registrar_strike_omega(autor, motivo_omega, mensaje_usuario, url_post)
                    await ocultar_comentario_fb(page, item["commentId"])

                    if recien_baneado:
                        guardar_respuesta(cids, url_post, autor, mensaje_usuario, "[OMEGA: Usuario baneado y notificado por WA]")
                        await notificar_omega_whatsapp(autor, url_post, motivo_omega, mensaje_usuario)
                        continue
                    else:
                        oferta_ref = productos_post[0] if productos_post else None
                        respuesta_omega = await asyncio.to_thread(generar_advertencia_omega, mensaje_usuario, oferta_ref)
                        btn_reply = page.locator(f"[data-bandido-reply-id='{item['replyId']}']").first
                        if await btn_reply.count() > 0:
                            estado_env = await enviar_respuesta_con_mencion(page, btn_reply, autor, respuesta_omega)
                            if estado_env == "OK":
                                guardar_respuesta(cids, url_post, autor, mensaje_usuario, f"[OMEGA STRIKE 1]: {respuesta_omega}")
                        continue

            btn_reply = page.locator(f"[data-bandido-reply-id='{item['replyId']}']").first
            if await btn_reply.count() == 0:
                continue

            tienda_link, _ = extraer_url_tienda(mensaje_usuario)
            genero_usr = inferir_genero_usuario(autor, mensaje_usuario)
            es_alternativa = False
            es_replica_hilo = bool(item.get("esRespuestaHilo"))
            contexto_padre = (item.get("contextoPadre") or "").strip()
            autor_padre = (item.get("autorPadre") or "").strip()
            prod_elegido = None

            if not tienda_link:
                prod_elegido = buscar_coincidencia_real(mensaje_usuario, productos_post, es_post=True, genero_usuario=genero_usr)
                if not prod_elegido and catalogo_d1:
                    prod_elegido = buscar_coincidencia_real(mensaje_usuario, catalogo_d1, es_post=False, genero_usuario=genero_usr)
                    if prod_elegido:
                        es_alternativa = True

                # Si es una respuesta dentro de un hilo (ej. Sergio respondiendo al comentario de Fabian) y no nombró el producto, heredarlo del comentario padre
                if not prod_elegido and es_replica_hilo and contexto_padre:
                    prod_elegido = buscar_coincidencia_real(contexto_padre, productos_post, es_post=True, genero_usuario=genero_usr)
                    if not prod_elegido and catalogo_d1:
                        prod_elegido = buscar_coincidencia_real(contexto_padre, catalogo_d1, es_post=False, genero_usuario=genero_usr)
                        if prod_elegido:
                            es_alternativa = True

            estado_log = (
                f"Link {tienda_link}" if tienda_link
                else (f"Hilo ({autor_padre}): {prod_elegido.get('titulo', '')[:28]}" if (es_replica_hilo and prod_elegido)
                      else (f"Alt D1: {prod_elegido.get('titulo', '')[:30]}" if es_alternativa
                            else (f"Post: {prod_elegido.get('titulo', '')[:30]}" if prod_elegido else "No en D1 -> Promocionar Web")))
            )
            print(f"💬 [CHAT NUEVO] {autor} ({genero_usr}): '{mensaje_usuario[:50]}' -> [{estado_log}]")

            respuesta = await asyncio.to_thread(
                vender,
                mensaje_usuario,
                prod_elegido,
                es_alternativa,
                es_replica_hilo,
                contexto_padre
            )

            estado_envio = await enviar_respuesta_con_mencion(page, btn_reply, autor, respuesta)
            if estado_envio == "OK":
                guardar_respuesta(cids, url_post, autor, mensaje_usuario, respuesta)
                print(f"✅ [CHAT RESPONDIDO] Contestación enviada a {autor}.")
                await page.wait_for_timeout(random.randint(5000, 8500))
            elif estado_envio == "AUTO_TAG_CANCELADO":
                guardar_respuesta(cids, url_post, autor, mensaje_usuario, "[CANCELADO: Auto-etiqueta Bandido Ofertas]")

        await page.wait_for_timeout(random.randint(2500, 4500))

    try:
        await page.goto("https://www.facebook.com/", timeout=30000, wait_until="domcontentloaded")
    except Exception:
        pass


async def main():
    liberar_perfil_navegador(Path(PROF_FB_CHAT))
    modo_ini, _ = obtener_modo_activo()
    print(f"🟢 [CHAT] Iniciando sesión persistente única (Modo: {modo_ini} | Omega: {'ON' if PROTOCOLO_OMEGA_ACTIVO else 'OFF'})...")
    async with adquirir_perfil_navegador(Path(PROF_FB_CHAT), origen="chat"):
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(PROF_FB_CHAT),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--window-position=-32000,-32000"
                ],
                viewport={"width": 1366, "height": 900},
                locale="es-MX",
                timezone_id="America/Mexico_City"
            )
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            try:
                while True:
                    try:
                        await procesar_ronda_chat(page)
                    except Exception as e:
                        print(f"❌ [CHAT ERROR RONDA]: {e}")
                    modo_actual, espera = obtener_modo_activo()
                    mins = espera / 60
                    print(f"⏳ [CHAT | MODO {modo_actual}] Sesión en reposo. Esperando {mins:.1f} min para la siguiente ronda...")
                    await asyncio.sleep(espera)
            finally:
                await ctx.close()


if __name__ == "__main__":
    asyncio.run(main())