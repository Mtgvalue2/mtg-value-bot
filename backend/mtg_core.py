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
    try:
        params_fuzzy = {"fuzzy": nombre}
        response = requests.get("https://api.scryfall.com/cards/named",  params_fuzzy)
        if response.status_code != 200:
            # Usar caché local
            cache = cargar_cache()
            if nombre.lower() in cache:
                return cache[nombre.lower()]
            return []

        datos = response.json()

        # Añadir edición principal
        usd = float(datos["prices"]["usd"]) if datos["prices"].get("usd") else 0.0
        set_name = datos.get("set_name", "Sin Edición")

        todas_ediciones = [{
            "nombre": datos["name"],
            "edicion": set_name,
            "precio": usd,
            "image_url": datos.get("image_uris", {}).get("normal")
        }]

        # Obtener otras ediciones si hay prints_search_uri
        if datos.get("prints_search_uri"):
            while True:
                response_prints = requests.get(datos["prints_search_uri"])
                response_prints.raise_for_status()
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
                    break
                else:
                    break

        # Eliminar duplicados por edición
        ediciones_unicas = {}
        for c in todas_ediciones:
            ediciones_unicas[c["edicion"]] = c

        return list(ediciones_unicas.values())

    except Exception as e:
        print(f"❌ Error al buscar ediciones: {str(e)}")
        # Buscar en caché local
        cache = cargar_cache()
        return cache.get(nombre.lower(), [])

def buscar_carta(nombre, edicion=None):
    """Buscar carta en Scryfall o usar caché local si falla"""
    try:
        params_fuzzy = {"fuzzy": nombre}
        response = requests.get("https://api.scryfall.com/cards/named",  params_fuzzy)
        response.raise_for_status()

        datos = response.json()
        todas_ediciones = []

        # Añadir edición principal
        usd = float(datos["prices"]["usd"]) if datos["prices"].get("usd") else 0.0
        set_name = datos.get("set_name", "Sin Edición")

        todas_ediciones.append({
            "nombre": datos["name"],
            "edicion": set_name,
            "precio": usd,
            "image_url": datos.get("image_uris", {}).get("normal")
        })

        # Obtener otras ediciones si existe prints_search_uri
        if datos.get("prints_search_uri"):
            while True:
                response_prints = requests.get(datos["prints_search_uri"])
                response_prints.raise_for_status()
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
                    break
                else:
                    break

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
            print("📚 Usando caché local...")
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
