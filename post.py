import asyncio
from datetime import datetime
import json
import os
import random
import re
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright
from cfg import BASE_DIR, PROF_FB_POST, DIR_QR, get_db, init_db
from mind import limpiar_prohibidas, seducir_post_fb
from calc import auditar_numeros
from browser_queue import adquirir_perfil_navegador

JSON_POSTS = BASE_DIR / "posts_activos.json"
PROMOS_PATH = BASE_DIR / "promos.json"
ASSET_ID = "1410612968801274"
META_HOME_URL = f"https://business.facebook.com/latest/home?asset_id={ASSET_ID}"
META_COMPOSER_URL = f"https://business.facebook.com/latest/composer?asset_id={ASSET_ID}"
META_POSTS_URL = f"https://business.facebook.com/latest/posts/published_posts?asset_id={ASSET_ID}"
FB_PAGE_PUBLIC_URL = f"https://www.facebook.com/{ASSET_ID}"

ESPERA_LINK_SEG = 20
PAUSA_POST_SEG = 5400  # 90 minutos base


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


def limpiar_titulo_comercial(titulo: str) -> str:
    if not titulo:
        return "Producto Destacado"
    for sep in ("|", " - ", " — ", " – "):
        if sep in titulo:
            titulo = titulo.split(sep)[0]
    titulo = re.sub(r'\s+', ' ', titulo).strip()
    if len(titulo) >= 75 and not titulo.endswith((")", '"', "”", "K", "G", "B", "z")):
        palabras = titulo.split()
        if len(palabras) > 4:
            titulo = " ".join(palabras[:-1]).rstrip(",;:/-")
    return titulo[:85].strip()


def obtener_contexto_temporada_post() -> tuple[str, str, str]:
    """Devuelve (emoji_banner, nombre_campana, hashtags_extra) según la fecha actual."""
    ahora = datetime.now()
    m, d = ahora.month, ahora.day
    if m == 11 and 24 <= d <= 29:
        return ("🖤🔥", "ESPECIAL BLACK FRIDAY", "#BlackFridayMexico #BlackFriday")
    if (m == 11 and d == 30) or (m == 12 and d <= 2):
        return ("⚡💻", "ESPECIAL CYBER MONDAY", "#CyberMondayMexico #CyberMonday")
    if m == 12 and 3 <= d <= 24:
        return ("🎄🎁", "ESPECIAL NAVIDEÑO", "#NavidadMexico #RegalosNavidad")
    if (m == 12 and d >= 25) or (m == 1 and d <= 6):
        return ("👑✨", "ESPECIAL DÍA DE REYES", "#DiaDeReyes #ReyesMagos")
    if m == 2 and 1 <= d <= 14:
        return ("💘🎁", "ESPECIAL SAN VALENTÍN", "#SanValentin #Regalos")
    if m == 5 and 1 <= d <= 10:
        return ("💐✨", "ESPECIAL DÍA DE LAS MADRES", "#DiaDeLasMadres")
    if m == 5 and 15 <= d <= 31:
        return ("🔥🛍️", "ESPECIAL HOT SALE", "#HotSaleMexico #HotSale")
    if m == 7 and 8 <= d <= 22:
        return ("📦⚡", "ESPECIAL PRIME DAY", "#PrimeDayMexico #PrimeDay")
    if d in (14, 15, 16, 29, 30, 31, 1):
        return ("💸🦝", "ESPECIAL DE QUINCENA", "#Quincena #AhorroInteligente")
    return ("🚨", "JOYAS AUDITADAS HOY", "#CazaOfertas")


def hay_promos_bancarias_activas() -> bool:
    try:
        if PROMOS_PATH.exists():
            data = json.loads(PROMOS_PATH.read_text(encoding="utf-8"))
            return bool(data.get("amazon") or data.get("mercadolibre"))
    except Exception:
        pass
    return False


async def guardar_en_portapapeles_browser(page, texto: str):
    try:
        await page.evaluate("(t) => navigator.clipboard.writeText(t)", texto)
    except Exception as e:
        print(f"⚠️ [CLIPBOARD AVISO]: {e}")


def guardar_url_en_fichero(url: str):
    ruta_absoluta = JSON_POSTS.resolve()
    if not JSON_POSTS.exists():
        data = []
    else:
        try:
            with open(JSON_POSTS, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except Exception:
            data = []

    if url and url.startswith("http") and url not in data:
        data.insert(0, url)
        data = data[:12]
        with open(JSON_POSTS, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📂 [POST] Enlace guardado exitosamente en: {ruta_absoluta} ({len(data)}/12)")


def generar_imagen_tarjeta(oferta: dict) -> str:
    Path(DIR_QR).mkdir(parents=True, exist_ok=True)
    try:
        from art import crear_tarjeta
        ruta = crear_tarjeta(oferta)
        if ruta and os.path.exists(ruta) and os.path.getsize(ruta) > 1024:
            return os.path.abspath(ruta)
    except Exception as e:
        print(f"⚠️ [POST ART ERROR]: {e}")
    return ""


def construir_copy_multiple(ofertas: list) -> str:
    emoji_temp, titulo_temp, tags_temp = obtener_contexto_temporada_post()
    total = len(ofertas)

    if hay_promos_bancarias_activas():
        cta_superior = (
            f"{emoji_temp} ¡{titulo_temp}: {total} JOYAS AUDITADAS (CERO HUMO)! 🦝\n"
            "💬 Comenta el NÚMERO que te interesa o tu BANCO y te paso el link con bonificación 👇\n"
        )
    else:
        cta_superior = (
            f"{emoji_temp} ¡{titulo_temp}: {total} JOYAS AUDITADAS (CERO HUMO)! 🦝\n"
            "💬 Comenta el NÚMERO que quieres o pega un link de Amazon/ML y te lo audito en segundos 👇\n"
        )

    lineas_texto = [cta_superior]

    for idx, of in enumerate(ofertas, 1):
        titulo_limpio = limpiar_titulo_comercial(of["titulo"])
        subcat = of.get("subcategoria") or "HOG"
        nums = auditar_numeros({
            "precio_oferta": of.get("precio_oferta"),
            "precio_original": of.get("precio_original"),
            "descuento": of.get("descuento_txt", "")
        })
        p_of = nums["precio_oferta"]
        p_or = nums["precio_original"]
        pct = nums["pct_real"]

        if p_or > p_of > 0:
            linea_precio = f"💰 De ${p_or:,.0f} a ${p_of:,.0f} MXN (-{pct}% real)"
        elif p_of > 0:
            linea_precio = f"💰 ${p_of:,.0f} MXN ({of.get('descuento_txt') or 'Oferta verificada'})"
        else:
            linea_precio = f"💰 {of.get('descuento_txt') or 'Oferta verificada'}"

        gancho = seducir_post_fb(titulo_limpio, of["tienda"], subcat, pct)

        lineas_texto.append(
            f"[{idx}] 📦 {titulo_limpio} ({of['tienda']})\n"
            f"{linea_precio}\n"
            f"✨ {gancho}\n"
        )

    lineas_texto.append(f"#BandidoOfertas #GangasMexico #OfertasReales {tags_temp}".strip())
    return limpiar_prohibidas("\n".join(lineas_texto))


async def abrir_compositor_activo(page):
    print("🌐 [POST] Abriendo compositor de Meta Business Suite...")
    await page.goto(META_COMPOSER_URL, timeout=50000, wait_until="domcontentloaded")
    await page.wait_for_timeout(random.randint(5500, 7500))

    url_actual = page.url.split("?")[0].lower()
    if "facebook.com/login" in url_actual or "checkpoint" in url_actual:
        print("🔐 [POST AVISO] Sesión cerrada o en verificación. Ejecuta auth.py (opción 3) primero.")
        return False
    return True


async def subir_fotos_multiples(page, rutas_imagenes: list):
    validas = [r for r in rutas_imagenes if r and os.path.exists(r)]
    if not validas:
        print("⚠️ [POST] No hay imágenes válidas para subir.")
        return False

    for _ in range(2):
        try:
            btn_agregar = page.locator("text=Agregar foto/video").first
            if await btn_agregar.count() > 0 and await btn_agregar.is_visible():
                async with page.expect_file_chooser(timeout=10000) as fc_info:
                    await btn_agregar.click(force=True)
                file_chooser = await fc_info.value
                await file_chooser.set_files(validas)
                print(f"✅ [POST] {len(validas)} imágenes cargadas correctamente en carrusel.")
                await page.wait_for_timeout(7000)
                return True
        except Exception:
            pass

        try:
            inp = page.locator("input[type='file']").first
            if await inp.count() > 0:
                await inp.set_input_files(validas)
                print(f"✅ [POST] {len(validas)} imágenes cargadas en input oculto.")
                await page.wait_for_timeout(7000)
                return True
        except Exception:
            pass
        await page.wait_for_timeout(2000)

    print("⚠️ [POST] No se logró adjuntar las imágenes.")
    return False


async def encontrar_caja_texto(page):
    for _ in range(15):
        for frame in [page] + list(page.frames):
            try:
                cajas = frame.locator("div[contenteditable='true'], textarea")
                total = await cajas.count()
                for i in range(total):
                    caja = cajas.nth(i)
                    if await caja.is_visible():
                        return caja
            except Exception:
                continue
        await page.wait_for_timeout(1000)
    return None


async def manejar_popups_posteriores(page):
    print("🧹 [POST] Cerrando popups emergentes de Meta...")
    for intento in range(6):
        try:
            btn_x = page.locator(
                "div[aria-label='Cerrar'], button[aria-label='Cerrar'], "
                "svg[aria-label='Cerrar'], [role='dialog'] button:has(svg), "
                "div[role='dialog'] div[aria-label='Cerrar']"
            ).first
            if await btn_x.count() > 0 and await btn_x.is_visible():
                await btn_x.click(force=True)
                print(f"   ✖️ [POPUP] Clic en X (intento {intento+1})")
                await page.wait_for_timeout(2000)
                continue

            btn_texto = page.locator(
                "button:has-text('Tal vez más tarde'), "
                "button:has-text('Listo'), "
                "div[role='button']:has-text('Listo')"
            ).first
            if await btn_texto.count() > 0 and await btn_texto.is_visible():
                await btn_texto.click(force=True)
                print(f"   ✔️ [POPUP] Clic en botón de salida (intento {intento+1})")
                await page.wait_for_timeout(2000)
                continue

            dialogos = page.locator("[role='dialog']")
            if await dialogos.count() == 0:
                break

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)
        except Exception:
            pass


def normalizar_url_fb(raw_url: str) -> str:
    if not raw_url or "facebook.com" not in raw_url:
        return ""
    u = raw_url.strip()
    if "permalink.php" in u or "story_fbid=" in u or "fbid=" in u:
        return u
    return u.split("?")[0].rstrip("/")


async def extraer_enlace_por_dom(page, urls_interceptadas: list[str]) -> str:
    # CAPA 1: Si ya se interceptó en la respuesta GraphQL de publicación, devolver de inmediato
    for u in urls_interceptadas:
        limpia = normalizar_url_fb(u)
        if limpia:
            print(f"✅ [POST CAPA 1] Enlace capturado directamente desde la API de Meta: {limpia}")
            return limpia

    # CAPA 2: Tabla de Meta Business Suite + Panel lateral de detalles
    print("🔍 [POST CAPA 2] Navegando a Publicaciones y reels para extraer el enlace oficial...")
    try:
        await page.goto(META_POSTS_URL, timeout=45000, wait_until="domcontentloaded")
    except Exception as nav_err:
        print(f"⚠️ [POST AVISO NAV]: {nav_err}")
    await page.wait_for_timeout(7500)

    for intento in range(5):
        try:
            url_extraida = await page.evaluate(r"""(assetId) => {
                const esLinkPost = (href) => (
                    href &&
                    href.includes('facebook.com') &&
                    !href.includes('business.facebook.com') &&
                    (
                        href.includes('/posts/') ||
                        href.includes('story_fbid') ||
                        href.includes('/permalink/') ||
                        href.includes('/photos/') ||
                        href.includes('fbid=') ||
                        href.includes('/share/p/')
                    )
                );

                // 1) Buscar enlaces directos en todo el documento o en filas de tabla
                for (const a of document.querySelectorAll('a[href]')) {
                    if (esLinkPost(a.href)) return a.href;
                }

                // 2) Buscar IDs ocultos en atributos o HTML de las primeras filas (saltando cabecera)
                const rows = Array.from(document.querySelectorAll('div[role="row"], tr')).filter(r => !r.querySelector('th') && (r.innerText || '').trim().length > 15);
                for (const row of rows.slice(0, 3)) {
                    const htmlText = row.innerHTML || '';
                    const mPost = htmlText.match(/(?:post_id|story_fbid|top_level_post_id|fbid|target_id)["'=:\s]+(\d{15,20})/i);
                    if (mPost && mPost[1] !== assetId) {
                        return 'https://www.facebook.com/permalink.php?story_fbid=' + mPost[1] + '&id=' + assetId;
                    }
                    const matchPfbid = htmlText.match(/\b(pfbid[A-Za-z0-9]+)\b/);
                    if (matchPfbid) {
                        return 'https://www.facebook.com/BandidoOfertas/posts/' + matchPfbid[1];
                    }
                }
                return null;
            }""", ASSET_ID)

            limpia = normalizar_url_fb(url_extraida or "")
            if limpia:
                print(f"✅ [POST CAPA 2] Enlace extraído del DOM de Business Suite: {limpia}")
                return limpia

            # En intento 2, hacer clic en la primera fila de publicaciones para abrir el panel lateral de Meta
            if intento == 2:
                primera_fila = page.locator("div[role='row']:has-text('JOYAS'), div[role='row']:has-text('ESPECIAL'), div[role='row']:has-text('Bandido')").first
                if await primera_fila.count() == 0:
                    filas = page.locator("div[role='row']")
                    if await filas.count() > 1:
                        primera_fila = filas.nth(1)
                if await primera_fila.count() > 0:
                    await primera_fila.click(force=True)
                    await page.wait_for_timeout(3500)
                    # Buscar botón/enlace "Ver publicación" dentro del panel lateral
                    ver_pub = page.locator("a:has-text('Ver publicación'), a:has-text('Ver en Facebook'), a[href*='/posts/'], a[href*='permalink.php']").first
                    if await ver_pub.count() > 0:
                        href_panel = await ver_pub.get_attribute("href")
                        limpia_panel = normalizar_url_fb(href_panel or "")
                        if limpia_panel:
                            print(f"✅ [POST CAPA 2B] Enlace extraído desde el panel de detalles: {limpia_panel}")
                            return limpia_panel
        except Exception as e:
            print(f"⚠️ [POST AVISO DOM intento {intento+1}]: {e}")
        await page.wait_for_timeout(2500)

    # CAPA 3: Fallback infalible — Ir directo a la página pública de Bandido Ofertas y leer el 1er post
    print("🌐 [POST CAPA 3] Consultando directamente la página pública de Bandido Ofertas...")
    try:
        await page.goto(FB_PAGE_PUBLIC_URL, timeout=45000, wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        await page.evaluate("window.scrollBy(0, 500)")
        await page.wait_for_timeout(2500)

        url_perfil = await page.evaluate(r"""(assetId) => {
            for (const a of document.querySelectorAll('a[href]')) {
                const href = a.href || '';
                if (
                    href.includes('facebook.com') &&
                    (
                        href.includes('/posts/') ||
                        href.includes('story_fbid=') ||
                        href.includes('/permalink/') ||
                        href.includes('fbid=')
                    )
                ) {
                    return href;
                }
            }
            const html = document.body.innerHTML || '';
            const mPfbid = html.match(/\b(pfbid[A-Za-z0-9]+)\b/);
            if (mPfbid) return 'https://www.facebook.com/BandidoOfertas/posts/' + mPfbid[1];

            const mId = html.match(/"post_id":"(\d{15,20})"/);
            if (mId && mId[1] !== assetId) {
                return 'https://www.facebook.com/permalink.php?story_fbid=' + mId[1] + '&id=' + assetId;
            }
            return null;
        }""", ASSET_ID)

        limpia_perfil = normalizar_url_fb(url_perfil or "")
        if limpia_perfil:
            print(f"✅ [POST CAPA 3] Enlace rescatado desde la página pública: {limpia_perfil}")
            return limpia_perfil
    except Exception as e:
        print(f"⚠️ [POST CAPA 3 ERROR]: {e}")

    return ""


async def publicar_lote_ofertas(page):
    init_db()
    with get_db() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(ofertas)").fetchall()]
        if "publicado_fb" not in cols:
            conn.execute("ALTER TABLE ofertas ADD COLUMN publicado_fb INTEGER DEFAULT 0")

        rows = conn.execute("""
            SELECT id, titulo, tienda, precio_oferta, precio_original, descuento_txt,
                   subcategoria, url_afiliado, razonamiento, imagen_url 
            FROM ofertas WHERE IFNULL(publicado_fb, 0) = 0
            ORDER BY score ASC, id DESC LIMIT 5
        """).fetchall()

    if not rows:
        print("😴 [POST] No hay ofertas pendientes para publicar.")
        return

    ofertas = [dict(r) for r in rows]
    print(f"🎯 [POST] Lote seleccionado: {len(ofertas)} ofertas para carrusel.")

    rutas_imagenes = []
    ids_publicados = []
    for of in ofertas:
        ruta = await asyncio.to_thread(generar_imagen_tarjeta, of)
        if ruta:
            rutas_imagenes.append(ruta)
            ids_publicados.append(of["id"])

    if not rutas_imagenes:
        print("❌ [POST ERROR] No se pudo generar ninguna tarjeta visual.")
        return

    copy_texto = await asyncio.to_thread(construir_copy_multiple, ofertas)
    print("📝 [POST] Copy generado:")
    print("--------------------------------------------------")
    print(copy_texto)
    print("--------------------------------------------------")

    if not await abrir_compositor_activo(page):
        return

    await subir_fotos_multiples(page, rutas_imagenes)

    caja_texto = await encontrar_caja_texto(page)
    if not caja_texto:
        print("❌ [POST ERROR] No se encontró la caja de texto.")
        return

    await caja_texto.click()
    await page.wait_for_timeout(random.randint(800, 1400))

    await guardar_en_portapapeles_browser(page, copy_texto)
    await page.keyboard.press("Control+v")
    await page.wait_for_timeout(random.randint(2000, 3200))

    # Listener de respuestas de red para capturar el ID/permalink al instante de publicar
    urls_interceptadas = []

    async def on_response(resp):
        try:
            u = resp.url
            if "graphql" in u or "publish" in u or "composer" in u:
                txt = await resp.text()
                if "story_fbid" in txt or "post_id" in txt or "pfbid" in txt:
                    m_url = re.search(r'https:\\?/\\?/www\.facebook\.com\\?/[^"\\\s]+(?:posts|permalink|story_fbid)[^"\\\s]*', txt)
                    if m_url:
                        urls_interceptadas.append(m_url.group(0).replace("\\/", "/"))
                    else:
                        m_pfbid = re.search(r'\b(pfbid[A-Za-z0-9]+)\b', txt)
                        if m_pfbid:
                            urls_interceptadas.append(f"https://www.facebook.com/BandidoOfertas/posts/{m_pfbid.group(1)}")
                        else:
                            m_pid = re.search(r'"(?:post_id|story_fbid)"\s*:\s*"(\d{15,20})"', txt)
                            if m_pid and m_pid.group(1) != ASSET_ID:
                                urls_interceptadas.append(f"https://www.facebook.com/permalink.php?story_fbid={m_pid.group(1)}&id={ASSET_ID}")
        except Exception:
            pass

    page.on("response", on_response)

    print("🚀 [POST] Haciendo clic en Publicar...")
    btn_publicar = page.locator(
        "div[role='button']:has-text('Publicar'), "
        "button:has-text('Publicar'), "
        "div[role='button']:has-text('Publish')"
    ).last
    await btn_publicar.click()

    print(f"⏳ [POST] Publicado. Esperando {ESPERA_LINK_SEG} segundos para cerrar popups...")
    await page.wait_for_timeout(ESPERA_LINK_SEG * 1000)
    try:
        page.remove_listener("response", on_response)
    except Exception:
        pass

    await manejar_popups_posteriores(page)

    url_post = await extraer_enlace_por_dom(page, urls_interceptadas)

    with get_db() as conn:
        for oid in ids_publicados:
            conn.execute("UPDATE ofertas SET publicado_fb = 1 WHERE id = ?", (oid,))

    if url_post and "facebook.com" in url_post:
        guardar_url_en_fichero(url_post)
        with get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posts_fb (
                    url_post TEXT PRIMARY KEY,
                    ofertas_json TEXT,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """, ())
            conn.execute(
                "INSERT OR REPLACE INTO posts_fb (url_post, ofertas_json) VALUES (?, ?)",
                (url_post, json.dumps(ofertas, ensure_ascii=False))
            )
        print("✅ [POST] Lote publicado con éxito y enlace capturado en JSON.")
    else:
        print("⚠️ [POST AVISO] Publicado correctamente, pero no se pudo capturar el enlace automático en este intento.")

    try:
        await page.goto(META_HOME_URL, timeout=30000, wait_until="domcontentloaded")
    except Exception:
        pass


async def main():
    liberar_perfil_navegador(Path(PROF_FB_POST))
    print("🟢 [POST] Iniciando sesión persistente única en Meta Business Suite...")
    async with adquirir_perfil_navegador(Path(PROF_FB_POST), origen="post"):
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(PROF_FB_POST),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--window-position=-32000,-32000"
                ],
                viewport={"width": 1440, "height": 900},
                locale="es-MX",
                timezone_id="America/Mexico_City"
            )
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            try:
                while True:
                    try:
                        await publicar_lote_ofertas(page)
                    except Exception as e:
                        print(f"❌ [POST CRASH]: {e}")
                    espera = PAUSA_POST_SEG + random.randint(-180, 300)
                    print(f"💤 [POST] Sesión en reposo. Esperando {espera // 60} min para el siguiente lote...")
                    await asyncio.sleep(espera)
            finally:
                await ctx.close()


if __name__ == "__main__":
    asyncio.run(main())