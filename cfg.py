import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.sqlite"
DIR_IMG = BASE_DIR / "img"
DIR_QR = BASE_DIR / "qr"

# Perfiles aislados para evitar bloqueos de Chrome entre bots concurrentes
PROF_ML = BASE_DIR / "prof_ml"
PROF_AMZ = BASE_DIR / "prof_amz"
PROF_FB_POST = BASE_DIR / "prof_fb_post"
PROF_FB_CHAT = BASE_DIR / "prof_fb_chat"

for d in (DIR_IMG, DIR_QR, PROF_ML, PROF_AMZ, PROF_FB_POST, PROF_FB_CHAT):
    d.mkdir(parents=True, exist_ok=True)

# Cloudflare Worker
WORKER_URL = "https://bandidoofertas.com"
WORKER_TOKEN = "Bearer bandido_secret"

# Afiliados oficiales
ML_WORD = "cofa20231216170418"
ML_TOOL = "92220708"
AMZ_TAG = "bandidooferta-20"

# Ollama local (ASUS TUF A15)
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO_AUDITOR = "llama3"
MODELO_VENDEDOR = "llama3"

CODIGOS_CAT = {
    "A", "A1", "A2", "B", "B1", "B2", "B3", "B4",
    "C", "C1", "C2", "C3", "D", "D1", "D2",
    "E", "E1", "E2", "E3", "F", "F1", "F2",
    "G", "G1", "G2", "H", "H1", "H2"
}

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ofertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_normal TEXT UNIQUE,
            url_afiliado TEXT,
            titulo TEXT,
            tienda TEXT,
            precio_oferta REAL,
            precio_original REAL,
            descuento_txt TEXT,
            score INTEGER,
            subcategoria TEXT,
            razonamiento TEXT,
            imagen_url TEXT,
            urgencia TEXT,
            publicado_fb INTEGER DEFAULT 0,
            creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS posts_fb (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_post TEXT UNIQUE,
            ofertas_json TEXT,
            activo INTEGER DEFAULT 1,
            creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS respuestas_fb (
            cid TEXT PRIMARY KEY,
            url_post TEXT,
            respondido_en DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

if __name__ == "__main__":
    init_db()
    print("✅ [CFG] Base de datos SQLite WAL y carpetas inicializadas en:", BASE_DIR)
