from urllib.parse import urlencode

def formatear_enlace_afiliado_ml(url_producto: str) -> str:
    """
    Toma una URL limpia de un producto o utiliza la base de creador 
    inyectando automáticamente los parámetros de afiliado oficiales de Mercado Libre México.
    """
    # Identificadores fijos de tu cuenta de afiliado descubiertos en tus analíticas
    BASE_SOCIAL = "https://www.mercadolibre.com.mx/social/cofa20231216170418"
    MATT_WORD = "cofa20231216170418"
    MATT_TOOL = "92220708"
    
    # Si recibimos una URL de producto específica, podemos empaquetarla 
    # o apuntar al escaparate general con los parámetros de tu herramienta de creador.
    parametros = {
        "matt_word": MATT_WORD,
        "matt_tool": MATT_TOOL,
        "forceInApp": "true"
    }
    
    if url_producto and url_producto != "#":
        # Adjuntamos la referencia del producto si el scraper la extrajo con éxito
        parametros["ref_producto"] = url_producto
        
    query_string = urlencode(parametros)
    enlace_final = f"{BASE_SOCIAL}?{query_string}"
    
    return enlace_final

if __name__ == "__main__":
    print("--- PRUEBA DE GENERADOR DE AFILIADOS ---")
    url_ejemplo = "https://www.mercadolibre.com.mx/articulo-de-prueba"
    link_generado = formatear_enlace_afiliado_ml(url_ejemplo)
    print("Enlace de afiliado resultante:")
    print(link_generado)