# difusion_bandido.py

# 1. Consulta SQL: Selecciona ofertas Nivel 1 a 3 no enviadas a Telegram
QUERY_D1 = """
SELECT id, titulo, precio, precio_lista, enlace, categoria, nivel 
FROM ofertas 
WHERE enviado_telegram = 0 AND nivel <= 3 
ORDER BY nivel ASC, fecha_creacion DESC 
LIMIT 5;
"""

# 2. Después de enviar con éxito a Telegram, marca como enviado_telegram = 1
UPDATE_D1 = """
UPDATE ofertas 
SET enviado_telegram = 1 
WHERE id = ?;
"""

def formatear_mensaje_bandido(oferta):
    # Mapeo visual de categorías (para filtrado fácil)
    iconos_categoria = {
        "Tecnología": "📱 #Tecnología",
        "Gaming": "🎮 #Gaming",
        "Hogar": "🏠 #Hogar",
        "Ropa": "👟 #Moda",
        "General": "📦 #Ofertas"
    }
    
    tag_categoria = iconos_categoria.get(oferta['categoria'], "🔥 #Ganga")
    tag_nivel = f"#Nivel{oferta['nivel']}"

    # Plantilla con el tono astuto y coqueto del mapache
    mensaje = (
        f"{tag_categoria} | {tag_nivel}\n\n"
        f"🐾 *{oferta['titulo']}*\n"
        f"💰 **De:** ~${oferta['precio_lista']}~ ➔ **A solo:** **${oferta['precio']}**\n\n"
        f"¿Le vas a decir que no a este antojo? Acércate un poquito y échale el ojo antes de que vuele... 😉✨\n\n"
        f"👉 [Conseguir Ganga Aquí]({oferta['enlace']})"
    )
    return mensaje