import asyncio
import json
import os
import requests

from scraper_bandido import extraer_ofertas_ml_autonomo
from scraper_amazon import extraer_ofertas_amazon_autonomo
from cerebro_ia import cerebro_autonomo_bandido

REGISTRO_HISTORICO = os.path.join("C:\\Bandido\\Bandido", "ofertas_procesadas.json")
WORKER_URL = "https://bandido.bandidoofertas.workers.dev/api/guardar"
WORKER_TOKEN = "Bearer bandido_secret"
INTERVALO_MINUTOS = 15

def cargar_historico():
    if os.path.exists(REGISTRO_HISTORICO):
        try:
            with open(REGISTRO_HISTORICO, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def guardar_historico(historico):
    try:
        with open(REGISTRO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump(list(historico), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ No se pudo actualizar el histórico: {e}")

def enviar_oferta_a_cloudflare(oferta):
    headers = {
        "Content-Type": "application/json",
        "Authorization": WORKER_TOKEN
    }
    
    payload = {
        "titulo": oferta.get("titulo"),
        "precio_oferta": oferta.get("precio_oferta", "Ver en sitio"),
        "precio_original": oferta.get("precio_original", ""),
        "descuento": oferta.get("descuento", "Oferta"),
        "tienda": oferta.get("tienda"),
        "url_afiliado": oferta.get("url_afiliado"),
        "score": oferta.get("score"),
        "es_hot": oferta.get("es_hot"),
        "categoria_principal": oferta.get("categoria_principal", "General"),
        "subcategoria": oferta.get("subcategoria", "H2"),
        "razonamiento": oferta.get("razonamiento"),
        "mensaje_redes": oferta.get("mensaje_redes", ""),
        "metodos_pago": oferta.get("metodos_pago", ""),
        "fecha_vencimiento": oferta.get("fecha_vencimiento", None),
        "imagen_url": oferta.get("imagen_url", "")
    }

    try:
        response = requests.post(WORKER_URL, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"   ☁️ [NUBE] Sincronizada con éxito en Cloudflare D1.")
        else:
            print(f"   ⚠️ [NUBE] Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"   ⚠️ [NUBE] Excepción con el Worker: {e}")

async def ejecutar_ciclo_maestro():
    print("🦝 [BANDIDO MAESTRO] Iniciando ciclo de rastreo...")
    
    ofertas_ml = await extraer_ofertas_ml_autonomo()
    ofertas_amazon = await extraer_ofertas_amazon_autonomo()
    
    todas_crudas = ofertas_ml + ofertas_amazon
    print(f"\n🎯 Total de ofertas brutas recolectadas: {len(todas_crudas)}")
    
    if not todas_crudas:
        print("❌ No se encontraron ofertas en este ciclo.")
        return

    ids_procesados = cargar_historico()
    
    for oferta in todas_crudas:
        clave_unica = oferta.get("url_normal") or oferta.get("url_afiliado")
        if not clave_unica or clave_unica in ids_procesados:
            continue
            
        analisis = cerebro_autonomo_bandido(oferta)
        if not analisis:
            await asyncio.sleep(0.2)
            continue
            
        score = analisis.get("score", 3)
        descartar = analisis.get("descartar", False)
        subcat = analisis.get("subcategoria", "H2")
        
        if descartar:
            print(f"🗑️ [FILTRO ANTIHUMO] Descartada: {oferta.get('titulo')[:45]}...")
        else:
            es_hot = score <= 2
            cat_letra = subcat[0] if subcat else "H"
            oferta_final = {
                **oferta,
                "score": score,
                "nivel": score,
                "es_hot": es_hot,
                "categoria_principal": cat_letra,
                "subcategoria": subcat,
                "razonamiento": analisis.get("razonamiento_antihumo"),
                "url_afiliado": analisis.get("url_final", oferta.get("url_afiliado")),
                "imagen_local": analisis.get("imagen_local", "")
            }
            
            estado_img = "🖼️ OK" if oferta_final["imagen_local"] else "⚠️ Sin foto"
            print(f"🦝 [Score {score}/5 | Cat: {subcat} | {estado_img}] {oferta.get('titulo')[:45]}...")
            print(f"   💬 {oferta_final['razonamiento']}")
            enviar_oferta_a_cloudflare(oferta_final)
            
        ids_procesados.add(clave_unica)
        await asyncio.sleep(0.1)

    guardar_historico(ids_procesados)
    print("\n🏁 CICLO COMPLETADO. Esperando el próximo turno...")

async def main_loop():
    while True:
        try:
            await ejecutar_ciclo_maestro()
        except Exception as e:
            print(f"⚠️ Error crítico en el ciclo maestro: {e}")
        
        print(f"⏳ Pausa de {INTERVALO_MINUTOS} minutos antes del siguiente rastreo...")
        await asyncio.sleep(INTERVALO_MINUTOS * 60)

if __name__ == "__main__":
    asyncio.run(main_loop())