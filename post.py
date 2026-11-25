import asyncio
import json
import os
import re
import time
from pathlib import Path
from playwright.async_api import async_playwright
from cfg import PROF_FB_POST, DIR_QR, get_db, init_db
from mind import limpiar_prohibidas, seducir_tarjeta

BASE_DIR = Path(__file__).resolve().parent
JSON_POSTS = BASE_DIR / "posts_activos.json"
ASSET_ID = "1410612968801274"
META_COMPOSER_URL = f"https://business.facebook.com/latest/composer?asset_id={ASSET_ID}"
META_POSTS_URL = f"https://business.facebook.com/latest/posts/published_posts?asset_id={ASSET_ID}"

ESPERA_LINK_SEG = 20
PAUSA_POST_SEG = 5400  # 90 minutos exactos


def limpiar_titulo_comercial(titulo: str) -> str:
    """Elimina precios, pulgadas excesivas y datos técnicos, dejando solo nombre y modelo."""
    if not titulo:
        return "Producto Destacado"
    if "|" in titulo:
        titulo = titulo.split("|")[0]
    if " - " in titulo:
        titulo = titulo.split(" - ")[0]
    return re.sub(r'\s+', ' ', titulo).strip()


async def guardar_en_portapapeles_browser(page, texto: str):
    """Copia el texto al portapapeles usando la API nativa del navegador."""
    try:
        await page.evaluate("(t) => navigator.clipboard.writeText(t)", texto)
    except Exception as e:
        print(f"⚠️ [CLIPBOARD AVISO]: {e}")


def guardar_url_en_fichero(url: str):
    """Inserta la nueva URL al inicio del array JSON usando ruta absoluta y mantiene máximo 10 enlaces."""
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
        data = data[:10]
        with open(JSON_POSTS, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📂 [POST] Enlace guardado exitosamente en: {ruta_absoluta} ({len(data)}/10)")


def generar_imagen_con_qr(oferta: dict) -> str:
    """Genera la tarjeta visual con QR optimizada."""
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
    """Construye un copy coqueto SIN PRECIOS y SIN DATOS TÉCNICOS."""
    lineas_texto = ["🔥 ¡GANGAZAS REALES DETECTADAS! 🔥\n"]
    
    for idx, of in enumerate(ofertas, 1):
        titulo_limpio = limpiar_titulo_comercial(of["titulo"])
        subcat = of.get("subcategoria") or "H1"
        gancho = seducir_tarjeta(titulo_limpio, of["tienda"], subcat, 0)
        
        lineas_texto.append(
            f"[{idx}] 📦 {titulo_limpio}\n"
            f"✨ {gancho}\n"
            f"👉 Atrápalo aquí: {of['url_afiliado']}\n"
        )

    lineas_texto.append(
        "💬 Comenta tu banco y te calculo si aplica bonificación extra 🦝🌙\n"
        "#BandidoOfertas #Gangas #OfertasMexico"
    )
    return limpiar_prohibidas("\n".join(lineas_texto))


async def abrir_compositor_activo(page):
    """Abre directamente el compositor de Meta Business Suite."""
    print("🌐 [POST] Abriendo compositor de Meta Business Suite...")
    await page.goto(META_COMPOSER_URL, timeout=50000, wait_until="domcontentloaded")
    await page.wait_for_timeout(6000)

    url_actual = page.url.split("?")[0].lower()
    if "facebook.com/login" in url_actual or "checkpoint" in url_actual:
        print("🔐 [POST AVISO] Sesión cerrada. Ejecuta auth.py (opción 3) primero.")
        return False
    return True


async def subir_fotos_multiples(page, rutas_imagenes: list):
    """Sube múltiples imágenes juntas (hasta 5) al compositor."""
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
    """Localiza el cuadro de texto editable del compositor."""
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
    """Cierra con precisión quirúrgica AMBOS popups posteriores (Anuncio y App QR)."""
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


async def extraer_enlace_por_dom(page) -> str:
    """Navega a Publicaciones y reels y extrae el ID o enlace directamente de los atributos de la primera fila de la tabla."""
    print("🔍 [POST] Navegando a Publicaciones y reels para extraer el enlace oficial...")
    await page.goto(META_POSTS_URL, timeout=40000, wait_until="domcontentloaded")
    await page.wait_for_timeout(6000)

    print("🖱️ [POST] Analizando la primera fila de la tabla para obtener el enlace...")
    for intento in range(4):
        try:
            url_extraida = await page.evaluate("""() => {
                const rows = document.querySelectorAll('div[role="row"]:not(:has(th)), tr:not(:has(th))');
                if (rows.length === 0) return null;
                
                const firstRow = rows[0];
                
                const links = Array.from(firstRow.querySelectorAll('a'));
                for (const a of links) {
                    const href = a.href || '';
                    if (href.includes('/posts/') || href.includes('story_fbid') || href.includes('posts_id')) {
                        return href;
                    }
                }

                const walker = document.createTreeWalker(firstRow, NodeFilter.SHOW_ELEMENT);
                let node;
                while (node = walker.nextNode()) {
                    for (const attr of node.attributes) {
                        const val = attr.value || '';
                        const match = val.match(/\\b\\d{15,20}\\b/);
                        if (match) {
                            return 'https://www.facebook.com/' + match[0];
                        }
                    }
                }

                const htmlText = firstRow.innerHTML;
                const matchHtml = htmlText.match(/\\b(1\\d{16,18})\\b/);
                if (matchHtml) {
                    return 'https://www.facebook.com/' + matchHtml[1];
                }

                return null;
            }""")

            if url_extraida and "facebook.com" in url_extraida:
                clean_url = url_extraida.split("?")[0]
                print(f"✅ [POST] Enlace extraído directamente del DOM: {clean_url}")
                return clean_url
        except Exception as e:
            print(f"⚠️ [POST AVISO DOM intento {intento+1}]: {e}")
        await page.wait_for_timeout(2500)

    return ""


async def publicar_lote_ofertas():
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

    print("🎨 [POST] Generando tarjetas QR para el lote...")
    rutas_imagenes = []
    ids_publicados = []
    for of in ofertas:
        ruta = await asyncio.to_thread(generar_imagen_con_qr, of)
        if ruta:
            rutas_imagenes.append(ruta)
            ids_publicados.append(of["id"])

    if not rutas_imagenes:
        print("❌ [POST ERROR] No se pudo generar ninguna tarjeta QR.")
        return

    print("🧠 [POST] Construyendo copy múltiple...")
    copy_texto = construir_copy_multiple(ofertas)
    print("📝 [POST] Copy generado:")
    print("--------------------------------------------------")
    print(copy_texto)
    print("--------------------------------------------------")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROF_FB_POST),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled", 
                "--start-maximized",
                "--window-position=-32000,-32000"
            ],
            viewport={"width": 1920, "height": 1080},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        try:
            if not await abrir_compositor_activo(page):
                return

            print("🖼️ [POST] Subiendo lote de imágenes al carrusel...")
            await subir_fotos_multiples(page, rutas_imagenes)

            print("✍️ [POST] Pegando copy en el compositor...")
            caja_texto = await encontrar_caja_texto(page)
            if not caja_texto:
                print("❌ [POST ERROR] No se encontró la caja de texto.")
                return

            await caja_texto.click()
            await page.wait_for_timeout(800)

            await guardar_en_portapapeles_browser(page, copy_texto)
            await page.keyboard.press("Control+v")
            await page.wait_for_timeout(2000)

            print("🚀 [POST] Haciendo clic en Publicar...")
            btn_publicar = page.locator(
                "div[role='button']:has-text('Publicar'), "
                "button:has-text('Publicar'), "
                "div[role='button']:has-text('Publish')"
            ).last
            await btn_publicar.click()

            print(f"⏳ [POST] Publicado. Esperando {ESPERA_LINK_SEG} segundos para cerrar popups...")
            await page.wait_for_timeout(ESPERA_LINK_SEG * 1000)
            await manejar_popups_posteriores(page)

            url_post = await extraer_enlace_por_dom(page)
            
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

        except Exception as e:
            print(f"❌ [POST ERROR CRítico]: {e}")
        finally:
            await ctx.close()


async def main():
    while True:
        try:
            await publicar_lote_ofertas()
        except Exception as e:
            print(f"❌ [POST CRASH]: {e}")
        print(f"💤 [POST] Esperando {PAUSA_POST_SEG} segundos (90 min) para el siguiente lote...")
        await asyncio.sleep(PAUSA_POST_SEG)


if __name__ == "__main__":
    asyncio.main(main()) if hasattr(asyncio, "main") else asyncio.run(main())