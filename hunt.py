import asyncio
import re
from datetime import datetime, timezone, timedelta
import requests
from playwright.async_api import async_playwright
from cfg import (
    PROF_ML, PROF_AMZ, WORKER_URL, WORKER_TOKEN,
    ML_WORD, ML_TOOL, AMZ_TAG, get_db, init_db
)
from calc import limpiar_monto
from mind import auditar

INTERVALO_SEG = 900  # 15 minutos

def link_ml_respaldo(url: str) -> str:
    limpia = url.split("#")[0].split("?")[0]
    if not limpia.startswith("http"):
        limpia = f"https://www.mercadolibre.com.mx{limpia}"
    return f"{limpia}?matt_word={ML_WORD}&matt_tool={ML_TOOL}&forceInApp=true"

def link_amz_afiliado(asin: str) -> str:
    return f"https://www.amazon.com.mx/dp/{asin}?tag={AMZ_TAG}"

def subir_a_d1(oferta_db: dict):
    payload = {
        "titulo": oferta_db["titulo"],
        "precio_oferta": f"${oferta_db['precio_oferta']:,.2f}",
        "precio_original": f"${oferta_db['precio_original']:,.2f}" if oferta_db["precio_original"] > oferta_db["precio_oferta"] else "",
        "descuento": oferta_db["descuento_txt"],
        "tienda": oferta_db["tienda"],
        "url_afiliado": oferta_db["url_afiliado"],
        "score": oferta_db["score"],
        "es_hot": 1 if oferta_db["score"] <= 2 else 0,
        "categoria_principal": oferta_db["subcategoria"][0],
        "subcategoria": oferta_db["subcategoria"],
        "razonamiento": oferta_db["razonamiento"],
        "mensaje_redes": oferta_db.get("copy_web", ""),
        "fecha_vencimiento": (datetime.now(timezone.utc) + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"),
        "imagen_url": oferta_db["imagen_url"]
    }
    try:
        r = requests.post(
            f"{WORKER_URL}/api/guardar",
            json=payload,
            headers={"Content-Type": "application/json", "Authorization": WORKER_TOKEN},
            timeout=10
        )
        if r.status_code == 200:
            print("   ☁️ [D1 OK] Sincronizada en web.")
    except Exception as e:
        print(f"   ⚠️ [D1 ERROR]: {e}")

async def _procesar_ficha_ml(ctx, sem: asyncio.Semaphore, item: dict) -> dict | None:
    async with sem:
        page = await ctx.new_page()
        url_base = item["url_normal"]
        try:
            await page.goto(url_base, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2800)

            # Extraer imagen HD oficial y urgencia dentro de la ficha
            datos_ficha = await page.evaluate("""() => {
                const og = document.querySelector('meta[property="og:image"]')?.getAttribute('content') || '';
                const imgMain = document.querySelector('img.ui-pdp-image, figure img')?.getAttribute('src') || '';
                const foto = og.startsWith('http') ? og : (imgMain.startsWith('http') ? imgMain : '');
                const t = (document.body.innerText || '').toLowerCase();
                let urg = '';
                if (t.includes('oferta relámpago') || t.includes('oferta relampago')) urg = 'relampago';
                else if (t.includes('oferta del día') || t.includes('oferta del dia')) urg = 'oferta del dia';
                return { foto, urg };
            }""")

            if datos_ficha.get("foto"):
                item["imagen_url"] = datos_ficha["foto"]
            item["urgencia"] = datos_ficha.get("urg", "")

            url_af = None
            for sel in ['button:has-text("Compartir")', 'button:has-text("Obtener enlace")', '.ui-pdp-share button']:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(1500)
                    url_af = await page.evaluate("""() => {
                        for (const inp of document.querySelectorAll('input, textarea')) {
                            if (inp.value && inp.value.includes('meli.la/')) return inp.value.trim();
                        }
                        const m = document.body.innerText.match(/https:\\/\\/meli\\.la\\/[A-Za-z0-9]+/);
                        return m ? m[0] : null;
                    }""")
                    break

            item["url_afiliado"] = url_af if (url_af and "meli.la/" in url_af) else link_ml_respaldo(url_base)
            return item
        except Exception:
            item["url_afiliado"] = link_ml_respaldo(url_base)
            return item
        finally:
            await page.close()

async def cazar_ml(urls_conocidas: set) -> list:
    print("🟡 [HUNT ML] Escaneando Mercado Libre...")
    resultados = []
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROF_ML),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-position=-2400,0"],
            viewport={"width": 1366, "height": 900},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto("https://www.mercadolibre.com.mx/ofertas", timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5500)
            for _ in range(4):
                try:
                    await page.mouse.wheel(0, 950)
                except Exception:
                    pass
                await page.wait_for_timeout(1100)

            crudos = []
            for _ in range(3):
                try:
                    crudos = await page.evaluate("""() => {
                        const out = [];
                        const vistos = new Set();
                        document.querySelectorAll('a[href*="/p/MLM"], a[href*="MLM-"], a[href*="/up/MLM"]').forEach(a => {
                            const href = (a.getAttribute('href') || '').split('#')[0].split('?')[0];
                            if (!href || vistos.has(href) || href.includes('login')) return;
                            const card = a.closest('div[class*="poly-card"], div[class*="andes-card"], li, article') || a.parentElement?.parentElement;
                            if (!card) return;
                            const titleEl = card.querySelector('h2, h3, a[class*="title"], span[class*="title"]');
                            const title = (a.getAttribute('title') || (titleEl ? titleEl.innerText : '') || '').trim();
                            let pOf = '', pOr = '';
                            const prev = card.querySelector('s .andes-money-amount__fraction, .andes-money-amount--previous .andes-money-amount__fraction');
                            if (prev) pOr = prev.innerText.replace(/[^0-9,.]/g, '');
                            for (const amt of card.querySelectorAll('.andes-money-amount')) {
                                if (amt.closest('s') || amt.classList.contains('andes-money-amount--previous') || amt.closest('[class*="installments"]')) continue;
                                const f = amt.querySelector('.andes-money-amount__fraction');
                                if (f) { pOf = f.innerText.replace(/[^0-9,.]/g, ''); break; }
                            }
                            const desc = card.querySelector('[class*="discount"]')?.innerText.trim() || 'Oferta';
                            const imgEl = card.querySelector('img');
                            const rawImg = imgEl ? (imgEl.getAttribute('data-src') || imgEl.getAttribute('src') || '') : '';
                            const img = rawImg.startsWith('http') ? rawImg : '';
                            if (title.length > 8 && pOf && !title.startsWith('$') && !title.startsWith('-')) {
                                vistos.add(href);
                                out.push({ href, title, pOf, pOr, desc, img });
                            }
                        });
                        return out;
                    }""")
                    if crudos:
                        break
                except Exception:
                    await page.wait_for_timeout(3000)

            print(f"   🔎 [ML RAW] Tarjetas leídas: {len(crudos)}")
            nuevos = []
            vistos = set()
            for c in crudos:
                u = c["href"]
                if not u.startswith("http"):
                    u = f"https://www.mercadolibre.com.mx{u}"
                if u in vistos or u in urls_conocidas or limpiar_monto(c["pOf"]) <= 0:
                    continue
                vistos.add(u)
                nuevos.append({
                    "url_normal": u,
                    "titulo": c["title"][:110],
                    "tienda": "Mercado Libre México",
                    "precio_oferta": c["pOf"],
                    "precio_original": c["pOr"],
                    "descuento": c["desc"],
                    "imagen_url": c["img"]
                })
                if len(nuevos) >= 12:
                    break

            sem = asyncio.Semaphore(3)
            tareas = [_procesar_ficha_ml(ctx, sem, it) for it in nuevos]
            procesados = await asyncio.gather(*tareas)
            resultados = [r for r in procesados if r]
        except Exception as e:
            print(f"⚠️ [HUNT ML ERROR]: {e}")
        finally:
            await ctx.close()
    return resultados

async def cazar_amz(urls_conocidas: set) -> list:
    print("🟠 [HUNT AMZ] Escaneando Amazon México...")
    resultados = []
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROF_AMZ),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-position=-2400,0"],
            viewport={"width": 1366, "height": 900},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto("https://www.amazon.com.mx/gp/goldbox", timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4500)
            for _ in range(5):
                try:
                    await page.mouse.wheel(0, 950)
                except Exception:
                    pass
                await page.wait_for_timeout(1000)

            crudos = await page.evaluate("""() => {
                const out = [];
                const vistosAsin = new Set();
                document.querySelectorAll('a[href*="/dp/"]').forEach(a => {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/\\/dp\\/([A-Z0-9]{10})/);
                    if (!m) return;
                    const asin = m[1];
                    if (vistosAsin.has(asin)) return;

                    const card = a.closest('div[data-testid="product-card"], div[data-asin], .a-cardui, .Grid--child, .celwidget, li');
                    if (!card) return;

                    let title = '';
                    const candidatos = [
                        card.querySelector('[data-testid="product-card-title"]'),
                        card.querySelector('.a-truncate-full'),
                        card.querySelector('span.a-size-base-plus'),
                        card.querySelector('span.a-size-medium'),
                        card.querySelector('h2 span'),
                        card.querySelector('img[alt]')
                    ];
                    for (const el of candidatos) {
                        if (!el) continue;
                        const txt = (el.tagName === 'IMG' ? el.getAttribute('alt') : el.innerText || '').trim();
                        if (txt.length > 10 && !txt.startsWith('$') && !txt.startsWith('-') && !txt.toLowerCase().startsWith('promoción')) {
                            title = txt;
                            break;
                        }
                    }

                    const pOf = card.querySelector('.a-price .a-offscreen, span[data-a-color="price"] .a-offscreen')?.innerText.trim() || '';
                    const pOr = card.querySelector('.a-text-price .a-offscreen, span[data-a-strike="true"] .a-offscreen')?.innerText.trim() || '';
                    const desc = card.querySelector('.a-badge-text, span[aria-label*="%"], div[data-testid="discount-badge"]')?.innerText.trim() || 'Oferta';
                    const img = card.querySelector('img')?.getAttribute('src') || '';

                    if (title.length > 10 && pOf) {
                        vistosAsin.add(asin);
                        out.push({ href, title, pOf, pOr, desc, img });
                    }
                });
                return out;
            }""")

            print(f"   🔎 [AMZ RAW] Tarjetas limpias leídas: {len(crudos)}")
            vistos = set()
            for c in crudos:
                m = re.search(r"/dp/([A-Z0-9]{10})", c["href"])
                if not m:
                    continue
                asin = m.group(1)
                u = f"https://www.amazon.com.mx/dp/{asin}"
                if u in vistos or u in urls_conocidas or limpiar_monto(c["pOf"]) <= 0:
                    continue
                vistos.add(u)
                resultados.append({
                    "url_normal": u,
                    "url_afiliado": link_amz_afiliado(asin),
                    "titulo": c["title"][:110],
                    "tienda": "Amazon México",
                    "precio_oferta": c["pOf"],
                    "precio_original": c["pOr"],
                    "descuento": c["desc"],
                    "imagen_url": c["img"],
                    "urgencia": ""
                })
                if len(resultados) >= 12:
                    break
        except Exception as e:
            print(f"⚠️ [HUNT AMZ ERROR]: {e}")
        finally:
            await ctx.close()
    return resultados

async def ciclo_caza():
    init_db()
    with get_db() as conn:
        rows = conn.execute("SELECT url_normal FROM ofertas").fetchall()
        conocidas = {r["url_normal"] for r in rows}

    ml_items, amz_items = await asyncio.gather(cazar_ml(conocidas), cazar_amz(conocidas))
    brutas = ml_items + amz_items
    print(f"🎯 [HUNT] Total nuevas por auditar: {len(brutas)}")

    for of in brutas:
        veredicto = await asyncio.to_thread(auditar, of)
        if veredicto["descartar"]:
            print(f"🗑️ [DESCARTADA] {of['titulo'][:42]} -> {veredicto['razonamiento']}")
            continue

        nums = veredicto["numeros"]
        registro = {
            "url_normal": of["url_normal"],
            "url_afiliado": of["url_afiliado"],
            "titulo": of["titulo"],
            "tienda": of["tienda"],
            "precio_oferta": nums["precio_oferta"],
            "precio_original": nums["precio_original"],
            "descuento_txt": f"-{nums['pct_real']}% OFF" if nums["pct_real"] > 0 else of.get("descuento", "Oferta"),
            "score": veredicto["score"],
            "subcategoria": veredicto["subcategoria"],
            "razonamiento": veredicto["razonamiento"],
            "copy_web": veredicto.get("copy_web", ""),
            "imagen_url": of.get("imagen_url", ""),
            "urgencia": of.get("urgencia", "")
        }

        with get_db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO ofertas (
                    url_normal, url_afiliado, titulo, tienda, precio_oferta,
                    precio_original, descuento_txt, score, subcategoria,
                    razonamiento, imagen_url, urgencia
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                registro["url_normal"], registro["url_afiliado"], registro["titulo"],
                registro["tienda"], registro["precio_oferta"], registro["precio_original"],
                registro["descuento_txt"], registro["score"], registro["subcategoria"],
                registro["copy_web"] or registro["razonamiento"], registro["imagen_url"], registro["urgencia"]
            ))

        print(f"💎 [SCORE {registro['score']}/5 | {registro['subcategoria']}] {registro['titulo'][:45]} (${registro['precio_oferta']:,.0f})")
        await asyncio.to_thread(subir_a_d1, registro)

async def main():
    while True:
        try:
            await ciclo_caza()
        except Exception as e:
            print(f"❌ [HUNT CRASH]: {e}")
        print(f"⏳ [HUNT] Esperando {INTERVALO_SEG // 60} min para siguiente cacería...")
        await asyncio.sleep(INTERVALO_SEG)

if __name__ == "__main__":
    asyncio.run(main())