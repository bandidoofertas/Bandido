import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from cfg import PROF_ML, PROF_AMZ, PROF_FB_POST, PROF_FB_CHAT

BASE_DIR = Path(__file__).resolve().parent
PROF_WHATSAPP = BASE_DIR / "prof_whatsapp"
PROF_WALMART = BASE_DIR / "prof_walmart"
PROF_AURRERA = BASE_DIR / "prof_aurrera"

META_HOME_URL = (
    "https://business.facebook.com/latest/home?"
    "asset_id=1410612968801274&nav_ref=biz_unified_f3_login_page_to_mbs&"
    "biz_login_source=biz_unified_f3_fb_login_button&join_id=fd8d1d92-2e8c-477e-aaf3-c2809d8a3720"
)

PERFILES = {
    "1": ("Mercado Libre (Afiliados)", PROF_ML, "https://www.mercadolibre.com.mx"),
    "2": ("Amazon México", PROF_AMZ, "https://www.amazon.com.mx"),
    "3": ("Meta Business Suite (Publicador Facebook)", PROF_FB_POST, META_HOME_URL),
    "4": ("Facebook - Bot Vendedor/Chat", PROF_FB_CHAT, "https://www.facebook.com"),
    "5": ("WhatsApp Web (Autenticador QR)", PROF_WHATSAPP, "https://web.whatsapp.com"),
    "6": ("Walmart México (Cookies y Código Postal)", PROF_WALMART, "https://www.walmart.com.mx"),
    "7": ("Bodega Aurrera (Cookies y Código Postal)", PROF_AURRERA, "https://www.bodegaaurrera.com.mx"),
}


async def abrir_sesion(opcion: str, nombre: str, ruta_perfil, url: str):
    Path(ruta_perfil).mkdir(parents=True, exist_ok=True)
    print(f"\n🔐 Abriendo navegador visible para: {nombre}")
    print(f"📁 Perfil persistente: {ruta_perfil}")

    # Para Facebook (3 y 4) y WhatsApp (5) forzamos posición visible dentro de la pantalla principal
    if opcion in ("3", "4", "5"):
        args_ventana = [
            "--disable-blink-features=AutomationControlled",
            "--window-position=120,60",
            "--window-size=1180,820"
        ]
        viewport_cfg = {"width": 1160, "height": 760}
    else:
        args_ventana = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
        viewport_cfg = None

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(ruta_perfil),
            headless=False,
            args=args_ventana,
            viewport=viewport_cfg,
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(url)

        if opcion == "5":
            print("👉 Escanea el código QR desde tu teléfono (WhatsApp > Dispositivos vinculados).")
            print("👉 Espera a que carguen tus chats por completo antes de cerrar.")
        else:
            print(f"👉 Inicia sesión manualmente en la ventana para {nombre}.")
            print("👉 Asegúrate de cambiar al perfil de 'Bandido Ofertas' si estás en Facebook.")

        await asyncio.to_thread(input, "👉 Presiona ENTER aquí en la terminal cuando hayas terminado para guardar la sesión y cerrar... ")
        await ctx.close()
        print(f"✅ Sesión y cookies guardadas exitosamente en {ruta_perfil}\n")


async def main():
    while True:
        print("=== GESTOR DE SESIONES Y CREDENCIALES BANDIDO ===")
        for k, (nom, _, _) in PERFILES.items():
            print(f"  [{k}] {nom}")
        print("  [0] Salir")
        op = input("Elige una opción de perfil a configurar: ").strip()
        if op == "0":
            break
        if op in PERFILES:
            nom, ruta, url = PERFILES[op]
            await abrir_sesion(op, nom, ruta, url)


if __name__ == "__main__":
    asyncio.run(main())