import sqlite3

# Conectar a la base de datos (se creará automáticamente)
conn = sqlite3.connect("mtg_cards.db")
cursor = conn.cursor()

# Crear tablas
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

cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    chat_id INTEGER PRIMARY KEY,
    username TEXT,
    fecha_registro TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS portafolio (
    usuario_id INTEGER,
    carta_nombre TEXT,
    cantidad INTEGER,
    precio_compra REAL,
    fecha_compra TEXT
)
''')

conn.commit()
print("✅ Base de datos SQLite creada correctamente")
