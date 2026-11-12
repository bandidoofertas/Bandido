import os
import json
from google import genai

# Cargar la API Key desde credenciales o variables de entorno
try:
    from credenciales import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

client = genai.Client()

def cerebro_autonomo_bandido(datos_oferta_bruta):
    """
    Agente de razonamiento autónomo estricto de Bandido.
    Utiliza la nueva escala de 1 a 8 para detectar marketing tramposo,
    precios inflados artificialmente (humo) y gangas históricas.
    """
    system_instruction = (
        "Eres Bandido, un mapache coqueto, astuto, pícaro y experto analista "
        "en comercio electrónico en México. Tu misión es desenterrar gangas reales "
        "y cazar sin piedad el 'humo' corporativo y las falsas rebajas donde las tiendas "
        "inflan el precio base para engañar a los compradores."
    )

    prompt = f"""
    {system_instruction}
    
    Analiza con rigor esta oferta extraída de la web y responde estrictamente en formato JSON válido (sin bloques de código markdown adicionales, solo el JSON puro):
    
    Datos del producto:
    - Título: {datos_oferta_bruta.get('titulo')}
    - Precio Original (anunciado): {datos_oferta_bruta.get('p_orig')}
    - Precio de Oferta: {datos_oferta_bruta.get('p_ofer')}
    - Tienda: {datos_oferta_bruta.get('tienda')}
    - URL: {datos_oferta_bruta.get('url_afiliado')}
    
    Criterios de Evaluación (Escala del 1 al 8):
    - Niveles 1 a 3 (Ofertas TOP / Gangas históricas): Descuentos reales, agresivos y verdaderos chollos imperdibles.
    - Niveles 4 a 5 (Ofertas razonables): Descuentos sólidos pero comunes o de temporada regular.
    - Niveles 6 a 8 (Basura / Falsas rebajas): Patrones de marketing tramposos donde las tiendas inflan el precio base artificialmente.
    
    Instrucciones de decisión:
    1. Asigna un "score" numérico entero del 1 al 8 basándote en la escala anterior.
    2. Determina si debe descartarse (true si el score >= 6, indicando que es humo o precio inflado; false si es menor a 6 para aceptarla).
    3. Redacta el razonamiento antihumo detallado y un mensaje tentador para redes si pasa el filtro.
    
    Estructura JSON requerida:
    {{
      "score": int,
      "descartar": bool,
      "razonamiento_antihumo": "Explicación detallada de por qué es una ganga o por qué se detectó truco/inflado artificial",
      "mensaje_redes": "Texto persuasivo y coqueto con emojis de mapache listo para difundir si se aprueba"
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        
        texto_respuesta = response.text.strip()
        
        # Limpiar bloques de markdown si la IA los incluye
        if texto_respuesta.startswith("```json"):
            texto_respuesta = texto_respuesta[7:]
        if texto_respuesta.endswith("```"):
            texto_respuesta = texto_respuesta[:-3]
            
        resultado_json = json.loads(texto_respuesta.strip())
        return resultado_json
        
    except Exception as e:
        print(f"❌ Error procesando el cerebro autónomo de Gemini: {e}")
        return None

if __name__ == "__main__":
    print("🧠 [CEREBRO BANDIDO] Iniciando pruebas del agente de razonamiento estricto (1-8)...\n")
    
    # Caso 1: Simulando una oferta con precio inflado artificialmente (Humo / Nivel 7)
    oferta_humo = {
        "titulo": "Smart TV LED 50 Pulgadas 4K (Precio inflado temporalmente)",
        "p_orig": "$18,999 MXN",
        "p_ofer": "$9,499 MXN",
        "tienda": "Amazon México",
        "url_afiliado": "https://www.amazon.com.mx/dp/ejemplo1"
    }
    
    print("--- EVALUANDO CASO 1: Posible Falsa Rebaja ---")
    print(f"Producto: {oferta_humo['titulo']} | Antes: {oferta_humo['p_orig']} -> Ahora: {oferta_humo['p_ofer']}")
    analisis_1 = cerebro_autonomo_bandido(oferta_humo)
    print(json.dumps(analisis_1, indent=2, ensure_ascii=False))
    print("\n" + "="*50 + "\n")

    # Caso 2: Simulando una ganga real y agresiva (Nivel 2)
    oferta_ganga = {
        "titulo": "SSD NVMe M.2 2TB de alta velocidad",
        "p_orig": "$3,800 MXN",
        "p_ofer": "$1,450 MXN",
        "tienda": "Mercado Libre",
        "url_afiliado": "https://www.mercadolibre.com.mx/ejemplo2"
    }
    
    print("--- EVALUANDO CASO 2: Posible Ganga Histórica ---")
    print(f"Producto: {oferta_ganga['titulo']} | Antes: {oferta_ganga['p_orig']} -> Ahora: {oferta_ganga['p_ofer']}")
    analisis_2 = cerebro_autonomo_bandido(oferta_ganga)
    print(json.dumps(analisis_2, indent=2, ensure_ascii=False))
