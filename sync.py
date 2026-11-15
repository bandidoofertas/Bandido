import subprocess
from datetime import datetime

def correr(cmd: list):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr.strip():
        print(f"⚠️ {res.stderr.strip()}")
    return res.returncode == 0

def main():
    print("🔄 [SYNC] Preparando subida limpia a GitHub...")
    correr(["git", "add", "."])
    hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    hubo_cambios = correr(["git", "commit", "-m", f"Actualizacion Bandido Ofertas ({hora})"])
    if not hubo_cambios:
        print("ℹ️ No había cambios nuevos pendientes por commitear.")
    print("🚀 [SYNC] Enviando a GitHub...")
    if correr(["git", "push"]):
        print("✅ [SYNC OK] GitHub actualizado y Cloudflare sincronizado.")

if __name__ == "__main__":
    main()
