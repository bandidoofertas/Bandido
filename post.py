import asyncio
import json
import os
import random
from playwright.async_api import async_playwright
from cfg import PROF_FB_POST, WORKER_URL, get_db, init_db
from art import crear_tarjeta, limpiar_qr

INTERVALO_SEG = 3600  # 1 hora

def obtener_lote_ofertas(limite: int = 4) -> list:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM ofertas
            WHERE publicado_fb = 0 AND score <= 3
            ORDER BY score ASC, id DESC
            LIMIT ?
        """, (limite,)).fetchall()

        if len(rows) < limite:
            faltan = limite - len(rows)
            ids_ya = [r["id"] for r in rows]
            placeholders = ",".join("?" * len(ids_ya)) if ids_ya else "0"
            extra = conn.execute(f"""
                SELECT * FROM ofertas
                WHERE publicado_fb = 0 AND score = 4 AND id NOT IN ({placeholders})
                ORDER BY id DESC
                LIMIT ?
            """, (*ids_ya, faltan)).fetchall()
            rows = list(rows) + list(extra)

        return [dict(r) for r in rows]

def marcar_publicadas(ids: list):
    if not ids:
        return
    with get_db() as conn:
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"UPDATE ofertas SET publicado_fb = 1 WHERE id IN ({placeholders})", ids)

def registrar_post(url_post: str, lote: list):
    if not url_post:
        return
    resumen = [
        {
            "id": o["id"],
            "titulo": o["titulo"],
            "tienda": o["tienda"],
            "precio_oferta": o["precio_oferta"],
            "precio_original": o["precio_original"],
            "descuento": o["descuento_txt"],
            "score": o["score"],
            "url_afiliado": o["url_afiliado"]
        }
        for o in lote
    ]
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO posts_fb (url_post, ofertas_json, activo)
            VALUES (?, ?, 1)
        """, (url_post, json.dumps(resumen, ensure_ascii=False)))

        # Mantener solo los últimos 15 posts activos para vigilancia ágil
        conn.execute("""
            UPDATE posts_fb SET activo = 0
            WHERE id NOT IN (SELECT id FROM posts_fb ORDER BY id DESC LIMIT 15)
        """)

async def publicar_en_fb(rutas_img: list, lote: list) -> str:
    print("🚀 [POST] Abriendo navegador para publicar galería en Facebook...")
    url_capturada = ""

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROF_FB_POST),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=-2400,0"  # Fuera de vista para no estorbar tu pantalla
            ],
            viewport={"width": 1366, "height": 900},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        try:
            await page.goto("https://www.facebook.com/", timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(random.randint(4500, 6500))

            # Armar texto coqueto y limpio
            lineas = []
            for idx, o in enumerate(lote, 1):
                t = o["titulo"][:55]
                tienda = o["tienda"].upper()
                lineas.append(f"{idx}️⃣ 🦝 {t} ({tienda})")

            caption = (
                "🔥 ¡NUEVA TANDA DE TESOROS CAZADOS POR EL MAPACHE! 🔥\n\n"
                + "\n".join(lineas)
                + "\n\n👀 Escanea el código QR de la foto que te gustó o coméntame aquí abajo cuál te llamó la atención (o qué banco usas) y te paso el enlace directo + cálculo de promo extra 💳😏\n\n"
                + f"🌐 Catálogo completo en vivo:\n{WORKER_URL}"
            )

            # Abrir modal de Foto/Video
            btn_foto = page.locator("span:has-text('Foto/video'), span:has-text('Foto/vídeo')").first
            await btn_foto.wait_for(state="visible", timeout=15000)
            await btn_foto.click()
            await page.wait_for_timeout(random.randint(2500, 3800))

            # Subir las imágenes al input file del diálogo
            file_input = page.locator("div[role='dialog'] input[type='file'], input[type='file']").first
            await file_input.set_input_files(rutas_img)
            print(f"📸 [POST] Subiendo {len(rutas_img)} tarjetas QR...")
            await page.wait_for_timeout(random.randint(7000, 9500))

            # Escribir caption en el textbox del modal
            textbox = page.locator("div[role='dialog'] div[role='textbox']").first
            await textbox.click()
            await page.wait_for_timeout(800)
            await page.keyboard.insert_text(caption)
            await page.wait_for_timeout(random.randint(2500, 3500))

            # Clic en Publicar
            btn_pub = page.locator("div[role='dialog'] div[aria-label='Publicar'][role='button']").first
            await btn_pub.click()
            print("⏳ [POST] Publicando tanda, esperando confirmación de Facebook...")
            await page.wait_for_timeout(14000)

            # Recargar perfil/inicio para capturar el enlace real del post más reciente
            await page.goto("https://www.facebook.com/me", timeout=35000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            url_capturada = await page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                for (const a of links) {
                    const h = a.href || '';
                    if (h.includes('/posts/') || h.includes('/permalink/') || h.includes('/share/p/')) {
                        return h.split('?')[0];
                    }
                }
                return '';
            }""")

            if url_capturada:
                print(f"✅ [POST OK] Publicado y rastreado en: {url_capturada}")
            else:
                print("⚠️ [POST] Publicado, pero no se pudo extraer el permalink en este turno.")

        except Exception as e:
            print(f"❌ [POST ERROR]: {e}")
        finally:
            await ctx.close()

    return url_capturada

async def ciclo_publicacion():
    init_db()
    limpiar_qr(6)
    lote = obtener_lote_ofertas(4)

    if not lote:
        print("😴 [POST] Sin ofertas nuevas pendientes en db.sqlite.")
        return

    rutas = []
    for of in lote:
        ruta = await asyncio.to_thread(crear_tarjeta, of)
        if ruta and os.path.exists(ruta):
            rutas.append(ruta)

    if not rutas:
        return

    url_post = await publicar_en_fb(rutas, lote)
    # Marcamos publicadas si se subió con éxito (o si capturó URL)
    marcar_publicadas([o["id"] for o in lote])
    if url_post:
        registrar_post(url_post, lote)

    for r in rutas:
        try:
            os.remove(r)
        except Exception:
            pass

async def main():
    while True:
        try:
            await ciclo_publicacion()
        except Exception as e:
            print(f"❌ [POST CRASH]: {e}")
        print(f"⏳ [POST] Siguiente tanda en {INTERVALO_SEG // 60} minutos...")
        await asyncio.sleep(INTERVALO_SEG)

if __name__ == "__main__":
    asyncio.run(main())