import requests
from credenciales import ACCOUNT_ID, DATABASE_ID, API_TOKEN

URL_D1 = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def limpiar_base_datos_d1():
    query = "DELETE FROM ofertas;"
    payload = {"sql": query}
    
    print("🦝 [LIMPIEZA D1] Conectando con Cloudflare para purgar datos antiguos...")
    try:
        response = requests.post(URL_D1, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print("✨ ¡Tabla 'ofertas' purgada con éxito! Todo limpio y a cero.")
        else:
            print(f"❌ Error al limpiar D1: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    limpiar_base_datos_d1()