import requests

enlaces_cortos = [
    "https://meli.la/2PNBcjs",
    "https://meli.la/2ZLLxmU",
    "https://meli.la/2J2eGi7"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

print("ANALIZADOR CON NAVEGADOR: Rastreando redirecciones de afiliado...")

for enlace in enlaces_cortos:
    try:
        respuesta = requests.get(enlace, headers=headers, allow_redirects=True, timeout=10)
        print("\nCorto:", enlace)
        print("  Status Code:", respuesta.status_code)
        print("  URL Final Destino:", respuesta.url)
    except Exception as e:
        print("Error al resolver", enlace, ":", e)

