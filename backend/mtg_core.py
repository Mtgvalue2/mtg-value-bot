import os
import json
from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression
import requests
from PIL import Image
import matplotlib.pyplot as plt

# Archivos del sistema
HISTORIAL_FILE = "precios_historicos.json"
CACHE_FILE = "data/cache_cards.json"

def cargar_historial():
    """Cargar historial desde archivo JSON"""
    if not os.path.exists(HISTORIAL_FILE):
        return {}
    try:
        with open(HISTORIAL_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error al cargar historial: {str(e)}")
        return {}

def guardar_historial(historial):
    """Guardar datos para uso offline"""
    with open(HISTORIAL_FILE, 'w') as f:
        json.dump(historial, f, indent=2)

def cargar_cache():
    """Cargar caché local de cartas"""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ No se pudo cargar el caché: {str(e)}")
        return {}

def guardar_cache(cache):
    """Guardar caché de cartas"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def calcular_rsi(precios, periodo=14):
    """Calcular RSI técnico"""
    if len(precios) < periodo + 1:
        return None
    deltas = np.diff(precios[-periodo-1:])
    ganancias = np.where(deltas > 0, deltas, 0)
    perdidas = np.where(deltas < 0, -deltas, 0)
    avg_ganancia = np.mean(ganancias)
    avg_perdida = np.mean(perdidas)
    rs = avg_ganancia / avg_perdida if avg_perdida != 0 else float('inf')
    rsi = 100 - (100 / (1 + rs)) if avg_perdida != 0 else 100.0
    return round(rsi, 2)

def predecir_precio_futuro(precios):
    """Predecir los próximos precios usando regresión lineal"""
    if len(precios) < 5:
        return []

    try:
        x = np.array(range(len(precios))).reshape(-1, 1)
        y = np.array([float(p) for p in precios]).reshape(-1, 1)

        modelo = LinearRegression()
        modelo.fit(x, y)

        x_pred = np.array(range(len(precios), len(precios)+6)).reshape(-1, 1)
        predicciones = modelo.predict(x_pred)

        return [round(float(p[0]), 2) for p in predicciones]
    except Exception as e:
        print(f"⚠️ Error al predecir precio: {str(e)}")
        return []

def obtener_todas_ediciones(nombre):
    """Obtener todas las ediciones disponibles de una carta"""
    resultado_scryfall = buscar_en_scryfall(nombre)
    if resultado_scryfall:
        return resultado_scryfall

    resultado_magic_api = buscar_en_magic_api(nombre)
    if resultado_magic_api:
        print("📚 Usando datos de magicthegathering.io...")
        return resultado_magic_api

    # Usar caché local como último recurso
    cache = cargar_cache()
    return cache.get(nombre.lower(), [])

def buscar_en_scryfall(nombre):
    """Buscar en Scryfall (primera opción principal)"""
    try:
        params_fuzzy = {"fuzzy": nombre}
        response = requests.get("https://api.scryfall.com/cards/named",  params_fuzzy)
        if response.status_code != 200:
            return None

        datos = response.json()

        todas_ediciones = [{
            "nombre": datos["name"],
            "edicion": datos.get("set_name", "Sin Edición"),
            "precio": float(datos["prices"]["usd"]) if datos["prices"].get("usd") else 0.0,
            "image_url": datos.get("image_uris", {}).get("normal")
        }]

        if datos.get("prints_search_uri"):
            response_prints = requests.get(datos["prints_search_uri"])
            if response_prints.status_code == 200:
                datos_prints = response_prints.json()
                if datos_prints.get("object") == "list":
                    for item in datos_prints["data"]:
                        if item["prices"].get("usd"):
                            todas_ediciones.append({
                                "nombre": item["name"],
                                "edicion": item.get("set_name", "Sin Edición"),
                                "precio": float(item["prices"]["usd"]),
                                "image_url": item.get("image_uris", {}).get("normal")
                            })

        ediciones_unicas = {}
        for c in todas_ediciones:
            ediciones_unicas[c["edicion"]] = c

        return list(ediciones_unicas.values())

    except Exception as e:
        print(f"🚫 Fallo en Scryfall: {str(e)}")
        return None

def buscar_en_magic_api(nombre):
    """Buscar en Magic The Gathering IO (respaldo)"""
    try:
        params = {"name": nombre}
        response = requests.get("https://api.magicthegathering.io/v1/cards",  params=params)
        if response.status_code != 200:
            return None

        datos = response.json().get("cards", [])
        if not datos:
            return None

        todas_ediciones = []
        for item in datos:
            nombre_card = item.get("name")
            set_name = item.get("set", "Sin Edición")
            texto = item.get("text", "")
            precio_text = ''.join(filter(str.isdigit, texto))
            precio = float(precio_text) / 100 if precio_text else 0.0

            todas_ediciones.append({
                "nombre": nombre_card,
                "edicion": set_name,
                "precio": precio,
                "image_url": item.get("imageUrl")
            })

        ediciones_unicas = {}
        for c in todas_ediciones:
            ediciones_unicas[c["edicion"]] = c

        return list(ediciones_unicas.values())

    except Exception as e:
        print(f"⚠️ Error en magicthegathering.io: {str(e)}")
        return None

def buscar_carta(nombre, edicion=None):
    """Buscar carta en Scryfall o usar caché local"""
    try:
        # Primero intentar con Scryfall
        resultado_scryfall = buscar_en_scryfall(nombre)
        if resultado_scryfall:
            todas_ediciones = resultado_scryfall
        else:
            # Si falla, intentar con magicthegathering.io
            resultado_backup = buscar_en_magic_api(nombre)
            if resultado_backup:
                print("📚 Usando datos de magicthegathering.io...")
                todas_ediciones = resultado_backup
            else:
                # Finalmente, usar caché local
                cache = cargar_cache()
                if nombre.lower() in cache:
                    print("📦 Usando caché local...")
                    todas_ediciones = cache[nombre.lower()]
                else:
                    raise Exception("No se encontraron datos")

        resultado = []
        if edicion:
            resultado = [c for c in todas_ediciones if edicion.lower() in c["edicion"].lower()]
            if not resultado:
                resultado = [todas_ediciones[0]]
        else:
            resultado = sorted([c for c in todas_ediciones if c["precio"] > 0.0], key=lambda x: x["precio"], reverse=True)[:1]

        res = resultado[0] if resultado else todas_ediciones[0]
        clave = f"{res['nombre']} - {res['edicion']}"
        historial = cargar_historial()

        if res["precio"] > 0.0:
            if clave not in historial:
                historial[clave] = []
            historial[clave].append({
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "precio": res["precio"],
                "edicion": res["edicion"]
            })
            guardar_historial(historial)

        registros = historial.get(clave, [])
        fechas_registro = [r["fecha"] for r in registros]
        precios_registro = [float(r["precio"]) for r in registros]

        rsi = calcular_rsi(precios_registro) if len(precios_registro) >= 15 else None
        predicciones = predecir_precio_futuro(precios_registro)

        # Guardar en caché local
        cache = cargar_cache()
        cache[nombre.lower()] = todas_ediciones
        guardar_cache(cache)

        return {
            "nombre": res["nombre"],
            "edicion": res["edicion"],
            "precio": res["precio"],
            "rsi": rsi,
            "predicciones": predicciones,
            "fechas": fechas_registro,
            "precios": precios_registro,
            "image_url": res["image_url"]
        }

    except Exception as e:
        print(f"❌ Error grave al buscar en Scryfall: {str(e)}")
        # Usar caché local como respaldo
        cache = cargar_cache()
        if nombre.lower() in cache:
            print("📦 Usando caché local...")
            todas_ediciones = cache[nombre.lower()]
            res = todas_ediciones[0]
            return {
                "nombre": res["nombre"],
                "edicion": res["edicion"],
                "precio": res["precio"],
                "rsi": None,
                "predicciones": [],
                "fechas": [],
                "precios": [],
                "image_url": res.get("image_url", None)
            }
        return {
            "error": str(e),
            "nombre": nombre,
            "edicion": edicion or "N/A",
            "precio": 0.0,
            "rsi": None,
            "predicciones": [],
            "fechas": [],
            "precios": [],
            "image_url": None
        }
