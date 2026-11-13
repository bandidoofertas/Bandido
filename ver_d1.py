import requests
from credenciales import ACCOUNT_ID, DATABASE_ID, API_TOKEN

def consultar_ofertas_d1():
    """
    Consulta las últimas ofertas almacenadas en la base de datos Cloudflare D1.
    """
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Consulta SQL limpia usando los nombres reales de tus columnas
    sql_query = "SELECT id, titulo, precio_oferta, tienda, nivel, fecha FROM ofertas ORDER BY rowid DESC LIMIT 5;"
    
    payload = {
        "sql": sql_query
    }
    
    print("🔌 Conectando con Cloudflare D1 para inspeccionar la tabla 'ofertas'...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        resultado = response.json()
        
        if resultado.get("success"):
            print("✨ ¡Consulta exitosa!\n")
            # Cloudflare D1 regresa los resultados estructurados en 'result'
            results_data = resultado.get("result", [])
            
            if not results_data or not results_data[0].get("results"):
                print("📭 La tabla 'ofertas' está actualmente vacía. Esperando a que el scraper capture gangas.")
                return

            filas = results_data[0]["results"]
            print(f"📦 Mostrando las últimas {len(filas)} ofertas registradas:\n")
            
            for idx, fila in enumerate(filas, 1):
                print(f"--- Oferta #{idx} ---")
                print(f"• Título: {fila.get('titulo')}")
                print(f"• Precio: {fila.get('precio_oferta')}")
                print(f"• Tienda: {fila.get('tienda')}")
                print(f"• Nivel: {fila.get('nivel')}")
                print(f"• Fecha: {fila.get('fecha')}")
                print("-" * 30)
        else:
            print(f"❌ Error en la respuesta de Cloudflare: {resultado.get('errors')}")
            
    except Exception as e:
        print(f"❌ Error de conexión al consultar D1: {e}")

if __name__ == "__main__":
    consultar_ofertas_d1()