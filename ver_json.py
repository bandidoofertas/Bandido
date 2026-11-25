import json
from pathlib import Path
from cfg import get_db

BASE_DIR = Path(__file__).resolve().parent


def revisar_archivos_json():
    print("=" * 60)
    print(f"📂 REVISANDO ARCHIVOS .JSON EN: {BASE_DIR}")
    print("=" * 60)

    archivos = list(BASE_DIR.rglob("*.json"))
    if not archivos:
        print("⚠️ No se encontró ningún archivo .json en esta ruta.")
        return

    for archivo in archivos:
        print(f"\n📄 Archivo: {archivo.resolve()}")
        try:
            contenido = json.loads(archivo.read_text(encoding="utf-8"))
            if isinstance(contenido, list):
                print(f"   📊 Total de elementos: {len(contenido)}")
                for idx, item in enumerate(contenido, 1):
                    print(f"      [{idx}] {item}")
            else:
                print(f"   📋 Claves: {list(contenido.keys()) if isinstance(contenido, dict) else type(contenido)}")
        except Exception as e:
            print(f"   ❌ Error leyendo JSON: {e}")


def revisar_base_datos_chat():
    print("\n" + "=" * 60)
    print("🗄️ REGISTROS EN SQLITE (respuestas_fb y posts_fb)")
    print("=" * 60)

    with get_db() as conn:
        # 1. Posts guardados en SQLite
        try:
            posts = conn.execute("SELECT url_post, fecha FROM posts_fb ORDER BY fecha DESC").fetchall()
            print(f"\n📌 Posts registrados en tabla 'posts_fb' ({len(posts)}):")
            for p in posts:
                print(f"   - [{p['fecha']}] {p['url_post']}")
        except Exception as e:
            print(f"   ⚠️ Tabla posts_fb: {e}")

        # 2. Huellas de comentarios respondidos
        try:
            resps = conn.execute("SELECT cid, url_post FROM respuestas_fb").fetchall()
            print(f"\n🔒 Comentarios bloqueados/respondidos en 'respuestas_fb' ({len(resps)}):")
            for r in resps:
                print(f"   - {r['url_post']} | CID: {r['cid'][:16]}...")
        except Exception as e:
            print(f"   ⚠️ Tabla respuestas_fb: {e}")

        # 3. Historial legible (si ya corriste el chat actualizado)
        try:
            hist = conn.execute(
                "SELECT fecha, autor, comentario, url_post FROM historial_comentarios_fb ORDER BY fecha DESC"
            ).fetchall()
            print(f"\n💬 Historial legible en 'historial_comentarios_fb' ({len(hist)}):")
            for h in hist:
                print(f"   - [{h['fecha']}] {h['autor']}: '{h['comentario']}' ({h['url_post']})")
        except Exception:
            pass


if __name__ == "__main__":
    revisar_archivos_json()
    revisar_base_datos_chat()