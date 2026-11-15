import asyncio
from playwright.async_api import async_playwright
from cfg import PROF_ML, PROF_AMZ, PROF_FB_POST, PROF_FB_CHAT

PERFILES = {
    "1": ("Mercado Libre (Afiliados)", PROF_ML, "https://www.mercadolibre.com.mx"),
    "2": ("Amazon México", PROF_AMZ, "https://www.amazon.com.mx"),
    "3": ("Facebook - Bot Publicador", PROF_FB_POST, "https://www.facebook.com"),
    "4": ("Facebook - Bot Vendedor/Chat", PROF_FB_CHAT, "https://www.facebook.com"),
}

async def abrir_sesion(nombre: str, ruta_perfil, url: str):
    print(f"\n🔐 Abriendo navegador visible para: {nombre}")
    print(f"📁 Perfil: {ruta_perfil}")
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(ruta_perfil),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            viewport=None,
            locale="es-MX",
            timezone_id="America/Mexico_City"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(url)

        print("👉 Inicia sesión en la ventana del navegador.")
        print("👉 Si es Facebook, cambia al perfil de la página 'Bandido Ofertas'.")
        await asyncio.to_thread(input, "👉 Presiona ENTER aquí cuando ya hayas terminado para guardar y cerrar... ")
        await ctx.close()
        print(f"✅ Sesión guardada en {ruta_perfil}\n")

async def main():
    while True:
        print("=== GESTOR DE SESIONES BANDIDO ===")
        for k, (nom, _, _) in PERFILES.items():
            print(f"  [{k}] {nom}")
        print("  [0] Salir")
        op = input("Elige una opción: ").strip()
        if op == "0":
            break
        if op in PERFILES:
            nom, ruta, url = PERFILES[op]
            await abrir_sesion(nom, ruta, url)

if __name__ == "__main__":
    asyncio.run(main())