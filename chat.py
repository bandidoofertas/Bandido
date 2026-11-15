import asyncio
import hashlib
import json
import random
from playwright.async_api import async_playwright
from cfg import PROF_FB_CHAT, WORKER_URL, get_db, init_db
from mind import vender

PAUSA_CICLO = 35  # Segundos entre rondas de revisión

def obtener_posts_activos() -> list:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT url_post, ofertas_json FROM posts_fb
            WHERE activo = 1
            ORDER BY id DESC LIMIT 10
        """).fetchall()
        return [dict(r) for r in rows]

def ya_respondido(cid: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM respuestas_fb WHERE cid = ?", (cid,)).fetchone()
        return row is not None

def guardar_respuesta(cid: str, url_post: str):
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO respuestas_fb (cid, url_post) VALUES (?, ?)", (cid, url_post))

def elegir_producto_del_post(comentario: str, productos: list) -> dict | None:
    if not productos:
        return None
    if len(productos) == 1:
        return productos[0]

    # Detectar si mencionó número de foto (1, 2, 3, 4 o primera, segunda...)
    c_low = comentario.lower()
    mapa_ord = {"1": 0, "primera": 0, "primero": 0, "2": 1, "segunda": 1, "segundo": 1,
                "3": 2, "tercera": 2, "tercero": 2, "4": 3, "cuarta": 3, "cuarto": 3}
    for clave, idx in mapa_ord.items():
        if f" {clave}" in f" {c_low}" and idx < len(productos):
            return productos[idx]

    # Buscar coincidencia de palabras clave contra los títulos de ese post
    palabras = [p for p in c_low.split() if len(p) > 3 and p not in {"cuanto", "cuesta", "precio", "tiene", "tarjeta", "banco", "info", "link", "enlace", "quiero"}]
    mejor = None
    max_hits = 0
    for prod in productos:
        tit = prod.get("titulo", "").lower()
        hits = sum(1 for p in palabras if p in tit)
        if hits > max_hits:
            max_hits = hits
            mejor = prod

    return mejor if mejor else productos[0]

def es_comentario_generico(comentario: str) -> bool:
    c = comentario.lower().strip()
    genericos = ["info", "informes", "precio", "link", "enlace", "me interesa", "detalles", "donde", "dónde"]
    return len(c.split()) <= 3 and any(g in c for g in genericos)

async def atender_comentarios():
    init_db()
    posts = obtener_posts_activos()
    if not posts:
        print("😴 [CHAT] Sin posts activos en db.sqlite. Esperando a que post.py publique...")
        return

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROF_FB_CHAT),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=-2400,0"
            ],
            viewport={"width": 1366, "height": 900},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        try:
            for post in posts:
                url_post = post["url_post"]
                try:
                    productos = json.loads(post["ofertas_json"])
                except Exception:
                    productos = []

                print(f"🔎 [CHAT] Revisando comentarios en: {url_post}")
                await page.goto(url_post, timeout=35000, wait_until="domcontentloaded")
                await page.wait_for_timeout(random.randint(3500, 5000))
                await page.evaluate("window.scrollBy(0, 700)")
                await page.wait_for_timeout(2000)

                bloques = page.locator("div[role='article']")
                total = await bloques.count()

                for i in range(total):
                    art = bloques.nth(i)
                    try:
                        texto_bruto = (await art.inner_text()).strip()
                    except Exception:
                        continue

                    if not texto_bruto or "Bandido Ofertas" in texto_bruto:
                        continue

                    # Limpiar líneas de botones de Facebook para quedarnos con autor + comentario
                    lineas = [
                        l.strip() for l in texto_bruto.splitlines()
                        if l.strip() and l.strip() not in {"Me gusta", "Responder", "Compartir", "Autor", "Destacado", "Editar", "Ocultar"}
                    ]
                    if len(lineas) < 2:
                        continue

                    autor = lineas[0]
                    mensaje_usuario = " ".join(lineas[1:])
                    if len(mensaje_usuario) < 2:
                        continue

                    cid = hashlib.sha256(f"{url_post}|{autor}|{mensaje_usuario}".encode("utf-8")).hexdigest()
                    if ya_respondido(cid):
                        continue

                    print(f"💬 [CHAT NUEVO] {autor}: '{mensaje_usuario[:50]}'")

                    # Si es una galería de varios productos y solo dijo "info/link", le damos todos los links del post
                    if len(productos) > 1 and es_comentario_generico(mensaje_usuario):
                        lista_links = "\n".join(
                            f"🦝 {idx}. {pr['titulo'][:42]} -> {pr['url_afiliado']}"
                            for idx, pr in enumerate(productos, 1)
                        )
                        respuesta = (
                            f"¡Aquí tienes los enlaces directos de esta tanda, cómplice! 😏🔥\n\n"
                            f"{lista_links}\n\n"
                            f"💳 Si quieres saber en cuánto te queda alguno con tu tarjeta bancaria, dime cuál producto y qué banco usas."
                        )
                    else:
                        prod_elegido = elegir_producto_del_post(mensaje_usuario, productos)
                        respuesta = await asyncio.to_thread(vender, mensaje_usuario, prod_elegido)

                    # Hacer clic en Responder dentro de ese comentario específico
                    btn_reply = art.locator("div[role='button']:has-text('Responder'), span:has-text('Responder')").first
                    if await btn_reply.count() == 0:
                        continue

                    await btn_reply.scroll_into_view_if_needed()
                    await page.wait_for_timeout(700)
                    await btn_reply.click()
                    await page.wait_for_timeout(1500)

                    # Localizar la caja de respuesta activa (enfocada)
                    caja_activa = page.locator("div[role='textbox'][contenteditable='true']:focus").first
                    if await caja_activa.count() == 0:
                        caja_activa = page.locator("div[role='textbox'][contenteditable='true']").last

                    await page.keyboard.insert_text(respuesta)
                    await page.wait_for_timeout(random.randint(1500, 2500))
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(4000)

                    guardar_respuesta(cid, url_post)
                    print(f"✅ [CHAT RESPONDIDO] Contestación enviada a {autor}.")
                    # Pausa humana entre respuestas para evitar límites anti-spam de FB
                    await page.wait_for_timeout(random.randint(5000, 8000))

        except Exception as e:
            print(f"⚠️ [CHAT ERROR]: {e}")
        finally:
            await ctx.close()

async def main():
    while True:
        try:
            await atender_comentarios()
        except Exception as e:
            print(f"❌ [CHAT CRASH]: {e}")
        await asyncio.sleep(PAUSA_CICLO)

if __name__ == "__main__":
    asyncio.run(main())