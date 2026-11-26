import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOCK_DIR = BASE_DIR / "browser_locks"
LOCK_DIR.mkdir(parents=True, exist_ok=True)


def chat_necesita_navegador() -> bool:
    """Permite a hunt.py saber si chat.py está en cola esperando un perfil."""
    return any(LOCK_DIR.glob("priority_*.flag"))


@asynccontextmanager
async def adquirir_perfil_navegador(ruta_perfil: Path, origen: str = "hunt", timeout_seg: int = 180):
    """
    Cola basada en archivos lock para evitar colisiones de Chromium sobre el mismo user_data_dir.
    origen='chat' activa una bandera de prioridad para que hunt.py ceda el paso rápido.
    """
    nombre = Path(ruta_perfil).name
    lock_file = LOCK_DIR / f"{nombre}.lock"
    prio_file = LOCK_DIR / f"priority_{nombre}_{os.getpid()}.flag"

    if origen == "chat":
        prio_file.write_text(str(time.time()), encoding="utf-8")

    inicio = time.time()
    try:
        while True:
            # Limpiar locks huérfanos de más de 5 minutos (por si hubo un cierre abrupto)
            if lock_file.exists():
                try:
                    if time.time() - lock_file.stat().st_mtime > 300:
                        lock_file.unlink(missing_ok=True)
                except Exception:
                    pass

            try:
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{origen}:{os.getpid()}".encode("utf-8"))
                os.close(fd)
                break
            except FileExistsError:
                if time.time() - inicio > timeout_seg:
                    # Forzar liberación si se excedió el tiempo máximo de espera
                    lock_file.unlink(missing_ok=True)
                else:
                    await asyncio.sleep(1.5)

        yield ruta_perfil
    finally:
        try:
            lock_file.unlink(missing_ok=True)
        except Exception:
            pass
        if origen == "chat":
            try:
                prio_file.unlink(missing_ok=True)
            except Exception:
                pass