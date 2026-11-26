import asyncio
from pathlib import Path
import random
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
import requests
from playwright.async_api import async_playwright
import cfg
from cfg import (
    PROF_ML, PROF_AMZ, WORKER_URL, WORKER_TOKEN,
    ML_WORD, ML_TOOL, AMZ_TAG, get_db, init_db
)
from calc import limpiar_monto
from mind import auditar, es_contenido_adulto
from browser_queue import adquirir_perfil_navegador, chat_necesita_navegador

HORAS_VIGENCIA = 24
META_OFERTAS_LLENA = 35  # Cantidad de ofertas activas para considerar llena la web

BASE_DIR = Path(__file__).resolve().parent
PROF_WALMART = BASE_DIR / "prof_walmart"
PROF_AURRERA = BASE_DIR / "prof_aurrera"

IMPACT_BASE = getattr(cfg, "IMPACT_BASE", "")

MODOS_HUNT = {
    "1": ("Modo 1: Rápido y Poderoso (Bucle cada ~2-3 min anti-baneo)", 135),
    "2": ("Modo 2: Pasivo (Revisión cada 1 hora)", 3600),
    "3": ("Modo 3: Descanso (Ahorro profundo cada 6 horas)", 21600),
    "4": ("Modo 4: Automático Inteligente (Adapta velocidad según stock y temporada)", 135),
}


def es_temporada_alta() -> tuple[bool, str]:
    """Detecta temporadas de alto volumen de ofertas en México."""
    ahora = datetime.now()
    mes, dia = ahora.month, ahora.day
    if mes == 5 and 15 <= dia <= 31:
        return True, "Hot Sale"
    if mes == 7 and 8 <= dia <= 22:
        return True, "Prime Day"
    if mes == 11 and 10 <= dia <= 30:
        return True, "Buen Fin / Black Friday / Cyber Monday"
    if mes == 12 and 1 <= dia <= 24:
        return True, "Temporada Navideña"
    return False, "Temporada Normal"


def contar_ofertas_activas() -> int:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM ofertas").fetchone()
            return int(row["total"]) if row else 0
    except Exception:
        return 0


def link_ml_respaldo(url: str) -> str:
    limpia = url.split("#")[0].split("?")[0]
    if not limpia.startswith("http"):
        limpia = f"https://www.mercadolibre.com.mx{limpia}"
    return f"{limpia}?matt_word={ML_WORD}&matt_tool={ML_TOOL}&forceInApp=true"


def link_amz_afiliado(asin: str) -> str:
    return f"https://www.amazon.com.mx/dp/{asin}?tag={AMZ_TAG}"


def link_generico_afiliado(url_limpia: str, tienda: str) -> str:
    sep = "&" if "?" in url_limpia else "?"
    if IMPACT_BASE and ("walmart" in tienda.lower() or "aurrera" in tienda.lower()):
        return f"{IMPACT_BASE}?u={quote_plus(url_limpia)}"
    return f"{url_limpia}{sep}utm_source=bandidoofertas&utm_medium=affiliate"


def borrar_oferta_local(url_normal: str):
    with get_db() as conn:
        conn.execute("DELETE FROM ofertas WHERE url_normal = ?", (url_normal,))


def subir_a_d1(oferta_db: dict):
    copy_final = oferta_db.get("copy_web") or oferta_db.get("razonamiento") or ""
    horas = 48 if oferta_db["score"] == 0 else (36 if oferta_db["score"] == 1 else HORAS_VIGENCIA)
    cat_principal = oferta_db["subcategoria"].split("-")[0]
    payload = {
        "titulo": oferta_db["titulo"],
        "precio_oferta": f"${oferta_db['precio_oferta']:,.2f}",
        "precio_original": f"${oferta_db['precio_original']:,.2f}" if oferta_db["precio_original"] > oferta_db["precio_oferta"] else "",
        "descuento": oferta_db["descuento_txt"],
        "tienda": oferta_db["tienda"],
        "url_afiliado": oferta_db["url_afiliado"],
        "score": oferta_db["score"],
        "es_hot": 1 if oferta_db["score"] <= 2 else 0,
        "categoria_principal": cat_principal,
        "subcategoria": oferta_db["subcategoria"],
        "razonamiento": copy_final,
        "mensaje_redes": copy_final,
        "fecha_vencimiento": (datetime.now(timezone.utc) + timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S"),
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
    if chat_necesita_navegador():
        item["url_afiliado"] = link_ml_respaldo(item["url_normal"])
        return item

    async with sem:
        page = await ctx.new_page()
        url_base = item["url_normal"]
        try:
            await page.goto(url_base, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2800)

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
    async with adquirir_perfil_navegador(Path(PROF_ML), origen="hunt"):
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
                for _ in range(5):
                    if chat_necesita_navegador():
                        print("   ⚡ [HUNT ML] Cediendo turno prioritario al chat...")
                        break
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
                    if es_contenido_adulto(c["title"]):
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
                    if len(nuevos) >= 16:
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
    async with adquirir_perfil_navegador(Path(PROF_AMZ), origen="hunt"):
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
                    if chat_necesita_navegador():
                        print("   ⚡ [HUNT AMZ] Cediendo turno prioritario al chat...")
                        break
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
                    if es_contenido_adulto(c["title"]):
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
                    if len(resultados) >= 14:
                        break
            except Exception as e:
                print(f"⚠️ [HUNT AMZ ERROR]: {e}")
            finally:
                await ctx.close()
    return resultados


async def _cazar_walmart_grupo(nombre_tienda: str, dominio: str, ruta_perfil: Path, urls_conocidas: set) -> list:
    print(f"🔵 [HUNT {nombre_tienda.upper()}] Escaneando ofertas con perfil persistente...")
    ruta_perfil.mkdir(parents=True, exist_ok=True)
    resultados = []
    async with adquirir_perfil_navegador(ruta_perfil, origen="hunt"):
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(ruta_perfil),
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--window-position=-2400,0"],
                viewport={"width": 1366, "height": 900},
                locale="es-MX",
                timezone_id="America/Mexico_City"
            )
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            try:
                await page.goto(f"{dominio}/shop/rebajas", timeout=45000, wait_until="domcontentloaded")
                await page.wait_for_timeout(5500)

                hay_items = await page.locator('a[href*="/ip/"]').count()
                if hay_items == 0:
                    await page.goto(f"{dominio}/search?q=ofertas+y+rebajas", timeout=45000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(5500)

                for _ in range(5):
                    if chat_necesita_navegador():
                        break
                    try:
                        await page.mouse.wheel(0, 900)
                    except Exception:
                        pass
                    await page.wait_for_timeout(1100)

                crudos = await page.evaluate("""() => {
                    const out = [];
                    const vistos = new Set();
                    document.querySelectorAll('a[href*="/ip/"]').forEach(a => {
                        const href = (a.getAttribute('href') || '').split('#')[0].split('?')[0];
                        if (!href || vistos.has(href)) return;
                        const card = a.closest('[data-item-id], [role="group"], div[class*="sans-serif"], li, article') || a.parentElement?.parentElement;
                        if (!card) return;

                        const titleEl = card.querySelector('[data-automation-id="product-title"], span[class*="lh-title"], h2, h3');
                        const title = ((titleEl ? titleEl.innerText : '') || a.getAttribute('aria-label') || a.innerText || '').trim();
                        const textoCard = card.innerText || '';

                        const precios = [...textoCard.matchAll(/\\$\\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\\.[0-9]{2})?)/g)].map(m => m[1]);
                        if (precios.length < 2 && !textoCard.toLowerCase().includes('ahorra')) return;

                        const pOf = precios[0];
                        const pOr = precios.length > 1 ? precios[1] : '';

                        const imgEl = card.querySelector('img');
                        const img = imgEl ? (imgEl.getAttribute('src') || '') : '';

                        if (title.length > 10 && !title.startsWith('$')) {
                            vistos.add(href);
                            out.push({ href, title, pOf, pOr, img });
                        }
                    });
                    return out;
                }""")

                print(f"   🔎 [{nombre_tienda.upper()} RAW] Tarjetas leídas: {len(crudos)}")
                vistos = set()
                for c in crudos:
                    u = c["href"]
                    if not u.startswith("http"):
                        u = f"{dominio}{u}"
                    p_of_num = limpiar_monto(c["pOf"])
                    p_or_num = limpiar_monto(c["pOr"])
                    if p_or_num > 0 and p_or_num < p_of_num:
                        p_of_num, p_or_num = p_or_num, p_of_num

                    if u in vistos or u in urls_conocidas or p_of_num <= 0:
                        continue
                    if es_contenido_adulto(c["title"]):
                        continue
                    vistos.add(u)
                    resultados.append({
                        "url_normal": u,
                        "url_afiliado": link_generico_afiliado(u, nombre_tienda),
                        "titulo": c["title"][:110],
                        "tienda": nombre_tienda,
                        "precio_oferta": p_of_num,
                        "precio_original": p_or_num,
                        "descuento": "Oferta",
                        "imagen_url": c["img"],
                        "urgencia": ""
                    })
                    if len(resultados) >= 12:
                        break
            except Exception as e:
                print(f"⚠️ [HUNT {nombre_tienda.upper()} ERROR]: {e}")
            finally:
                await ctx.close()
    return resultados


async def ciclo_caza() -> int:
    init_db()
    try:
        from sync import limpiar_caducados_24h
        limpiar_caducados_24h()
    except Exception as e:
        print(f"⚠️ [DB AVISO]: No se pudo ejecutar limpieza de 24h: {e}")

    with get_db() as conn:
        rows = conn.execute("SELECT url_normal FROM ofertas").fetchall()
        conocidas = {r["url_normal"] for r in rows}

    ml_items, amz_items = await asyncio.gather(
        cazar_ml(conocidas),
        cazar_amz(conocidas)
    )
    wm_items, ba_items = await asyncio.gather(
        _cazar_walmart_grupo("Walmart México", "https://www.walmart.com.mx", PROF_WALMART, conocidas),
        _cazar_walmart_grupo("Bodega Aurrera", "https://www.bodegaaurrera.com.mx", PROF_AURRERA, conocidas)
    )

    brutas = ml_items + amz_items + wm_items + ba_items
    print(f"🎯 [HUNT] Total nuevas/reanalizables por auditar: {len(brutas)}")

    aprobadas_nuevas = 0
    for of in brutas:
        veredicto = await asyncio.to_thread(auditar, of)
        if veredicto["descartar"]:
            borrar_oferta_local(of["url_normal"])
            print(f"🗑️ [DESCARTADA Y BORRADA] {of['titulo'][:42]} -> {veredicto['razonamiento']}")
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
                INSERT OR REPLACE INTO ofertas (
                    url_normal, url_afiliado, titulo, tienda, precio_oferta,
                    precio_original, descuento_txt, score, subcategoria,
                    razonamiento, imagen_url, urgencia, creado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                registro["url_normal"], registro["url_afiliado"], registro["titulo"],
                registro["tienda"], registro["precio_oferta"], registro["precio_original"],
                registro["descuento_txt"], registro["score"], registro["subcategoria"],
                registro["copy_web"] or registro["razonamiento"], registro["imagen_url"], registro["urgencia"]
            ))

        aprobadas_nuevas += 1
        print(f"💎 [{registro['tienda']} | TIER {registro['score']} | {registro['subcategoria']}] {registro['titulo'][:42]} (${registro['precio_oferta']:,.0f})")
        if registro["score"] <= 4:
            await asyncio.to_thread(subir_a_d1, registro)

    return aprobadas_nuevas


def calcular_espera_automatica(nuevas: int, total_activas: int, rondas_secas: int) -> tuple[int, str]:
    en_temporada, nombre_temp = es_temporada_alta()

    # 1. Si D1 aún no está llena (< 35 ofertas), acelerar en Modo 1 para poblar rápido
    if total_activas < META_OFERTAS_LLENA:
        espera = random.randint(120, 175)  # 2 a ~3 min con jitter anti-baneo
        return espera, f"MODO 1 (Llenando D1: {total_activas}/{META_OFERTAS_LLENA} ofertas | {nombre_temp})"

    # 2. En épocas fuertes (Buen Fin, Black Friday, Hot Sale, etc.) NUNCA entra en modo descanso (6h)
    if en_temporada:
        if nuevas >= 4:
            espera = random.randint(130, 180)
            return espera, f"MODO 1 ({nombre_temp} activo con alto flujo: +{nuevas} ofertas)"
        espera = random.randint(3300, 3900)  # ~1 hora
        return espera, f"MODO 2 ({nombre_temp} activo, web llena -> patrulla cada 1h)"

    # 3. Temporada normal con web llena: varía entre Modo 1, Modo 2 (1h) y Modo 3 Descanso (6h)
    if nuevas >= 5:
        espera = random.randint(135, 185)
        return espera, f"MODO 1 (Racha alta detectada: +{nuevas} ofertas)"
    if rondas_secas >= 2:
        espera = random.randint(21000, 22200)  # ~6 horas
        return espera, f"MODO 3 DESCANSO (Sin novedades tras {rondas_secas} rondas -> ahorro 6h)"
    espera = random.randint(3400, 3800)  # ~1 hora
    return espera, f"MODO 2 PASIVO (Web llena: {total_activas} ofertas -> revisión en 1h)"


def seleccionar_modo_inicio() -> str:
    # Permite arrancar directo por consola: python hunt.py --modo 4
    if "--modo" in sys.argv:
        idx = sys.argv.index("--modo")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] in MODOS_HUNT:
            return sys.argv[idx + 1]

    en_temp, nombre_temp = es_temporada_alta()
    print("\n=== 🦝 SELECTOR DE VELOCIDAD BANDIDO HUNT ===")
    print(f"📅 Estado de calendario: {nombre_temp}")
    for k, (desc, _) in MODOS_HUNT.items():
        print(f"  [{k}] {desc}")
    print("  [0] Salir")

    while True:
        op = input("Elige el modo de cacería [Enter = 4 Automático]: ").strip()
        if op == "":
            return "4"
        if op == "0":
            sys.exit(0)
        if op in MODOS_HUNT:
            return op


async def main():
    modo = seleccionar_modo_inicio()
    nombre_modo, seg_fijos = MODOS_HUNT[modo]
    print(f"\n🚀 Iniciando cacería en: {nombre_modo}\n")

    rondas_secas = 0
    while True:
        nuevas = 0
        try:
            nuevas = await ciclo_caza()
        except Exception as e:
            print(f"❌ [HUNT CRASH]: {e}")

        if nuevas <= 1:
            rondas_secas += 1
        else:
            rondas_secas = 0

        if modo == "4":
            total_activas = contar_ofertas_activas()
            espera_seg, etiqueta = calcular_espera_automatica(nuevas, total_activas, rondas_secas)
            mins = espera_seg / 60
            tiempo_txt = f"{mins:.1f} min" if mins < 90 else f"{mins / 60:.1f} horas"
            print(f"🧠 [AUTO] Nuevas: +{nuevas} | Activas: {total_activas} -> {etiqueta} (próxima en {tiempo_txt})")
        else:
            # Agrega variación aleatoria del ±12% para evitar patrones robóticos
            jitter = int(seg_fijos * 0.12)
            espera_seg = random.randint(max(120, seg_fijos - jitter), seg_fijos + jitter)
            mins = espera_seg / 60
            tiempo_txt = f"{mins:.1f} min" if mins < 90 else f"{mins / 60:.1f} horas"
            print(f"⏳ [HUNT {nombre_modo.split(':')[0]}] Nuevas: +{nuevas} | Esperando {tiempo_txt}...")

        await asyncio.sleep(espera_seg)


if __name__ == "__main__":
    asyncio.run(main())