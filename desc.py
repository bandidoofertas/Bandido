import asyncio
import json
import re
import requests
from playwright.async_api import async_playwright
from cfg import (
    BASE_DIR, PROF_AMZ, PROF_ML, OLLAMA_URL, MODELO_AUDITOR,
    WORKER_URL, WORKER_TOKEN
)

PROMOS_PATH = BASE_DIR / "promos.json"

BANCOS_VALIDOS = [
    "Banamex", "BBVA", "Santander", "Banorte", "HSBC",
    "Scotiabank", "Invex", "Afirme", "Mifel", "BanCoppel",
    "OpenBank", "Nu", "RappiCard", "American Express", "PayPal",
    "Kueski Pay", "Mercado Pago", "Cupón General ML", "Bancos Participantes MSI"
]

FUENTES_EXTERNAS_PROMOS = [
    "https://www.promodescuentos.com/grupo/promociones-bancarias",
    "https://www.xataka.com.mx/categoria/cazando-gangas-mexico"
]


async def raspar_promos_amazon() -> str:
    print("🟠 [DESC AMZ] Buscando promociones bancarias y cupones en Amazon México...")
    textos = []
    urls = [
        "https://www.amazon.com.mx/b?node=16976419011",
        "https://www.amazon.com.mx/b?node=17865213011",
        "https://www.amazon.com.mx/promociones",
        "https://www.amazon.com.mx/gp/goldbox"
    ]
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROF_AMZ),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-position=-2400,0"],
            viewport={"width": 1366, "height": 900},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        for u in urls:
            try:
                await page.goto(u, timeout=35000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4500)
                for _ in range(4):
                    await page.mouse.wheel(0, 850)
                    await page.wait_for_timeout(800)
                txt = await page.evaluate(r"""() => {
                    const bloques = [];
                    const rx = /banamex|citibanamex|bbva|santander|banorte|hsbc|scotiabank|invex|afirme|mifel|bancoppel|openbank|american express|amex|paypal|kueski|bonificaci|código|cupón|msi|meses sin intereses|compra mínima/i;
                    document.querySelectorAll('section, .a-cardui, .bxc-grid__column, [data-testid*="promo"], [class*="banner"], [class*="Legal"], p, li').forEach(el => {
                        const t = (el.innerText || '').trim();
                        if (t.length > 25 && t.length < 1000 && rx.test(t)) {
                            bloques.push(t.replace(/\s+/g, ' '));
                        }
                    });
                    document.querySelectorAll('img[alt]').forEach(img => {
                        const alt = (img.getAttribute('alt') || '').trim();
                        if (alt.length > 15 && rx.test(alt)) {
                            bloques.push('[BANNER IMG] ' + alt);
                        }
                    });
                    return [...new Set(bloques)].join('\n---\n');
                }""")
                if txt:
                    textos.append(txt[:5500])
            except Exception as e:
                print(f"   ⚠️ [DESC AMZ AVISO]: {e}")
        await ctx.close()
    return "\n".join(textos)[:11000]


async def raspar_promos_ml() -> str:
    print("🟡 [DESC ML] Buscando promociones bancarias y cupones en Mercado Libre...")
    textos = []
    urls = [
        "https://www.mercadolibre.com.mx/ofertas",
        "https://www.mercadolibre.com.mx/l/promociones-bancarias",
        "https://www.mercadolibre.com.mx/cupones"
    ]
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROF_ML),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-position=-2400,0"],
            viewport={"width": 1366, "height": 900},
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        for u in urls:
            try:
                await page.goto(u, timeout=35000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4500)
                for _ in range(4):
                    await page.mouse.wheel(0, 850)
                    await page.wait_for_timeout(800)
                txt = await page.evaluate(r"""() => {
                    const bloques = [];
                    const rx = /banamex|citibanamex|bbva|santander|banorte|hsbc|scotiabank|invex|mercado pago|nu|rappicard|american express|paypal|cupón|código|bonificaci|msi|meses sin intereses|compra mínima/i;
                    document.querySelectorAll('section, article, [class*="banner"], [class*="promo"], [class*="card"], p, li').forEach(el => {
                        const t = (el.innerText || '').trim();
                        if (t.length > 25 && t.length < 1000 && rx.test(t)) {
                            bloques.push(t.replace(/\s+/g, ' '));
                        }
                    });
                    document.querySelectorAll('img[alt]').forEach(img => {
                        const alt = (img.getAttribute('alt') || '').trim();
                        if (alt.length > 15 && rx.test(alt)) {
                            bloques.push('[BANNER IMG] ' + alt);
                        }
                    });
                    return [...new Set(bloques)].join('\n---\n');
                }""")
                if txt:
                    textos.append(txt[:5500])
            except Exception as e:
                print(f"   ⚠️ [DESC ML AVISO]: {e}")
        await ctx.close()
    return "\n".join(textos)[:11000]


def raspar_fuentes_recopiladoras() -> str:
    """Consulta sitios recopiladores en México para cruzar cupones y bonificaciones bancarias activas."""
    print("🌐 [DESC WEB] Consultando recopiladores de promos bancarias en México...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"}
    hallazgos = []
    rx = re.compile(
        r"(amazon|mercado libre|banamex|citibanamex|bbva|santander|banorte|hsbc|scotiabank|invex|nu|mercado pago|bonificaci|cupón|código|msi)",
        re.IGNORECASE
    )
    for url in FUENTES_EXTERNAS_PROMOS:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                limpio = re.sub(r"<[^>]+>", " ", r.text)
                limpio = re.sub(r"\s+", " ", limpio)
                for m in rx.finditer(limpio):
                    ini = max(0, m.start() - 120)
                    fin = min(len(limpio), m.end() + 220)
                    frag = limpio[ini:fin].strip()
                    if any(t in frag.lower() for t in ("amazon", "mercado libre")) and len(frag) > 60:
                        hallazgos.append(frag)
        except Exception:
            pass
    unicos = list(dict.fromkeys(hallazgos))
    return "\n---\n".join(unicos)[:7000]


def estructurar_con_ollama(tienda: str, texto_crudo: str, campana: str) -> list:
    if not texto_crudo.strip():
        return []

    prompt = (
        f"Eres un extractor experto de promociones bancarias y cupones en México para {tienda} durante '{campana}'.\n"
        "Analiza el siguiente texto extraído de la tienda y recopiladores, y devuelve ÚNICAMENTE un JSON con una lista de objetos.\n"
        f"Ignora promociones claramente vencidas de otros meses, pero INCLUYE todas las bonificaciones bancarias, MSI con descuento o cupones vigentes para {tienda}.\n"
        "Cada objeto DEBE tener exactamente estas claves:\n"
        '{"banco": "NombreBanco", "code": "CODIGO_O_VACIO", "pct": 10, "fijo": 0, "min": 3500, "tope": 500, "desc": "Resumen claro en 1 frase"}\n'
        f"Bancos permitidos: {', '.join(BANCOS_VALIDOS)}.\n"
        'Reglas: pct, fijo, min y tope deben ser números enteros (usa 0 si no aplica). Si no hay código escrito (bonificación directa con tarjeta), deja "code": "".\n'
        "Si no encuentras ninguna promoción bancaria clara y vigente, responde exactamente: []\n\n"
        f"TEXTO EXTRAÍDO:\n{texto_crudo}"
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_AUDITOR,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1400}
            },
            timeout=90
        )
        if r.status_code == 200:
            raw = r.json().get("response", "").strip()
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                lista = json.loads(m.group(0))
                limpios = []
                vistos = set()
                for item in lista:
                    banco = str(item.get("banco", "")).strip()
                    if not banco or banco in vistos:
                        continue
                    vistos.add(banco)
                    limpios.append({
                        "banco": banco,
                        "code": str(item.get("code", "")).strip().upper(),
                        "pct": int(item.get("pct", 0) or 0),
                        "fijo": int(item.get("fijo", 0) or 0),
                        "min": int(item.get("min", 0) or 0),
                        "tope": int(item.get("tope", 0) or 0),
                        "desc": str(item.get("desc", "")).strip()
                    })
                return limpios
    except Exception as e:
        print(f"⚠️ [OLLAMA DESC ERROR] ({tienda}): {e}")
    return []


def agregar_manual_consola(tienda_nombre: str, lista_actual: list) -> list:
    while True:
        resp = input(f"➕ ¿Deseas agregar o corregir algún cupón/banco manualmente en {tienda_nombre}? [s/n]: ").strip().lower()
        if resp != "s":
            break
        banco = input("   Nombre del banco (ej. BBVA, Banamex, Nu, Cupón General ML): ").strip()
        if not banco:
            continue
        code = input("   Código de cupón (deja vacío y da Enter si es bonificación directa): ").strip().upper()
        pct = int(input("   Porcentaje de descuento/bonificación (ej. 10, o 0 si es monto fijo): ").strip() or "0")
        fijo = int(input("   Descuento fijo en pesos (ej. 500, o 0 si es porcentaje): ").strip() or "0")
        minimo = int(input("   Compra mínima en pesos (ej. 3500, o 0 si no pide): ").strip() or "0")
        tope = int(input("   Tope máximo de bonificación en pesos (ej. 1000, o 0): ").strip() or "0")
        desc = input("   Descripción corta para el usuario (ej. 10% de bonificación pagando a MSI): ").strip()
        if not desc:
            desc = f"{pct}% de bonificación" if pct else f"${fijo} de descuento"

        lista_actual = [x for x in lista_actual if x["banco"].lower() != banco.lower()]
        lista_actual.append({
            "banco": banco,
            "code": code,
            "pct": pct,
            "fijo": fijo,
            "min": minimo,
            "tope": tope,
            "desc": desc
        })
        print(f"   ✅ {banco} agregado a {tienda_nombre}.")
    return lista_actual


def guardar_y_sincronizar(campana: str, amz_lista: list, ml_lista: list):
    promos_local = {"amazon": {}, "mercadolibre": {}}
    for item in amz_lista:
        promos_local["amazon"][item["banco"]] = [{
            "code": item["code"],
            "pct": item["pct"],
            "fijo": item["fijo"],
            "min": item["min"],
            "tope": item["tope"],
            "desc": item["desc"]
        }]
    for item in ml_lista:
        promos_local["mercadolibre"][item["banco"]] = [{
            "code": item["code"],
            "pct": item["pct"],
            "fijo": item["fijo"],
            "min": item["min"],
            "tope": item["tope"],
            "desc": item["desc"]
        }]

    PROMOS_PATH.write_text(json.dumps(promos_local, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 [LOCAL OK] promos.json actualizado ({len(amz_lista)} en Amazon, {len(ml_lista)} en ML).")

    payload_web = {
        "campana": campana,
        "tiendas": {
            "amazon": [
                {"banco": i["banco"], "code": i["code"], "desc": i["desc"]}
                for i in amz_lista
            ],
            "mercadolibre": [
                {"banco": i["banco"], "code": i["code"], "desc": i["desc"]}
                for i in ml_lista
            ]
        }
    }

    try:
        r = requests.post(
            f"{WORKER_URL}/api/promos/actualizar",
            json=payload_web,
            headers={"Content-Type": "application/json", "Authorization": WORKER_TOKEN},
            timeout=15
        )
        if r.status_code == 200:
            print(f"☁️ [WEB OK] Cupones de '{campana}' publicados en {WORKER_URL}.")
        else:
            print(f"⚠️ [WEB ERROR] Código {r.status_code}: {r.text}")
    except Exception as e:
        print(f"⚠️ [WEB ERROR] No se pudo conectar con el Worker: {e}")


async def main():
    print("====================================================")
    print("🦝 BANDIDO OFERTAS - ACTUALIZADOR DE PROMOS Y CUPONES")
    print("====================================================")
    print("1. Escanear y actualizar promos vigentes (ej. BLACK FRIDAY, HOT SALE)")
    print("2. Limpiar/eliminar todas las promos actuales (sin campaña activa)")
    opcion = input("\nElige una opción [1/2]: ").strip()

    if opcion == "2":
        guardar_y_sincronizar("PROMOS", [], [])
        print("✅ Todas las promos viejas fueron eliminadas de la web y del bot.")
        return

    campana = input("Nombre del evento para el botón web (ej. BLACK FRIDAY): ").strip().upper()
    if not campana:
        campana = "PROMOS"

    txt_amz, txt_ml = await asyncio.gather(raspar_promos_amazon(), raspar_promos_ml())
    txt_web = await asyncio.to_thread(raspar_fuentes_recopiladoras)

    print("🧠 [OLLAMA] Analizando condiciones bancarias y filtrando promos vigentes...")
    amz_lista = estructurar_con_ollama("Amazon México", f"{txt_amz}\n\n{txt_web}", campana)
    ml_lista = estructurar_con_ollama("Mercado Libre México", f"{txt_ml}\n\n{txt_web}", campana)

    print("\n📋 RESUMEN DETECTADO:")
    print(f"  🛒 Amazon ({len(amz_lista)}): {[x['banco'] + (' ['+x['code']+']' if x['code'] else '') for x in amz_lista]}")
    print(f"  🤝 Mercado Libre ({len(ml_lista)}): {[x['banco'] + (' ['+x['code']+']' if x['code'] else '') for x in ml_lista]}")

    amz_lista = agregar_manual_consola("Amazon México", amz_lista)
    ml_lista = agregar_manual_consola("Mercado Libre México", ml_lista)

    confirmar = input("\n¿Publicar estos cambios en promos.json y en bandidoofertas.com? [s/n]: ").strip().lower()
    if confirmar == "s":
        guardar_y_sincronizar(campana, amz_lista, ml_lista)
    else:
        print("❌ Operación cancelada. No se modificó ningún archivo.")


if __name__ == "__main__":
    asyncio.run(main())