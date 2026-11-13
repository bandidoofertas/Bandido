import asyncio
from playwright.async_api import async_playwright
import os
import re

def respaldo_enlace_ml(url_producto: str) -> str:
    """Respaldo seguro si la barra de afiliados de ML no responde en algún producto."""
    if not url_producto or "login" in url_producto or "cart" in url_producto:
        return None
    url_limpia = url_producto.split('#')[0].split('?')[0]
    if not url_limpia.startswith("http"):
        url_limpia = f"https://www.mercadolibre.com.mx{url_limpia}"
    return f"{url_limpia}?matt_word=cofa20231216170418&matt_tool=92220708&forceInApp=true"

async def obtener_enlace_afiliado_real(page_prod, url_producto: str) -> tuple[str, bool]:
    """
    Reutiliza una pestaña autenticada (browser_profile) para extraer
    el enlace corto oficial meli.la desde la barra de afiliados de Mercado Libre.
    """
    url_base = url_producto.split('#')[0].split('?')[0]
    if not url_base.startswith("http"):
        url_base = f"https://www.mercadolibre.com.mx{url_base}"

    try:
        await page_prod.goto(url_base, timeout=30000, wait_until="domcontentloaded")
        await page_prod.wait_for_timeout(3200)

        selectores_boton = [
            'button:has-text("Compartir")',
            'button:has-text("Obtener enlace")',
            '[data-testid*="affiliate"] button',
            '.ui-pdp-share button',
            'button[aria-label*="Compartir"]'
        ]

        clic_exitoso = False
        for sel in selectores_boton:
            btn = page_prod.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                clic_exitoso = True
                await page_prod.wait_for_timeout(1800)
                break

        if clic_exitoso:
            enlace_meli = await page_prod.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input[type="text"], input[readonly], textarea'));
                for (const inp of inputs) {
                    if (inp.value && inp.value.includes('meli.la/')) return inp.value.trim();
                }
                const match = document.body.innerText.match(/https:\\/\\/meli\\.la\\/[A-Za-z0-9]+/);
                return match ? match[0] : null;
            }""")

            if enlace_meli and "meli.la/" in enlace_meli:
                print(f"   💰 [AFILIADO REAL ML] Enlace oficial obtenido: {enlace_meli}")
                return enlace_meli, True

        print(f"   ⚠️ [AFILIADO ML] Barra no disponible en este ítem. Aplicando respaldo seguro.")
        return respaldo_enlace_ml(url_base), False

    except Exception as e:
        print(f"   ⚠️ [AFILIADO ML ERROR] {e}. Usando respaldo seguro.")
        return respaldo_enlace_ml(url_base), False

async def extraer_ofertas_ml_autonomo():
    ofertas = []
    user_data_dir = os.path.join("C:\\Bandido\\Bandido", "browser_profile")
    
    print("🚀 [BANDIDO ML v2] Extrayendo ofertas con sesión autenticada...")
    p = await async_playwright().start()
    context = None
    try:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized"
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = context.pages[0] if context.pages else await context.new_page()
        
        await page.goto("https://www.mercadolibre.com.mx/ofertas", timeout=60000, wait_until="load")
        await page.wait_for_selector('.andes-card, .poly-card', timeout=15000)
        await page.wait_for_timeout(2000)
        
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, 1000)")
            await page.wait_for_timeout(1200)

        items_encontrados = []
        for intento in range(3):
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                items_encontrados = await page.evaluate("""() => {
                    const results = [];
                    const cards = document.querySelectorAll('.andes-card, .poly-card, .promotions-pill-item, li.ui-search-layout__item');
                    
                    cards.forEach(card => {
                        const a = card.querySelector('a[href]');
                        if (!a) return;
                        const href = a.getAttribute('href');
                        let title = a.getAttribute('title') || card.querySelector('h2, .poly-component__title')?.innerText || '';
                        title = title.trim().replace(/\\s+/g, ' ');
                        
                        let priceOffer = '';
                        let priceOriginal = '';
                        let descuentoLabel = 'Oferta';
                        let imgSrc = '';
                        
                        const prevEl = card.querySelector('s .andes-money-amount__fraction, .andes-money-amount--previous .andes-money-amount__fraction, s');
                        if (prevEl) {
                            priceOriginal = prevEl.innerText.replace(/[^0-9,.]/g, '').trim();
                        }

                        const allAmounts = card.querySelectorAll('.andes-money-amount');
                        for (let amt of allAmounts) {
                            if (amt.tagName === 'S' || amt.closest('s') || amt.classList.contains('andes-money-amount--previous')) continue;
                            if (amt.closest('.poly-price__installments, .ui-search-installments')) continue;
                            
                            const frac = amt.querySelector('.andes-money-amount__fraction');
                            if (frac) {
                                priceOffer = frac.innerText.replace(/[^0-9,.]/g, '').trim();
                                break;
                            }
                        }

                        if (!priceOffer) {
                            const fallback = card.querySelector('.price-tag-fraction');
                            if (fallback) priceOffer = fallback.innerText.replace(/[^0-9,.]/g, '').trim();
                        }

                        const descEl = card.querySelector('.andes-money-amount__discount, .promotions-pill-label, span[class*="discount"], .poly-price__discount');
                        if (descEl) descuentoLabel = descEl.innerText.trim();
                        
                        const imgEl = card.querySelector('img');
                        if (imgEl) imgSrc = imgEl.getAttribute('data-src') || imgEl.getAttribute('src') || '';
                        
                        if (href && title && title.length > 10) {
                            if ((href.includes('/p/MLM') || href.includes('MLM-') || href.includes('_NoIndex_')) && !href.includes('login')) {
                                results.push({ 
                                    href: href, 
                                    title: title,
                                    precio_oferta: priceOffer ? '$' + priceOffer : '',
                                    precio_original: priceOriginal ? '$' + priceOriginal : '',
                                    descuento: descuentoLabel,
                                    imagen_url: imgSrc 
                                });
                            }
                        }
                    });
                    return results;
                }""")
                if items_encontrados:
                    break
            except Exception as nav_err:
                if "Execution context was destroyed" in str(nav_err) and intento < 2:
                    print("   🔄 Mercado Libre redirigió la vista, reintentando lectura...")
                    await page.wait_for_timeout(2500)
                    continue
                raise nav_err
        
        page_prod = await context.new_page()
        seen_urls = set()
        for item in items_encontrados:
            href = item["href"]
            url_normal = href.split('#')[0].split('?')[0]
            if not url_normal or url_normal in seen_urls or "login" in url_normal:
                continue
            seen_urls.add(url_normal)
            
            url_afiliado, afiliado_real = await obtener_enlace_afiliado_real(page_prod, url_normal)
            if not url_afiliado:
                continue
            
            p_oferta_str = item["precio_oferta"]
            p_orig_str = item["precio_original"]
            desc_str = item["descuento"]
            
            if not p_orig_str and p_oferta_str and "%" in desc_str:
                try:
                    num_oferta = float(re.sub(r'[^0-9.]', '', p_oferta_str.replace(',', '')))
                    match_pct = re.search(r'([0-9]+)\s*%', desc_str)
                    if match_pct and num_oferta > 0:
                        pct = float(match_pct.group(1))
                        if 0 < pct < 99:
                            num_orig = num_oferta / (1.0 - (pct / 100.0))
                            p_orig_str = f"${num_orig:,.0f}"
                except:
                    pass

            ofertas.append({
                "titulo": item["title"][:100],
                "precio_oferta": p_oferta_str if p_oferta_str else "Ver en sitio",
                "precio_original": p_orig_str if p_orig_str != p_oferta_str else "",
                "descuento": desc_str if desc_str else "Oferta",
                "tienda": "Mercado Libre México",
                "url_afiliado": url_afiliado,
                "url_normal": url_normal,
                "afiliado_confirmado": afiliado_real,
                "imagen_url": item["imagen_url"]
            })
            
            if len(ofertas) >= 15:
                break
                
    except Exception as e:
        print(f"⚠️ [ERROR MERCADO LIBRE]: {e}")
    finally:
        if context:
            try:
                await context.close()
            except:
                pass
        try:
            await p.stop()
        except:
            pass
            
    return ofertas