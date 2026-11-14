import asyncio
from playwright.async_api import async_playwright
import os


def formatear_enlace_afiliado_amazon(url_producto: str) -> str:
    TAG_AFILIADO = "bandidooferta-20"
    url_limpia = url_producto.split("?")[0]
    separador = "&" if "?" in url_limpia else "?"
    return f"{url_limpia}{separador}tag={TAG_AFILIADO}"


async def extraer_ofertas_amazon_autonomo():
    ofertas = []
    user_data_dir = os.path.join("C:\\Bandido\\Bandido", "amazon_profile")

    print("🚀 [BANDIDO AMAZON] Iniciando scraper autónomo de Amazon...")
    async with async_playwright() as p:
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

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.pages[0] if context.pages else await context.new_page()

        try:
            print("🔍 Navegando a Ofertas de Amazon...")
            await page.goto("https://www.amazon.com.mx/gp/goldbox", timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            print("📜 Realizando scroll automático...")
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(1500)

            print("🔍 Extrayendo ofertas limpias de Amazon con precios y vigencia...")
            items_encontrados = await page.evaluate("""() => {
                const results = [];
                const links = document.querySelectorAll('a[href*="/dp/"]');

                links.forEach(a => {
                    const href = a.getAttribute('href');
                    let card = a.closest('.a-cardui, .octopus-dlp-asin-stream-element, div[data-p13n-asin-metadata], .celwidget, .Grid--child');
                    let title = '';
                    let priceOffer = '';
                    let priceOriginal = '';
                    let descuentoLabel = 'Oferta Amazon';
                    let imgSrc = '';
                    let urgencia = '';

                    if (card) {
                        let titleEl = card.querySelector('span.a-size-base-plus, span.a-size-medium, h2 a span, .a-link-normal span');
                        let pOfferEl = card.querySelector('.a-price .a-offscreen, .a-color-price');
                        let pOrigEl = card.querySelector('.a-text-price .a-offscreen, span.a-text-price');
                        let descEl = card.querySelector('.a-badge-text, span[aria-label*="%"], .deal-badge');
                        let imgEl = card.querySelector('img');

                        if (titleEl) title = titleEl.innerText.trim();
                        if (pOfferEl) priceOffer = pOfferEl.innerText.trim();
                        if (pOrigEl) priceOriginal = pOrigEl.innerText.trim();
                        if (descEl) descuentoLabel = descEl.innerText.trim();
                        if (imgEl) imgSrc = imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '';

                        const cardText = (card.innerText || '').toLowerCase();
                        const pistas = ['oferta relámpago', 'oferta relampago', 'termina en', 'tiempo limitado', 'oferta del día', 'oferta del dia', 'reclamado', 'pocas piezas'];
                        for (const p of pistas) {
                            if (cardText.includes(p)) {
                                urgencia = p;
                                break;
                            }
                        }
                    }

                    if (!title && a.getAttribute('title')) {
                        title = a.getAttribute('title').trim();
                    }

                    if (href && title && title.length > 8) {
                        results.push({
                            href: href,
                            title: title,
                            precio_oferta: priceOffer,
                            precio_original: priceOriginal,
                            descuento: descuentoLabel,
                            imagen_url: imgSrc,
                            urgencia_texto: urgencia
                        });
                    }
                });
                return results;
            }""")

            seen_urls = set()
            for item in items_encontrados:
                href = item["href"]
                titulo = item["title"]

                if "/dp/" in href:
                    partes = href.split("/dp/")
                    asin_parte = partes[1].split("/")[0].split("?")[0] if len(partes) > 1 else ""
                    if len(asin_parte) == 10:
                        url_limpia = f"https://www.amazon.com.mx/dp/{asin_parte}"
                    else:
                        continue
                else:
                    continue

                if url_limpia not in seen_urls:
                    seen_urls.add(url_limpia)
                    url_final_afiliado = formatear_enlace_afiliado_amazon(url_limpia)

                    p_orig = item["precio_original"]
                    p_ofer = item["precio_oferta"]
                    if p_orig == p_ofer:
                        p_orig = ""

                    ofertas.append({
                        "titulo": titulo[:100],
                        "precio_oferta": p_ofer if p_ofer else "Ver en sitio",
                        "precio_original": p_orig,
                        "descuento": item["descuento"] if item["descuento"] else "Oferta Amazon",
                        "tienda": "Amazon México",
                        "url_afiliado": url_final_afiliado,
                        "url_normal": url_limpia,
                        "imagen_url": item["imagen_url"],
                        "urgencia_texto": item.get("urgencia_texto", "")
                    })

                    if len(ofertas) >= 25:
                        break

        except Exception as e:
            print(f"⚠️ [ERROR AMAZON]: {e}")
        finally:
            await context.close()

    return ofertas