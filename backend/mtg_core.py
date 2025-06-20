import os
import json
from datetime import datetime
import requests

def buscar_carta(nombre, edicion=None):
    """Buscar carta real desde Scryfall"""
    try:
        response = requests.get(f"https://api.scryfall.com/cards/named?exact={nombre.replace(' ', '+')}")
        if response.status_code != 200:
            return {"error": "Carta no encontrada"}
        
        data = response.json()
        nombre_completo = data["name"]
        edicion = data["set_name"] if "set_name" in data else "No disponible"
        precio = float(data["prices"].get("usd", 0.01))
        image_url = data.get("image_uris", {}).get("normal", "")

        return {
            "nombre": nombre_completo,
            "edicion": edicion,
            "precio": precio,
            "fechas": [datetime.now().strftime("%Y-%m-%d %H:%M")],
            "precios": [precio] * 5,
            "predicciones": [precio * (1 + i*0.05) for i in range(6)],
            "rsi": round((precio - 0.01) / (100 - 0.01) * 100, 1),
            "image_url": image_url
        }
    except Exception as e:
        print(f"❌ Error buscando carta: {e}")
        return {"error": "No disponible"}

def obtener_todas_ediciones(nombre):
    """Obtener todas las ediciones desde Scryfall"""
    try:
        response = requests.get(f"https://api.scryfall.com/cards/search?q={nombre.replace(' ', '+')}")
        if response.status_code != 200:
            return []
        
        registros = []
        for card in response.json()["data"]:
            registros.append({
                "edicion": f"{card['set_name']} {card['collector_number']}",
                "precio": float(card["prices"].get("usd", 0.01))
        })
        return registros
    except Exception as e:
        print(f"⚠️ No se pudieron cargar ediciones: {e}")
        return []

def cargar_historial():
    """Cargar historial de precios desde archivo"""
    if not os.path.exists("precios_historicos.json"):
        return {}
    try:
        with open("precios_historicos.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error cargando historial: {str(e)}")
        return {}
