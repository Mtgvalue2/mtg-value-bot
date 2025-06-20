import requests
import sqlite3
from datetime import datetime
import time

# Conectar a la base de datos SQLite
conn = sqlite3.connect("mtg_cards.db")
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cartas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        edicion TEXT,
        coleccion TEXT,
        precio REAL,
        fecha TEXT,
        image_url TEXT,
        rsi REAL
    )
''')

conn.commit()

def guardar_carta_en_db(nombre, edicion, coleccion, precio, image_url):
    cursor.execute('''
        INSERT INTO cartas (nombre, edicion, coleccion, precio, fecha, image_url, rsi)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nombre, edicion, coleccion, precio, datetime.now().strftime("%Y-%m-%d %H:%M"), image_url, None))
    conn.commit()
    print(f"💾 {nombre} – Guardada en base de datos")

def obtener_todas_las_cartas():
    url = "https://api.scryfall.com/cards/search?q=is%3Abooster+t%3Acard"
    
    while url:
        response = requests.get(url)
        if response.status_code != 200:
            print("❌ Error al conectarse a Scryfall")
            break

        data = response.json()
        for card in data["data"]:
            nombre = card["name"]
            edicion = card.get("set_name", "No disponible")
            coleccion = card.get("set", "No disponible")
            precios = card.get("prices", {})
            precio = float(precios.get("usd", 0.01)) if precios else 0.01
            image_url = card.get("image_uris", {}).get("normal", "")

            # Guardar en la base de datos 
            guardar_carta_en_db(nombre, edicion, coleccion, precio, image_url)

        print(f"📥 Cargadas {len(data['data'])} cartas...")
        url = data["next_page"] if data["has_more"] else None
        time.sleep(0.1)

    print("🎉 ¡Base de datos completada!")

obtener_todas_las_cartas()
