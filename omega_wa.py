import asyncio
import sys
import subprocess
from urllib.parse import quote
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent
PROF_WHATSAPP = BASE_DIR / "prof_whatsapp"
ADMIN_WHATSAPP_NUM = "5215615585886"  # Formato internacional México (+52 1 5615585886)

try:
    from browser_queue import adquirir_perfil_navegador
except ImportError:
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def adquirir_perfil_navegador(ruta, origen=""):
        yield


def liberar_perfil_whatsapp():
    try:
        cmd = (
            f"Get-CimInstance Win32_Process -Filter \"name = 'chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{PROF_WHATSAPP.name}*' }} | "
            f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=8)
        for lock in PROF_WHATSAPP.glob("Singleton*"):
            lock.unlink(missing_ok=True)
    except Exception:
        pass


async def enviar_alerta_omega(usuario: str, url_post: str, motivo: str = "reincidencia", mensaje: str = "") -> bool:
    """
    Abre WhatsApp Web usando las cookies de auth.py (prof_whatsapp),
    entra directo al chat de 5615585886 con texto precargado y lo envía.
    """
    if not PROF_WHATSAPP.exists():
        print("⚠️ [OMEGA WA] No existe prof_whatsapp. Ejecuta primero: python auth.py (opción 5).")
        return False

    liberar_perfil_whatsapp()

    texto_alerta = (
        f"🚨 PROTOCOLO OMEGA — USUARIO BLOQUEADO\n"
        f"👤 Usuario: {usuario}\n"
        f"🔗 Link del post: {url_post}\n"
        f"🚫 Motivo: {motivo}"
    )
    if mensaje:
        texto_alerta += f"\n💬 Comentario: {mensaje[:140]}"

    url_directa = f"https://web.whatsapp.com/send?phone={ADMIN_WHATSAPP_NUM}&text={quote(texto_alerta)}"
    print(f"📲 [OMEGA WA] Abriendo chat directo en WhatsApp Web para {ADMIN_WHATSAPP_NUM}...")

    async with adquirir_perfil_navegador(PROF_WHATSAPP, origen="omega_wa"):
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(PROF_WHATSAPP),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--window-position=-32000,-32000"
                ],
                viewport={"width": 1280, "height": 850},
                locale="es-MX",
                timezone_id="America/Mexico_City"
            )
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            try:
                await page.goto(url_directa, timeout=60000, wait_until="domcontentloaded")

                # Esperar hasta 60s a que WhatsApp Web termine de sincronizar o detectar si pide QR
                for _ in range(30):
                    await page.wait_for_timeout(2000)

                    # Verificar si cerró sesión y está pidiendo QR
                    pide_qr = await page.evaluate("""() => {
                        const txt = (document.body.innerText || '').toLowerCase();
                        return txt.includes('iniciar sesión en whatsapp') || txt.includes('escanear el código qr') || Boolean(document.querySelector('canvas[aria-label*="QR"]'));
                    }""")
                    if pide_qr:
                        print("🔐 [OMEGA WA ALERTA] La sesión de WhatsApp Web expiró o no está vinculada. Ejecuta: python auth.py (opción 5).")
                        return False

                    # Buscar la caja de mensaje o el botón de enviar cuando ya cargó el chat
                    enviado = await page.evaluate("""() => {
                        const btnSend = document.querySelector('button[aria-label="Enviar"], span[data-icon="send"]');
                        if (btnSend) {
                            const clickTarget = btnSend.closest('button') || btnSend;
                            clickTarget.click();
                            return 'boton';
                        }
                        const caja = document.querySelector('footer div[contenteditable="true"][role="textbox"], footer div[contenteditable="true"]');
                        if (caja && (caja.innerText || '').trim().length > 5) {
                            caja.focus();
                            return 'caja';
                        }
                        return '';
                    }""")

                    if enviado == "boton":
                        await page.wait_for_timeout(4500)
                        print(f"✅ [OMEGA WA] Alerta enviada mediante botón Enviar al {ADMIN_WHATSAPP_NUM}.")
                        return True
                    elif enviado == "caja":
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(4500)
                        print(f"✅ [OMEGA WA] Alerta enviada mediante Enter al {ADMIN_WHATSAPP_NUM}.")
                        return True

                print("❌ [OMEGA WA TIMEOUT] WhatsApp Web tardó más de 60s en cargar la conversación.")
                return False

            except Exception as e:
                print(f"❌ [OMEGA WA ERROR]: {e}")
                return False
            finally:
                await ctx.close()


if __name__ == "__main__":
    usr = sys.argv[1] if len(sys.argv) > 1 else "Usuario_Prueba_Omega"
    lnk = sys.argv[2] if len(sys.argv) > 2 else "https://www.facebook.com/bandidoofertas/posts/123456789"
    mot = sys.argv[3] if len(sys.argv) > 3 else "prueba_manual_omega"
    asyncio.run(enviar_alerta_omega(usr, lnk, mot))