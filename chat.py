import asyncio
import hashlib
import json
import random
import re
import subprocess
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from cfg import PROF_FB_CHAT, WORKER_URL, get_db, init_db
from mind import vender, extraer_url_tienda
from calc import detectar_banco
from browser_queue import adquirir_perfil_navegador

PAUSA_BASE_SEG = 780
POSTS_JSON = Path(__file__).resolve().parent / "posts_activos.json"
API_D1_OFERTAS = f"{WORKER_URL.rstrip('/')}/api/ofertas"

SINONIMOS_PRODUCTO = {
    "reloj": ["reloj", "smartwatch", "watch", "band", "pulsera", "bulova", "huawei"],
    "audifonos": ["audifonos", "audífonos", "earbuds", "airpods", "headset", "diadema", "iem", "kz"],
    "bocina": ["bocina", "altavoz", "speaker", "partybox", "soundbar", "barra"],
    "instrumento": ["guitarra", "bajo", "teclado", "piano", "sintetizador", "ukelele", "bateria", "microfono"],
    "laptop": ["laptop", "computadora", "compu", "notebook", "macbook", "pc"],
    "celular": ["celular", "telefono", "teléfono", "smartphone", "iphone", "samsung", "xiaomi", "oppo", "motorola", "tablet", "ipad"],
    "tele": ["tele", "television", "televisión", "pantalla", "tv", "smart tv", "dron", "alexa"],
    "juego": ["juego", "videojuego", "videojuegos", "consola", "switch", "nintendo", "ps5", "ps4", "playstation", "xbox", "dualsense", "joycon", "zelda", "mario", "pokemon"],
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
    "especial", "busca", "tengo", "aplica", "bonificacion", "bonificación"
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


def es_autor_propio(autor: str, texto_bruto: str = "") -> bool:
    a = (autor or "").strip().lower()
    t = (texto_bruto or "").strip().lower()
    if not a:
        return True
    if a == "bandido ofertas" or a.startswith("bandido ofertas"):
        return True
    if t.startswith("bandido ofertas") or "🦝" in t[:25]:
        return True
    return False


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
            "1": 0, "primera": 0, "primero": 0,
            "2": 1, "segunda": 1, "segundo": 1,
            "3": 2, "tercera": 2, "tercero": 2,
            "4": 3, "cuarta": 3, "cuarto": 3,
            "5": 4, "quinta": 4, "quinto": 4
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

        # Bonificación por coincidencia de género en ropa/calzado (ROP-M / ROP-H)
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

    texto = " ".join(filtradas)
    texto = re.sub(r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+){2,3}(?=[a-z0-9áéíóúñ])", "", texto).strip()
    return texto


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
            clicked = await page.evaluate("""() => {
                let count = 0;
                const candidatos = document.querySelectorAll('div[role="button"], span[role="button"], span');
                for (const el of candidatos) {
                    const txt = (el.innerText || '').trim().toLowerCase();
                    if (!txt || txt.length > 45) continue;
                    if (
                        /^ver\\s+.*respuesta/.test(txt) ||
                        /^\\d+\\s+respuesta/.test(txt) ||
                        /^ver\\s+más\\s+comentario/.test(txt) ||
                        /^ver\\s+comentarios\\s+anteriores/.test(txt)
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
    return await page.evaluate("""() => {
        document.querySelectorAll('[data-bandido-reply-id]').forEach(el => el.removeAttribute('data-bandido-reply-id'));

        const sel = 'div[role="article"], div[aria-label^="Comentario de"], div[aria-label^="Respuesta de"]';
        const nodos = Array.from(document.querySelectorAll(sel));
        const resultados = [];
        let seq = 0;

        for (const el of nodos) {
            const aria = el.getAttribute('aria-label') || '';
            const ariaLow = aria.toLowerCase();

            if (ariaLow.includes('bandido ofertas')) continue;

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
            const textoPropio = dirs.map(d => (d.innerText || '').trim()).filter(Boolean).join('\\n');
            if (!textoPropio) continue;

            let autorAria = '';
            const mAria = aria.match(/^(?:Comentario|Respuesta)\\s+de\\s+(.+?)(?:\\s+al?\\s+|\\s+hace\\s+|$)/i);
            if (mAria) autorAria = mAria[1].trim();

            const lineas = textoPropio.split('\\n').map(x => x.trim()).filter(Boolean);
            const autorFinal = autorAria || (lineas[0] || '');
            if (!autorFinal || autorFinal.toLowerCase().startsWith('bandido ofertas')) continue;
            if ((lineas[0] || '').toLowerCase().startsWith('bandido ofertas')) continue;

            let yaRespondidoDom = false;
            const contenedorHilo = el.closest('li') || el.parentElement?.parentElement || el.parentElement;
            if (contenedorHilo) {
                const subBloques = Array.from(contenedorHilo.querySelectorAll(sel));
                for (const sb of subBloques) {
                    if (sb === el) continue;
                    const txtSb = (sb.innerText || '');
                    const ariaSb = (sb.getAttribute('aria-label') || '');
                    const esDeBandido = txtSb.startsWith('Bandido Ofertas') || ariaSb.toLowerCase().includes('bandido ofertas');
                    if (esDeBandido) {
                        if (ariaLow.startsWith('comentario de') || txtSb.includes(autorFinal)) {
                            yaRespondidoDom = true;
                            break;
                        }
                    }
                }
            }

            seq += 1;
            const replyId = 'reply_' + seq;
            botonesReply[0].setAttribute('data-bandido-reply-id', replyId);

            resultados.push({
                replyId,
                aria,
                autorFinal,
                textoPropio,
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
            await page.goto(url_post, timeout=40000, wait_until="domcontentloaded")
            await page.wait_for_timeout(random.randint(4500, 6500))

            url_actual = page.url.lower()
            if "facebook.com/login" in url_actual or "checkpoint" in url_actual:
                print("🔐 [CHAT ALERTA] Facebook requiere verificación manual. Ejecuta auth.py (opción 4) y pausa el bot unos minutos.")
                return

            await page.evaluate("window.scrollBy(0, 700)")
            await page.wait_for_timeout(random.randint(1500, 2500))
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

            if len(mensaje_usuario) < 1:
                continue

            cids = calcular_cids(url_post, autor, mensaje_usuario)

            if ya_respondido_db(cids) or item.get("yaRespondidoDom"):
                if item.get("yaRespondidoDom") and not ya_respondido_db(cids):
                    guardar_respuesta(cids, url_post, autor, mensaje_usuario, "[Sincronizado desde DOM]")
                continue

            btn_reply = page.locator(f"[data-bandido-reply-id='{item['replyId']}']").first
            if await btn_reply.count() == 0:
                continue

            tienda_link, _ = extraer_url_tienda(mensaje_usuario)
            genero_usr = inferir_genero_usuario(autor, mensaje_usuario)
            es_alternativa = False
            prod_elegido = None

            if not tienda_link:
                prod_elegido = buscar_coincidencia_real(mensaje_usuario, productos_post, es_post=True, genero_usuario=genero_usr)
                if not prod_elegido and catalogo_d1:
                    prod_elegido = buscar_coincidencia_real(mensaje_usuario, catalogo_d1, es_post=False, genero_usuario=genero_usr)
                    if prod_elegido:
                        es_alternativa = True

            estado_log = (
                f"Link {tienda_link}" if tienda_link
                else (f"Alt D1: {prod_elegido.get('titulo', '')[:30]}" if es_alternativa
                      else (f"Post: {prod_elegido.get('titulo', '')[:30]}" if prod_elegido else "No en D1 -> Promocionar Web"))
            )
            print(f"💬 [CHAT NUEVO] {autor} ({genero_usr}): '{mensaje_usuario[:50]}' -> [{estado_log}]")

            respuesta = await asyncio.to_thread(vender, mensaje_usuario, prod_elegido, es_alternativa)

            await btn_reply.scroll_into_view_if_needed()
            await page.wait_for_timeout(random.randint(800, 1400))
            await btn_reply.click(force=True)
            await page.wait_for_timeout(random.randint(1500, 2300))

            caja_activa = page.locator("div[role='textbox'][contenteditable='true']:focus").first
            if await caja_activa.count() == 0:
                caja_activa = page.locator("div[role='textbox'][contenteditable='true']").last

            await page.keyboard.insert_text(respuesta)
            await page.wait_for_timeout(random.randint(1800, 3000))
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(4000)

            guardar_respuesta(cids, url_post, autor, mensaje_usuario, respuesta)
            print(f"✅ [CHAT RESPONDIDO] Contestación enviada a {autor}.")
            await page.wait_for_timeout(random.randint(6000, 10000))

        await page.wait_for_timeout(random.randint(3000, 6000))

    try:
        await page.goto("https://www.facebook.com/", timeout=30000, wait_until="domcontentloaded")
    except Exception:
        pass


async def main():
    liberar_perfil_navegador(Path(PROF_FB_CHAT))
    print("🟢 [CHAT] Iniciando sesión persistente única...")
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
                    espera = PAUSA_BASE_SEG + random.randint(-90, 180)
                    print(f"⏳ [CHAT] Sesión en reposo. Esperando {espera // 60} min para la siguiente ronda...")
                    await asyncio.sleep(espera)
            finally:
                await ctx.close()


if __name__ == "__main__":
    asyncio.run(main())