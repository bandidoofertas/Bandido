import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from cfg import DIR_QR, WORKER_URL, WORKER_TOKEN, get_db, init_db

BASE_DIR = Path(__file__).resolve().parent
POSTS_JSON = BASE_DIR / "posts_activos.json"
INTERVALO_SYNC_SEG = 6 * 3600  # 6 horas


def correr(cmd: list) -> bool:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr.strip():
        print(f"⚠️ {res.stderr.strip()}")
    return res.returncode == 0


def _url_sigue_activa(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
            allow_redirects=True
        )
        if r.status_code in (404, 410):
            return False
        html_low = r.text[:25000].lower()
        frases_muertas = [
            "publicación pausada", "publicación finalizada", "no disponible por el momento",
            "lo sentimos, no pudimos encontrar", "página no encontrada", "producto agotado"
        ]
        if any(f in html_low for f in frases_muertas):
            return False
        return True
    except Exception:
        return True


def auditar_y_purgar_web_d1():
    print("🌐 [SYNC WEB] Auditando ofertas publicadas en Cloudflare D1...")
    try:
        r = requests.get(f"{WORKER_URL}/api/ofertas?incluir_vencidas=1", timeout=15)
        if r.status_code != 200:
            print(f"⚠️ [SYNC WEB] No se pudo leer /api/ofertas ({r.status_code})")
            return
        ofertas_web = r.json()
    except Exception as e:
        print(f"⚠️ [SYNC WEB ERROR]: {e}")
        return

    ahora_utc = datetime.now(timezone.utc)
    borradas_web = 0

    for of in ofertas_web:
        oid = of.get("id")
        url_af = of.get("url_afiliado", "")
        f_venc = of.get("fecha_vencimiento")
        motivo = ""

        if f_venc:
            try:
                dt_exp = datetime.strptime(f_venc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if dt_exp <= ahora_utc:
                    motivo = "plazo de 24h expirado"
            except Exception:
                pass

        if not motivo and url_af:
            if not _url_sigue_activa(url_af):
                motivo = "producto agotado o enlace caído"

        if motivo:
            try:
                requests.post(
                    f"{WORKER_URL}/api/borrar",
                    json={"id": oid, "url_afiliado": url_af},
                    headers={"Content-Type": "application/json", "Authorization": WORKER_TOKEN},
                    timeout=10
                )
                borradas_web += 1
                print(f"   🗑️ [D1 PURGADA] {str(of.get('titulo', ''))[:42]} ({motivo})")
            except Exception:
                pass

    print(f"✨ [SYNC WEB] Revisadas: {len(ofertas_web)} | Eliminadas de la web: {borradas_web}")


def limpiar_caducados_24h():
    init_db()
    with get_db() as conn:
        cols_of = [c[1] for c in conn.execute("PRAGMA table_info(ofertas)").fetchall()]
        if "fecha" not in cols_of:
            conn.execute("ALTER TABLE ofertas ADD COLUMN fecha DATETIME")
            conn.execute("UPDATE ofertas SET fecha = CURRENT_TIMESTAMP WHERE fecha IS NULL")

        cur_of = conn.execute("DELETE FROM ofertas WHERE fecha < datetime('now', '-24 hours')")
        print(f"🧹 [SYNC DB] Ofertas locales caducadas (>24h) eliminadas: {cur_of.rowcount}")

        try:
            cols_hist = [c[1] for c in conn.execute("PRAGMA table_info(historial_precios)").fetchall()]
            if "fecha" in cols_hist:
                cur_hist = conn.execute("DELETE FROM historial_precios WHERE fecha < datetime('now', '-24 hours')")
                print(f"🧹 [SYNC DB] Registros de historial (>24h) eliminados: {cur_hist.rowcount}")
            else:
                cur_hist = conn.execute(
                    "DELETE FROM historial_precios WHERE url_normal NOT IN (SELECT url_normal FROM ofertas)"
                )
                print(f"🧹 [SYNC DB] Historial huérfano eliminado: {cur_hist.rowcount}")
        except Exception as e:
            print(f"⚠️ [SYNC HIST AVISO]: {e}")

        try:
            cols_resp = [c[1] for c in conn.execute("PRAGMA table_info(respuestas_fb)").fetchall()]
            if "fecha" in cols_resp:
                conn.execute("DELETE FROM respuestas_fb WHERE fecha < datetime('now', '-48 hours')")
        except Exception:
            pass

        conn.execute("VACUUM")


limpiar_caducados_12h = limpiar_caducados_24h


def limpiar_multimedia_y_json(horas: int = 24):
    ahora = time.time()
    limite = horas * 3600
    borrados = 0
    if DIR_QR.exists():
        for f in DIR_QR.iterdir():
            if f.is_file() and (ahora - f.stat().st_mtime) > limite:
                try:
                    f.unlink()
                    borrados += 1
                except Exception:
                    pass
    if borrados:
        print(f"🖼️ [SYNC ART] Tarjetas eliminadas: {borrados}")

    if POSTS_JSON.exists():
        try:
            data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
            if isinstance(data, list):
                limpios = [u.strip() for u in data if isinstance(u, str) and u.strip().startswith("http")]
                unicos = list(dict.fromkeys(limpios))[:12]
                POSTS_JSON.write_text(json.dumps(unicos, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"📋 [SYNC JSON] posts_activos.json validado ({len(unicos)} enlaces activos).")
        except Exception as e:
            print(f"⚠️ [SYNC JSON ERROR] Reparando posts_activos.json corrupto: {e}")
            POSTS_JSON.write_text("[]", encoding="utf-8")


def subir_cambios_github(mensaje: str = ""):
    print("📦 [GIT] Preparando subida a GitHub...")
    correr(["git", "add", "."])
    hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = mensaje or f"Actualizacion Bandido Ofertas ({hora})"
    hubo_cambios = correr(["git", "commit", "-m", msg])
    if not hubo_cambios:
        print("ℹ️ [GIT] Sin cambios locales nuevos para commitear.")
    print("🚀 [GIT] Haciendo git push...")
    if correr(["git", "push"]):
        print("✅ [GIT OK] GitHub actualizado (Cloudflare desplegará los cambios automáticamente).")


def reset_total_datos():
    """Borra TODAS las ofertas locales, historial y purga Cloudflare D1 para empezar limpio."""
    print("🦖 [RAWR RESET] Iniciando borrado total de datos locales y en la nube...")
    init_db()
    with get_db() as conn:
        for tabla in ("ofertas", "historial_precios"):
            try:
                cur = conn.execute(f"DELETE FROM {tabla}")
                print(f"   🗑️ Tabla local '{tabla}' vaciada ({cur.rowcount} filas eliminadas).")
            except Exception as e:
                print(f"   ⚠️ No se pudo vaciar '{tabla}': {e}")
        conn.execute("VACUUM")

    try:
        r = requests.post(
            f"{WORKER_URL}/api/purgar",
            headers={"Content-Type": "application/json", "Authorization": WORKER_TOKEN},
            timeout=15
        )
        if r.status_code == 200:
            print("   ☁️ [D1 PURGADA] Todas las ofertas de Cloudflare D1 fueron eliminadas.")
        else:
            print(f"   ⚠️ [D1 AVISO] Código {r.status_code}: {r.text}")
    except Exception as e:
        print(f"   ⚠️ [D1 ERROR] No se pudo purgar D1: {e}")

    limpiar_multimedia_y_json(horas=0)
    subir_cambios_github("Reset total de categorias, Tier 0 y limpieza de base de datos")
    print("🔥 [RAWR LISTO] Todo quedó en cero. Ya puedes arrancar hunt.py.")


def ejecutar_ciclo_sync():
    print("🔄 [SYNC] Iniciando mantenimiento de 24 horas y limpieza de ofertas muertas...")
    limpiar_caducados_24h()
    auditar_y_purgar_web_d1()
    limpiar_multimedia_y_json(horas=24)
    subir_cambios_github()


def main():
    if "--reset-total" in sys.argv:
        reset_total_datos()
    elif "--daemon" in sys.argv:
        print("⏰ [SYNC DAEMON] Modo automático activado: se ejecutará cada 6 horas.")
        while True:
            try:
                ejecutar_ciclo_sync()
            except Exception as e:
                print(f"❌ [SYNC CRASH]: {e}")
            print("⏳ [SYNC DAEMON] Durmiendo 6 horas hasta la siguiente revisión...")
            time.sleep(INTERVALO_SYNC_SEG)
    else:
        ejecutar_ciclo_sync()


if __name__ == "__main__":
    main()