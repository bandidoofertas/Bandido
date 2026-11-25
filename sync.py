import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from cfg import DIR_QR, get_db, init_db

BASE_DIR = Path(__file__).resolve().parent
POSTS_JSON = BASE_DIR / "posts_activos.json"


def correr(cmd: list) -> bool:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr.strip():
        print(f"⚠️ {res.stderr.strip()}")
    return res.returncode == 0


def limpiar_caducados_12h():
    """Elimina ofertas, historial de precios y registros con más de 12 horas para permitir reanálisis limpio."""
    init_db()
    with get_db() as conn:
        # 1. Asegurar columna fecha en ofertas
        cols_of = [c[1] for c in conn.execute("PRAGMA table_info(ofertas)").fetchall()]
        if "fecha" not in cols_of:
            conn.execute("ALTER TABLE ofertas ADD COLUMN fecha DATETIME")
            conn.execute("UPDATE ofertas SET fecha = CURRENT_TIMESTAMP WHERE fecha IS NULL")

        # 2. Borrar ofertas caducadas (> 12 horas)
        cur_of = conn.execute("DELETE FROM ofertas WHERE fecha < datetime('now', '-12 hours')")
        print(f"🧹 [SYNC DB] Ofertas caducadas (>12h) eliminadas: {cur_of.rowcount}")

        # 3. Borrar historial de precios caducado (> 12 horas) para que el reanálisis no marque falso humo
        try:
            cols_hist = [c[1] for c in conn.execute("PRAGMA table_info(historial_precios)").fetchall()]
            if "fecha" in cols_hist:
                cur_hist = conn.execute("DELETE FROM historial_precios WHERE fecha < datetime('now', '-12 hours')")
                print(f"🧹 [SYNC DB] Registros de historial (>12h) eliminados: {cur_hist.rowcount}")
            else:
                # Si la tabla vieja no tenía columna fecha, limpiar huérfanos que ya no están en ofertas
                cur_hist = conn.execute(
                    "DELETE FROM historial_precios WHERE url_normal NOT IN (SELECT url_normal FROM ofertas)"
                )
                print(f"🧹 [SYNC DB] Historial huérfano eliminado: {cur_hist.rowcount}")
        except Exception as e:
            print(f"⚠️ [SYNC HIST AVISO]: {e}")

        # 4. Limpiar tracking antiguo de comentarios/posts (> 48 horas) para no inflar SQLite
        try:
            cols_resp = [c[1] for c in conn.execute("PRAGMA table_info(respuestas_fb)").fetchall()]
            if "fecha" in cols_resp:
                conn.execute("DELETE FROM respuestas_fb WHERE fecha < datetime('now', '-48 hours')")
        except Exception:
            pass

        # Compactar base de datos
        conn.execute("VACUUM")


def limpiar_multimedia_y_json(horas: int = 12):
    """Limpia tarjetas QR viejas y valida la integridad de posts_activos.json (máximo 10 URLs)."""
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
        print(f"🖼️ [SYNC ART] Tarjetas QR caducadas eliminadas: {borrados}")

    # Validar y recortar posts_activos.json a los 10 más recientes
    if POSTS_JSON.exists():
        try:
            data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
            if isinstance(data, list):
                limpios = [u.strip() for u in data if isinstance(u, str) and u.strip().startswith("http")]
                # Eliminar duplicados preservando orden y limitar a 10
                unicos = list(dict.fromkeys(limpios))[:10]
                POSTS_JSON.write_text(json.dumps(unicos, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"📋 [SYNC JSON] posts_activos.json validado ({len(unicos)} enlaces activos).")
        except Exception as e:
            print(f"⚠️ [SYNC JSON ERROR] Reparando posts_activos.json corrupto: {e}")
            POSTS_JSON.write_text("[]", encoding="utf-8")


def main():
    print("🔄 [SYNC] Iniciando mantenimiento de 12 horas y limpieza de historial...")
    limpiar_caducados_12h()
    limpiar_multimedia_y_json(horas=12)

    print("📦 [SYNC] Preparando subida limpia a GitHub...")
    correr(["git", "add", "."])
    hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    hubo_cambios = correr(["git", "commit", "-m", f"Actualizacion y limpieza 12h Bandido Ofertas ({hora})"])
    if not hubo_cambios:
        print("ℹ️ Sin cambios de código pendientes por commitear.")
    print("🚀 [SYNC] Enviando a GitHub...")
    if correr(["git", "push"]):
        print("✅ [SYNC OK] Base de datos purgada, GitHub actualizado y Cloudflare sincronizado.")


if __name__ == "__main__":
    main()