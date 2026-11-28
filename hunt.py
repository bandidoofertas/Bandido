import asyncio
from pathlib import Path
import random
import re
import sys
from datetime import datetime, timezone, timedelta
import requests
from playwright.async_api import async_playwright
from cfg import (
    PROF_ML, PROF_AMZ, WORKER_URL, WORKER_TOKEN,
    ML_WORD, ML_TOOL, AMZ_TAG, get_db, init_db
)
from calc import limpiar_monto
from mind import auditar, es_contenido_adulto
from browser_queue import adquirir_perfil_navegador, chat_necesita_navegador

HORAS_VIGENCIA = 24
MODO_ACTUAL = "4"
META_OFERTAS_LLENA = 60

MODOS_HUNT = {
    "1": ("Modo 1: Rápido y Poderoso (Bucle cada ~2-3 min anti-baneo)", 135),
    "2": ("Modo 2: Pasivo (Revisión cada 1 hora)", 3600),
    "3": ("Modo 3: Descanso (Ahorro profundo cada 6 horas)", 21600),
    "4": ("Modo 4: Automático Inteligente (Llena D1 rápido -> luego patrulla cada 1h)", 135),
}


def es_temporada_alta() -> tuple[bool, str]:
    ahora = datetime.now()
    mes, dia = ahora.month, ahora.day
    if mes == 5 and 15 <= dia <= 31:
        return True, "Hot Sale"
    if mes == 7 and 8 <= dia <= 22:
        return True, "Prime Day"
    if mes == 11 and 10 <= dia <= 30:
        return True, "Temporada de Ofertas Noviembre"
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


def borrar_oferta_local(url_normal: str):
    with get_db() as conn:
        conn.execute("DELETE FROM ofertas WHERE url_normal = ?", (url_normal,))


def calcular_horas_vigencia(oferta_db: dict) -> float:
    horas_exactas = float(oferta_db.get("horas_restantes") or 0)
    if horas_exactas > 0:
        return max(0.5, min(horas_exactas, 72.0))

    urg = str(oferta_db.get("urgencia") or "").lower()
    if "relampago" in urg or "relámpago" in urg:
        return 4.0
    if "dia" in urg or "día" in urg:
        return 14.0

    score = int(oferta_db.get("score", 3))
    if score == 0:
        return 48.0
    if score == 1:
        return 36.0
    return float(HORAS_VIGENCIA)


def normalizar_url_imagen(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    return u


def es_url_imagen_valida(url: str) -> bool:
    u = normalizar_url_imagen(url)
    if not u.startswith("http"):
        return False
    low = u.lower()
    if any(bad in low for bad in ("frontend-assets", "sprite", "logo", "icon", "placeholder", "data:image", "1x1", "pixel", "verification", "captcha")):
        return False
    if low.split("?")[0].endswith(".svg"):
        return False
    return True


def rescatar_imagen_http(url: str) -> str:
    """Fallback por HTTP para sacar og:image, twitter:image o imagen mlstatic/amazon."""
    if not url or not url.startswith("http"):
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9",
        "Referer": "https://www.mercadolibre.com.mx/" if "mercadolibre" in url else "https://www.amazon.com.mx/"
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return ""
        html = r.text

        for prop in ("og:image", "twitter:image"):
            m1 = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if not m1:
                m1 = re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{prop}["\']', html, re.IGNORECASE)
            if m1 and es_url_imagen_valida(m1.group(1)):
                return normalizar_url_imagen(m1.group(1))

        m_ml = re.search(r'(?:https?:)?//(?:http2\.)?mlstatic\.com/D_[A-Za-z0-9_-]+?\.(?:webp|jpg|jpeg|png)', html, re.IGNORECASE)
        if m_ml and es_url_imagen_valida(m_ml.group(0)):
            return normalizar_url_imagen(m_ml.group(0))

        m_amz = re.search(r'https://m\.media-amazon\.com/images/I/[^"\'\s>]+?\.(?:jpg|jpeg|png|webp)', html, re.IGNORECASE)
        if m_amz and es_url_imagen_valida(m_amz.group(0)):
            return normalizar_url_imagen(m_amz.group(0))
    except Exception:
        pass
    return ""


def subir_a_d1(oferta_db: dict):
    copy_final = oferta_db.get("copy_web") or oferta_db.get("razonamiento") or ""
    horas = calcular_horas_vigencia(oferta_db)
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
        "fecha_vencimiento": oferta_db.get("fecha_vencimiento") or (datetime.now(timezone.utc) + timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S"),
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
            etiqueta_urg = f" ({oferta_db['urgencia']} -> {horas:.1f}h)" if oferta_db.get("urgencia") else f" ({horas:.0f}h)"
            print(f"   ☁️ [D1 OK] Sincronizada en web{etiqueta_urg}.")
    except Exception as e:
        print(f"   ⚠️ [D1 ERROR]: {e}")


def _estimar_pct_bruto(item: dict) -> float:
    """Ordena antes de Ollama para auditar y publicar primero los mayores descuentos."""
    p_of = limpiar_monto(item.get("precio_oferta", 0))
    p_or = limpiar_monto(item.get("precio_original", 0))
    if p_or > p_of > 0:
        return ((p_or - p_of) / p_or) * 100.0
    m = re.search(r"(\d{1,2})\s*%", str(item.get("descuento", "")))
    return float(m.group(1)) if m else 0.0


async def _procesar_ficha_ml(ctx, sem: asyncio.Semaphore, item: dict) -> dict | None:
    url_base = item["url_normal"]

    async with sem:
        page = await ctx.new_page()
        try:
            await asyncio.sleep(random.uniform(0.5, 1.1))
            await page.goto(url_base, timeout=26000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2400)

            if any(k in page.url.lower() for k in ("verification", "login", "captcha", "gz/account")):
                if not es_url_imagen_valida(item.get("imagen_url", "")):
                    item["imagen_url"] = await asyncio.to_thread(rescatar_imagen_http, url_base)
                item["url_afiliado"] = link_ml_respaldo(url_base)
                return item

            datos_ficha = await page.evaluate(r"""() => {
                const normUrl = (u) => {
                    if (!u || typeof u !== 'string') return '';
                    let s = u.trim();
                    if (s.startsWith('//')) s = 'https:' + s;
                    return s;
                };
                const esValida = (raw) => {
                    const u = normUrl(raw);
                    if (!u.startsWith('http')) return false;
                    const l = u.toLowerCase();
                    if (l.includes('frontend-assets') || l.includes('sprite') || l.includes('logo') || l.includes('icon') || l.includes('data:image')) return false;
                    if (l.split('?')[0].endsWith('.svg')) return false;
                    return true;
                };

                let foto = '';
                for (const sel of ['meta[property="og:image"]', 'meta[name="twitter:image"]', 'meta[property="twitter:image"]']) {
                    const cand = normUrl(document.querySelector(sel)?.getAttribute('content') || '');
                    if (esValida(cand)) { foto = cand; break; }
                }

                if (!foto) {
                    const mediaEls = document.querySelectorAll('img.ui-pdp-image, figure.ui-pdp-gallery__figure img, picture source, img[src*="mlstatic.com"], img[data-src*="mlstatic.com"]');
                    for (const el of mediaEls) {
                        const cands = [
                            el.currentSrc,
                            el.getAttribute('data-zoom'),
                            el.getAttribute('data-src'),
                            el.getAttribute('src')
                        ];
                        for (const c of cands) {
                            const nc = normUrl(c);
                            if (esValida(nc) && nc.includes('mlstatic.com')) { foto = nc; break; }
                        }
                        if (foto) break;
                        const srcset = el.getAttribute('srcset') || '';
                        const mSrc = srcset.match(/((?:https?:)?\/\/(?:http2\.)?mlstatic\.com\/D_[^\s,]+)/i);
                        if (mSrc && esValida(mSrc[1])) { foto = normUrl(mSrc[1]); break; }
                    }
                }

                if (!foto) {
                    const mHtml = document.documentElement.innerHTML.match(/(?:https?:)?\/\/(?:http2\.)?mlstatic\.com\/D_[A-Za-z0-9_-]+?\.(?:webp|jpg|jpeg|png)/i);
                    if (mHtml && esValida(mHtml[0])) foto = normUrl(mHtml[0]);
                }

                const t = (document.body.innerText || '').toLowerCase();
                let urg = '';
                let horasRestantes = 0;

                if (t.includes('oferta relámpago') || t.includes('oferta relampago')) {
                    urg = 'relampago';
                } else if (t.includes('oferta imperdible') || t.includes('oferta del día') || t.includes('oferta del dia')) {
                    urg = 'oferta del dia';
                }

                const mReloj = t.match(/termina\s+en\s+(\d{1,2})\s*:\s*(\d{2})(?:\s*:\s*(\d{2}))?/);
                if (mReloj) {
                    const hh = parseInt(mReloj[1], 10) || 0;
                    const mm = parseInt(mReloj[2], 10) || 0;
                    horasRestantes = hh + (mm / 60);
                    if (!urg && horasRestantes <= 8) urg = 'relampago';
                } else {
                    const mHoras = t.match(/termina\s+en\s+(\d{1,2})\s*h(?:\s*(\d{1,2})\s*m)?/);
                    if (mHoras) {
                        const hh = parseInt(mHoras[1], 10) || 0;
                        const mm = parseInt(mHoras[2] || '0', 10) || 0;
                        horasRestantes = hh + (mm / 60);
                        if (!urg && horasRestantes <= 8) urg = 'relampago';
                    }
                }

                return { foto, urg, horasRestantes };
            }""")

            if es_url_imagen_valida(datos_ficha.get("foto", "")):
                item["imagen_url"] = normalizar_url_imagen(datos_ficha["foto"])
            if datos_ficha.get("urg"):
                item["urgencia"] = datos_ficha["urg"]
            if datos_ficha.get("horasRestantes"):
                item["horas_restantes"] = float(datos_ficha["horasRestantes"])

            url_af = None
            if not chat_necesita_navegador():
                for sel in ['button:has-text("Compartir")', 'button:has-text("Obtener enlace")', '.ui-pdp-share button']:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(1400)
                        url_af = await page.evaluate(r"""() => {
                            for (const inp of document.querySelectorAll('input, textarea')) {
                                if (inp.value && inp.value.includes('meli.la/')) return inp.value.trim();
                            }
                            const m = document.body.innerText.match(/https:\/\/meli\.la\/[A-Za-z0-9]+/);
                            return m ? m[0] : null;
                        }""")
                        break

            if not es_url_imagen_valida(item.get("imagen_url", "")):
                item["imagen_url"] = await asyncio.to_thread(rescatar_imagen_http, url_base)

            item["url_afiliado"] = url_af if (url_af and "meli.la/" in url_af) else link_ml_respaldo(url_base)
            return item
        except Exception:
            if not es_url_imagen_valida(item.get("imagen_url", "")):
                item["imagen_url"] = await asyncio.to_thread(rescatar_imagen_http, url_base)
            item["url_afiliado"] = link_ml_respaldo(url_base)
            return item
        finally:
            await page.close()


async def cazar_ml(urls_conocidas: set, modo_llenado: bool = False) -> list:
    print(f"🟡 [HUNT ML] Escaneando Mercado Libre ({'barrido profundo' if modo_llenado else 'patrulla rápida'})...")
    resultados = []
    paginas_ml = [
        "https://www.mercadolibre.com.mx/ofertas",
        "https://www.mercadolibre.com.mx/ofertas?page=2",
        "https://www.mercadolibre.com.mx/ofertas?page=3",
    ] if modo_llenado else [
        "https://www.mercadolibre.com.mx/ofertas",
        f"https://www.mercadolibre.com.mx/ofertas?page={random.choice([2, 3])}",
    ]
    tope_nuevos = 22 if modo_llenado else 14

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
                crudos_totales = []
                for url_pag in paginas_ml:
                    await page.goto(url_pag, timeout=45000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(4200)

                    for paso in range(6):
                        if paso >= 3 and chat_necesita_navegador():
                            break
                        try:
                            await page.mouse.wheel(0, 1200)
                        except Exception:
                            pass
                        await page.wait_for_timeout(800)

                    lote = await page.evaluate(r"""() => {
                        const out = [];
                        const vistos = new Set();
                        const normUrl = (u) => {
                            if (!u || typeof u !== 'string') return '';
                            let s = u.trim();
                            if (s.startsWith('//')) s = 'https:' + s;
                            return s;
                        };
                        const esImgOk = (raw) => {
                            const u = normUrl(raw);
                            if (!u.startsWith('http')) return false;
                            const l = u.toLowerCase();
                            if (l.includes('frontend-assets') || l.includes('sprite') || l.includes('logo') || l.includes('icon') || l.includes('data:image')) return false;
                            if (l.split('?')[0].endsWith('.svg')) return false;
                            return true;
                        };

                        const mapaJsonImgs = {};
                        try {
                            const htmlRaw = document.documentElement.innerHTML;
                            const regexItems = /"(MLM\d{6,14})"[\s\S]{0,1200}?"((?:https?:)?\/\/(?:http2\.)?mlstatic\.com\/D_[^"]+\.(?:webp|jpg|jpeg|png))"/gi;
                            let m;
                            while ((m = regexItems.exec(htmlRaw)) !== null) {
                                if (!mapaJsonImgs[m[1]] && esImgOk(m[2])) {
                                    mapaJsonImgs[m[1]] = normUrl(m[2]);
                                }
                            }
                        } catch (e) {}

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

                            let img = '';
                            for (const mediaEl of card.querySelectorAll('img, picture source')) {
                                const cands = [
                                    mediaEl.currentSrc,
                                    mediaEl.getAttribute('data-src'),
                                    mediaEl.getAttribute('data-lazy'),
                                    mediaEl.getAttribute('data-zoom'),
                                    mediaEl.getAttribute('src')
                                ];
                                for (const c of cands) {
                                    const nc = normUrl(c);
                                    if (esImgOk(nc) && nc.includes('mlstatic.com')) { img = nc; break; }
                                }
                                if (img) break;
                                const srcset = mediaEl.getAttribute('srcset') || '';
                                const mSrc = srcset.match(/((?:https?:)?\/\/(?:http2\.)?mlstatic\.com\/D_[^\s,]+)/i);
                                if (mSrc && esImgOk(mSrc[1])) { img = normUrl(mSrc[1]); break; }
                            }

                            if (!img) {
                                const mCardHtml = (card.innerHTML || '').match(/(?:https?:)?\/\/(?:http2\.)?mlstatic\.com\/D_[A-Za-z0-9_-]+?\.(?:webp|jpg|jpeg|png)/i);
                                if (mCardHtml && esImgOk(mCardHtml[0])) img = normUrl(mCardHtml[0]);
                            }

                            if (!img) {
                                const mId = href.match(/(MLM\d{6,14})/i);
                                if (mId && mapaJsonImgs[mId[1].toUpperCase()]) {
                                    img = mapaJsonImgs[mId[1].toUpperCase()];
                                }
                            }

                            const cardTxt = (card.innerText || '').toLowerCase();
                            let urg = '';
                            if (cardTxt.includes('relámpago') || cardTxt.includes('relampago')) urg = 'relampago';
                            else if (cardTxt.includes('oferta imperdible') || cardTxt.includes('oferta del día') || cardTxt.includes('oferta del dia')) urg = 'oferta del dia';

                            if (title.length > 8 && pOf && !title.startsWith('$') && !title.startsWith('-')) {
                                vistos.add(href);
                                out.push({ href, title, pOf, pOr, desc, img, urg });
                            }
                        });
                        return out;
                    }""")
                    crudos_totales.extend(lote)
                    if chat_necesita_navegador():
                        break

                con_foto_raw = sum(1 for c in crudos_totales if es_url_imagen_valida(c.get("img", "")))
                print(f"   🔎 [ML RAW] Tarjetas leídas: {len(crudos_totales)} (con foto directa: {con_foto_raw})")

                nuevos = []
                vistos = set()
                for c in crudos_totales:
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
                        "imagen_url": normalizar_url_imagen(c["img"]) if es_url_imagen_valida(c["img"]) else "",
                        "urgencia": c.get("urg", ""),
                        "horas_restantes": 0
                    })
                    if len(nuevos) >= tope_nuevos:
                        break

                sem = asyncio.Semaphore(1)
                tareas = [_procesar_ficha_ml(ctx, sem, it) for it in nuevos]
                procesados = await asyncio.gather(*tareas)
                resultados = [r for r in procesados if r]
            except Exception as e:
                print(f"⚠️ [HUNT ML ERROR]: {e}")
            finally:
                await ctx.close()
    return resultados


async def cazar_amz(urls_conocidas: set, modo_llenado: bool = False) -> list:
    print(f"🟠 [HUNT AMZ] Escaneando Amazon México ({'barrido profundo' if modo_llenado else 'patrulla rápida'})...")
    resultados = []
    tope_nuevos = 22 if modo_llenado else 14
    pasos_scroll = 9 if modo_llenado else 5

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
                await page.wait_for_timeout(4200)
                for paso in range(pasos_scroll):
                    if paso >= 3 and chat_necesita_navegador():
                        print("   ⚡ [HUNT AMZ] Cediendo turno prioritario al chat...")
                        break
                    try:
                        await page.mouse.wheel(0, 1050)
                    except Exception:
                        pass
                    await page.wait_for_timeout(850)

                crudos = await page.evaluate(r"""() => {
                    const out = [];
                    const vistosAsin = new Set();
                    document.querySelectorAll('a[href*="/dp/"]').forEach(a => {
                        const href = a.getAttribute('href') || '';
                        const m = href.match(/\/dp\/([A-Z0-9]{10})/);
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

                        let img = '';
                        const imgEl = card.querySelector('img');
                        if (imgEl) {
                            const dyn = imgEl.getAttribute('data-a-dynamic-image');
                            if (dyn) {
                                try {
                                    const keys = Object.keys(JSON.parse(dyn));
                                    if (keys.length) img = keys[keys.length - 1];
                                } catch (e) {}
                            }
                            if (!img) img = imgEl.currentSrc || imgEl.getAttribute('src') || '';
                        }

                        const cardTxt = (card.innerText || '').toLowerCase();
                        let urg = '';
                        let horasRestantes = 0;
                        if (cardTxt.includes('relámpago') || cardTxt.includes('relampago')) {
                            urg = 'relampago';
                        } else if (cardTxt.includes('oferta del día') || cardTxt.includes('oferta del dia')) {
                            urg = 'oferta del dia';
                        }
                        const mReloj = cardTxt.match(/termina\s+en\s+(\d{1,2})\s*:\s*(\d{2})(?:\s*:\s*(\d{2}))?/);
                        if (mReloj) {
                            const hh = parseInt(mReloj[1], 10) || 0;
                            const mm = parseInt(mReloj[2], 10) || 0;
                            horasRestantes = hh + (mm / 60);
                            if (!urg && horasRestantes <= 8) urg = 'relampago';
                        }

                        if (title.length > 10 && pOf) {
                            vistosAsin.add(asin);
                            out.push({ href, title, pOf, pOr, desc, img, urg, horasRestantes });
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
                    img_final = normalizar_url_imagen(c["img"]) if es_url_imagen_valida(c["img"]) else await asyncio.to_thread(rescatar_imagen_http, u)
                    resultados.append({
                        "url_normal": u,
                        "url_afiliado": link_amz_afiliado(asin),
                        "titulo": c["title"][:110],
                        "tienda": "Amazon México",
                        "precio_oferta": c["pOf"],
                        "precio_original": c["pOr"],
                        "descuento": c["desc"],
                        "imagen_url": img_final,
                        "urgencia": c.get("urg", ""),
                        "horas_restantes": float(c.get("horasRestantes") or 0)
                    })
                    if len(resultados) >= tope_nuevos:
                        break
            except Exception as e:
                print(f"⚠️ [HUNT AMZ ERROR]: {e}")
            finally:
                await ctx.close()
    return resultados


async def ciclo_caza() -> int:
    init_db()
    try:
        from sync import auditar_y_purgar_todo
        tope_http = 10 if MODO_ACTUAL == "1" else (18 if MODO_ACTUAL in ("2", "4") else 25)
        auditar_y_purgar_todo(max_chequeos_http=tope_http)
    except Exception as e:
        print(f"⚠️ [DB AVISO]: No se pudo ejecutar auditoría de caducidad/stock: {e}")

    with get_db() as conn:
        rows = conn.execute("SELECT url_normal FROM ofertas").fetchall()
        conocidas = {r["url_normal"] for r in rows}

    modo_llenado = len(conocidas) < META_OFERTAS_LLENA

    ml_items, amz_items = await asyncio.gather(
        cazar_ml(conocidas, modo_llenado=modo_llenado),
        cazar_amz(conocidas, modo_llenado=modo_llenado)
    )

    # Intercalar ML + AMZ y ordenar por mayor descuento estimado para publicar los mejores al instante
    brutas = ml_items + amz_items
    brutas.sort(key=_estimar_pct_bruto, reverse=True)
    print(f"🎯 [HUNT] Total nuevas por auditar (priorizadas por descuento): {len(brutas)}")

    aprobadas_nuevas = 0
    for of in brutas:
        img_final = normalizar_url_imagen(of.get("imagen_url", ""))
        if not es_url_imagen_valida(img_final):
            img_final = await asyncio.to_thread(rescatar_imagen_http, of["url_normal"])

        # Filtrar antes de gastar Ollama si no tiene foto válida
        if not es_url_imagen_valida(img_final):
            print(f"⏭️ [OMITIDA SIN FOTO] {of['titulo'][:45]}")
            continue

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
            "imagen_url": img_final,
            "urgencia": of.get("urgencia", ""),
            "horas_restantes": of.get("horas_restantes", 0)
        }

        horas_venc = calcular_horas_vigencia(registro)
        fecha_venc_str = (datetime.now(timezone.utc) + timedelta(hours=horas_venc)).strftime("%Y-%m-%d %H:%M:%S")
        registro["fecha_vencimiento"] = fecha_venc_str

        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ofertas (
                    url_normal, url_afiliado, titulo, tienda, precio_oferta,
                    precio_original, descuento_txt, score, subcategoria,
                    razonamiento, imagen_url, urgencia, fecha_vencimiento, creado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                registro["url_normal"], registro["url_afiliado"], registro["titulo"],
                registro["tienda"], registro["precio_oferta"], registro["precio_original"],
                registro["descuento_txt"], registro["score"], registro["subcategoria"],
                registro["copy_web"] or registro["razonamiento"], registro["imagen_url"],
                registro["urgencia"], fecha_venc_str
            ))

        aprobadas_nuevas += 1
        print(f"💎 [{registro['tienda']} | NIVEL {registro['score']} | {registro['subcategoria']}] {registro['titulo'][:42]} (${registro['precio_oferta']:,.0f}) | IMG: OK")
        # Subida inmediata 1 a 1 para que esté disponible de inmediato en la web y bots
        if registro["score"] <= 4:
            await asyncio.to_thread(subir_a_d1, registro)

    return aprobadas_nuevas


def calcular_espera_automatica(nuevas: int, total_activas: int, rondas_secas: int) -> tuple[int, str]:
    en_temporada, nombre_temp = es_temporada_alta()

    if total_activas < META_OFERTAS_LLENA:
        espera = random.randint(120, 175)
        return espera, f"MODO 1 (Llenando D1: {total_activas}/{META_OFERTAS_LLENA} ofertas | {nombre_temp})"

    if en_temporada:
        if nuevas >= 5:
            espera = random.randint(135, 185)
            return espera, f"MODO 1 ({nombre_temp} activo con alto flujo: +{nuevas} ofertas)"
        espera = random.randint(3300, 3900)
        return espera, f"MODO 2 ({nombre_temp} activo, web llena -> patrulla cada 1h)"

    if rondas_secas >= 3:
        espera = random.randint(21000, 22200)
        return espera, f"MODO 3 DESCANSO (Sin novedades tras {rondas_secas} rondas -> ahorro 6h)"
    espera = random.randint(3400, 3800)
    return espera, f"MODO 2 AHORRO (Web llena: {total_activas} ofertas -> revisión en 1h)"


def seleccionar_modo_inicio() -> str:
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
    global MODO_ACTUAL
    modo = seleccionar_modo_inicio()
    MODO_ACTUAL = modo
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
            jitter = int(seg_fijos * 0.12)
            espera_seg = random.randint(max(120, seg_fijos - jitter), seg_fijos + jitter)
            mins = espera_seg / 60
            tiempo_txt = f"{mins:.1f} min" if mins < 90 else f"{mins / 60:.1f} horas"
            print(f"⏳ [HUNT {nombre_modo.split(':')[0]}] Nuevas: +{nuevas} | Esperando {tiempo_txt}...")

        await asyncio.sleep(espera_seg)


if __name__ == "__main__":
    asyncio.run(main())