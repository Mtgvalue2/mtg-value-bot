import os
import json

CACHE_FILE = "cartas_cache.json"

def cargar_datos_cache():
    """Cargar datos previos desde el archivo cache"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_datos_cache(datos):
    """Guardar datos para uso offline"""
    with open(CACHE_FILE, "w") as f:
        json.dump(datos, f, indent=2)

def obtener_carta_offline(nombre):
    """Obtener carta desde cache"""
    datos = cargar_datos_cache()
    return datos.get(nombre.lower())

def guardar_carta_offline(nombre, info):
    """Guardar una carta en cache para uso offline"""
    datos = cargar_datos_cache()
    datos[nombre.lower()] = info
    guardar_datos_cache(datos)
