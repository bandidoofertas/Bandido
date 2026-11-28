import json
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from cfg import DIR_QR, WORKER_URL, WORKER_TOKEN, get_db, init_db

BASE_DIR = Path(__file__).resolve().parent
POSTS_JSON = BASE_DIR / "posts_activos.json"
INTERVALO_SYNC_SEG = 1800  # 30 min si se corre independiente con --daemon


def correr(cmd: list) -> bool:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr.strip():
        print(f"⚠️ {res.stderr.strip()}")
    return res.returncode == 0


def asegurar_columnas_ofertas():
    """Garantiza que SQLite local tenga fecha_vencimiento sin romper tablas previas."""
    init_db()
    with get_db() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(ofertas)").fetchall()]
        if "fecha_vencimiento" not in cols:
            conn.execute("ALTER TABLE ofertas ADD COLUMN fecha_vencimiento DATETIME")
            conn.execute(
                "UPDATE ofertas SET fecha_vencimiento = datetime(COALESCE(creado_en, CURRENT_TIMESTAMP), '+24 hours') "
                "WHERE fecha_vencimiento IS NULL"
            )


def _limpiar_numero(txt: str) -> float:
    if not txt:
        return 0.0
    limpio = re.sub(r"[^0-9.]", "", str(txt).replace(",", ""))
    try:
        return float(limpio)
    except Exception:
        return 0.0


def es_imagen_valida(url: str) -> bool:
    """Verifica que la URL de imagen no esté vacía ni sea un placeholder/ícono roto."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    if not u.startswith("http"):
        return False
    low = u.lower()
    if any(bad in low for bad in ("frontend-assets", "sprite", "logo", "icon", "placeholder", "data:image", "1x1", "pixel", "undefined", "null", "verification", "captcha")):
        return False
    if low.split("?")[0].endswith(".svg"):
        return False
    return True


def _purgar_registro_local(conn, url_normal: str = "", url_afiliado: str = ""):
    """Elimina la oferta y su rastro en historial_precios para que hunt.py pueda volver a cazarla."""
    urls_normales = set()
    if url_normal:
        urls_normales.add(url_normal)
        rows = conn.execute("SELECT url_normal FROM ofertas WHERE url_normal = ?", (url_normal,)).fetchall()
        for r in rows:
            urls_normales.add(r["url_normal"])
        conn.execute("DELETE FROM ofertas WHERE url_normal = ?", (url_normal,))

    if url_afiliado:
        rows = conn.execute("SELECT url_normal FROM ofertas WHERE url_afiliado = ?", (url_afiliado,)).fetchall()
        for r in rows:
            if r["url_normal"]:
                urls_normales.add(r["url_normal"])
        conn.execute("DELETE FROM ofertas WHERE url_afiliado = ?", (url_afiliado,))

    for u_norm in urls_normales:
        try:
            conn.execute("DELETE FROM historial_precios WHERE url_normal = ?", (u_norm,))
        except Exception:
            pass


def _limpiar_url_de_posts_json(url_af: str, url_norm: str = ""):
    """Quita el enlace de posts_activos.json si estaba en la lista de publicados."""
    if not POSTS_JSON.exists():
        return
    try:
        data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return
        objetivos = {u.strip() for u in (url_af, url_norm) if u and u.strip()}
        if not objetivos:
            return
        filtrados = [u for u in data if isinstance(u, str) and u.strip() not in objetivos]
        if len(filtrados) != len(data):
            POSTS_JSON.write_text(json.dumps(filtrados, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def verificar_oferta_viva(url_objetivo: str, precio_guardado: float = 0.0) -> tuple[bool, str]:
    """
    Revisa la URL real (o de afiliado si no hay normal) para detectar:
    1) Página caída / publicación pausada / finalizada
    2) Producto sin stock ('Actualmente no disponible', 'Agotado', sin botón de compra)
    3) Oferta relámpago terminada (si el precio subió >18% respecto al precio de oferta guardado)
    """
    if not url_objetivo or not url_objetivo.startswith("http"):
        return False, "URL inválida"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "es-MX,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        r = requests.get(url_objetivo, headers=headers, timeout=12, allow_redirects=True)
        if r.status_code in (404, 410):
            return False, f"HTTP {r.status_code}"

        html = r.text
        html_low = html[:45000].lower()

        if "validatecaptcha" in html_low or "robot check" in html_low:
            return True, ""

        frases_muertas = [
            "publicación pausada",
            "publicación finalizada",
            "esta publicación finalizó",
            "no disponible por el momento",
            "actualmente no disponible",
            "lo sentimos, no pudimos encontrar",
            "página no encontrada",
            "producto agotado",
            "sin stock disponible"
        ]
        for frase in frases_muertas:
            if frase in html_low:
                return False, f"sin stock ({frase})"

        if precio_guardado > 0:
            precio_actual = 0.0
            if "amazon.com.mx" in r.url:
                m_amz = re.search(r'<span class="a-offscreen">\s*\$([0-9,]+(?:\.[0-9]{2})?)\s*</span>', html)
                if m_amz:
                    precio_actual = _limpiar_numero(m_amz.group(1))
            elif "mercadolibre.com.mx" in r.url:
                m_ml = re.search(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)', html)
                if m_ml:
                    precio_actual = _limpiar_numero(m_ml.group(1))

            if precio_actual > (precio_guardado * 1.18):
                return False, f"subió de precio (${precio_guardado:,.0f} -> ${precio_actual:,.0f})"

        return True, ""
    except Exception:
        return True, ""


def auditar_y_purgar_todo(max_chequeos_http: int = 12):
    """
    Audita en cada ronda de hunt:
    1) Ofertas locales sin foto o vencidas (borrándolas de ofertas + historial_precios para recazarlas)
    2) Ofertas web en Cloudflare D1 sin foto o vencidas por reloj
    3) Muestra rotativa ordenada por vencimiento más próximo (id ASC / fecha_vencimiento ASC)
    """
    asegurar_columnas_ofertas()
    ahora_utc = datetime.now(timezone.utc)
    ahora_str = ahora_utc.strftime("%Y-%m-%d %H:%M:%S")

    mapa_local_por_af = {}
    sin_foto_local = 0
    vencidas_local = 0

    with get_db() as conn:
        filas = conn.execute(
            "SELECT url_normal, url_afiliado, titulo, precio_oferta, imagen_url, fecha_vencimiento FROM ofertas"
        ).fetchall()

        for f in filas:
            item = dict(f)
            u_norm = item["url_normal"]
            u_af = item["url_afiliado"]
            fv = item["fecha_vencimiento"]

            if not es_imagen_valida(item.get("imagen_url", "")):
                _purgar_registro_local(conn, url_normal=u_norm, url_afiliado=u_af)
                _limpiar_url_de_posts_json(u_af, u_norm)
                sin_foto_local += 1
                continue

            if fv and fv <= ahora_str:
                _purgar_registro_local(conn, url_normal=u_norm, url_afiliado=u_af)
                _limpiar_url_de_posts_json(u_af, u_norm)
                vencidas_local += 1
                continue

            mapa_local_por_af[u_af] = item

        if sin_foto_local:
            print(f"🖼️ [SYNC DB] Ofertas locales sin foto eliminadas para recazar: {sin_foto_local}")
        if vencidas_local:
            print(f"🧹 [SYNC DB] Ofertas locales vencidas eliminadas: {vencidas_local}")

        try:
            cols_hist = [c[1] for c in conn.execute("PRAGMA table_info(historial_precios)").fetchall()]
            if "fecha" in cols_hist:
                conn.execute("DELETE FROM historial_precios WHERE fecha < datetime('now', '-36 hours')")
            else:
                conn.execute("DELETE FROM historial_precios WHERE url_normal NOT IN (SELECT url_normal FROM ofertas)")
        except Exception:
            pass

    try:
        r = requests.get(f"{WORKER_URL.rstrip('/')}/api/ofertas?incluir_vencidas=1", timeout=15)
        if r.status_code != 200:
            print(f"⚠️ [SYNC WEB] No se pudo leer /api/ofertas ({r.status_code})")
            return
        ofertas_web = r.json()
    except Exception as e:
        print(f"⚠️ [SYNC WEB ERROR]: {e}")
        return

    # Priorizar las más antiguas primero (id ASC) para que el chequeo HTTP rote por toda la base
    ofertas_ordenadas = sorted(ofertas_web, key=lambda x: int(x.get("id") or 0))

    borradas_web = 0
    chequeos_realizados = 0

    for of in ofertas_ordenadas:
        oid = of.get("id")
        url_af = of.get("url_afiliado", "")
        img_web = of.get("imagen_url", "")
        f_venc = of.get("fecha_vencimiento")
        motivo = ""

        if not es_imagen_valida(img_web):
            motivo = "sin imagen válida (se recazará)"

        if not motivo and f_venc:
            try:
                dt_exp = datetime.strptime(f_venc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if dt_exp <= ahora_utc:
                    motivo = "vigencia expirada"
            except Exception:
                pass

        info_local = mapa_local_por_af.get(url_af, {})
        url_chequeo = info_local.get("url_normal") or url_af
        precio_ref = float(info_local.get("precio_oferta") or _limpiar_numero(of.get("precio_oferta", "0")))

        if not motivo and url_chequeo and chequeos_realizados < max_chequeos_http:
            chequeos_realizados += 1
            viva, razon_baja = verificar_oferta_viva(url_chequeo, precio_ref)
            if not viva:
                motivo = razon_baja

        if motivo:
            borrado_ok = False
            try:
                r_del = requests.post(
                    f"{WORKER_URL.rstrip('/')}/api/borrar",
                    json={"id": oid, "url_afiliado": url_af},
                    headers={"Content-Type": "application/json", "Authorization": WORKER_TOKEN},
                    timeout=10
                )
                if r_del.status_code == 200:
                    borrado_ok = True
                else:
                    print(f"   ⚠️ [WORKER RECHAZÓ BORRADO] HTTP {r_del.status_code}: {r_del.text[:150]}")
            except Exception as e:
                print(f"   ⚠️ [ERROR RED BORRADO]: {e}")

            if borrado_ok:
                borradas_web += 1
                print(f"   🗑️ [PURGADA] {str(of.get('titulo', ''))[:42]} -> {motivo}")

            with get_db() as conn:
                _purgar_registro_local(
                    conn,
                    url_normal=info_local.get("url_normal", ""),
                    url_afiliado=url_af
                )
            _limpiar_url_de_posts_json(url_af, info_local.get("url_normal", ""))

    if borradas_web or chequeos_realizados:
        print(f"✨ [SYNC] Web activas: {len(ofertas_web)} | Chequeadas HTTP: {chequeos_realizados} | Eliminadas: {borradas_web}")


def limpiar_caducados_24h():
    """Alias compatible con llamadas previas desde hunt.py."""
    auditar_y_purgar_todo(max_chequeos_http=12)


limpiar_caducados_12h = limpiar_caducados_24h


def ejecutar_vacuum_seguro():
    """Ejecuta VACUUM fuera de bloques 'with conn:' para evitar error de transacción."""
    try:
        conn = get_db()
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.close()
    except Exception:
        pass


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
        except Exception:
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
        print("✅ [GIT OK] GitHub actualizado.")


def reset_total_datos():
    print("🦖 [RAWR RESET] Iniciando borrado total de datos locales y en la nube...")
    asegurar_columnas_ofertas()
    with get_db() as conn:
        for tabla in ("ofertas", "historial_precios", "posts_fb"):
            try:
                cur = conn.execute(f"DELETE FROM {tabla}")
                print(f"   🗑️ Tabla local '{tabla}' vaciada ({cur.rowcount} filas).")
            except Exception:
                pass
    ejecutar_vacuum_seguro()

    try:
        r = requests.post(
            f"{WORKER_URL.rstrip('/')}/api/purgar",
            headers={"Content-Type": "application/json", "Authorization": WORKER_TOKEN},
            timeout=15
        )
        print(f"   ☁️ [D1 PURGADA] Status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"   ⚠️ [D1 ERROR]: {e}")

    limpiar_multimedia_y_json(horas=0)
    print("🔥 [RAWR LISTO] Todo quedó en cero.")


def ejecutar_ciclo_sync():
    print("🔄 [SYNC] Auditando caducidades, imágenes, stock y precios vigentes...")
    auditar_y_purgar_todo(max_chequeos_http=25)
    limpiar_multimedia_y_json(horas=24)
    ejecutar_vacuum_seguro()


def main():
    if "--reset-total" in sys.argv:
        reset_total_datos()
    elif "--daemon" in sys.argv:
        print("⏰ [SYNC DAEMON] Modo automático activado (cada 30 min).")
        while True:
            try:
                ejecutar_ciclo_sync()
            except Exception as e:
                print(f"❌ [SYNC CRASH]: {e}")
            time.sleep(INTERVALO_SYNC_SEG)
    else:
        ejecutar_ciclo_sync()


if __name__ == "__main__":
    main()