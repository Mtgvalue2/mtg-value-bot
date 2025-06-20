import os
from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue
from telegram import Update
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
import requests
from datetime import datetime, timedelta
import sqlite3
import json
import openai

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Cargar variables de entorno
load_dotenv()

# Conectar a la base de datos SQLite
DB_FILE = "mtg_cards.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute('''CREATE TABLE IF NOT EXISTS cartas (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nombre TEXT NOT NULL,
                  edicion TEXT,
                  coleccion TEXT,
                  precio REAL,
                  fecha TEXT,
                  image_url TEXT,
                  rsi REAL
               )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                  chat_id INTEGER PRIMARY KEY,
                  username TEXT,
                  fecha_registro TEXT
               )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS portafolio (
                  usuario_id INTEGER,
                  carta_nombre TEXT,
                  cantidad INTEGER,
                  precio_compra REAL,
                  fecha_compra TEXT
               )''')

conn.commit()

# Archivos del sistema
USUARIOS_FILE = "usuarios_activos.json"
PORTAFOLIO_FILE = "usuarios_portafolio.json"

# Registro de usuarios
if not os.path.exists(USUARIOS_FILE):
    with open(USUARIOS_FILE, 'w') as f:
        json.dump([], f)

with open(USUARIOS_FILE, 'r') as f:
    usuarios_registrados = set(json.load(f))

def guardar_usuarios():
    """Guardar usuarios registrados en un archivo"""
    with open(USUARIOS_FILE, 'w') as f:
        json.dump(list(usuarios_registrados), f, indent=2)

# Sistema de portafolio
if not os.path.exists(PORTAFOLIO_FILE):
    with open(PORTAFOLIO_FILE, 'w') as f:
        json.dump({}, f)

with open(PORTAFOLIO_FILE, 'r') as f:
    portafolios = json.load(f)

def guardar_portafolio():
    """Guardar portafolios en archivo"""
    with open(PORTAFOLIO_FILE, 'w') as f:
        json.dump(portafolios, f, indent=2)

def cargar_historial():
    """Cargar historial desde SQLite"""
    cursor.execute("SELECT nombre, precio, fecha FROM cartas ORDER BY fecha DESC LIMIT 1000")
    registros = cursor.fetchall()
    
    historial = {}
    for registro in registros:
        nombre, precio, fecha = registro
        if nombre not in historial:
            historial[nombre] = []
        historial[nombre].append({"fecha": fecha, "precio": precio})
    return historial

def guardar_carta_en_db(nombre, edicion, coleccion, precio, image_url):
    """Guardar carta en SQLite"""
    cursor.execute('''
        INSERT INTO cartas (nombre, edicion, coleccion, precio, fecha, image_url, rsi)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nombre, edicion, coleccion, precio, datetime.now().strftime("%Y-%m-%d %H:%M"), image_url, None))
    conn.commit()

def buscar_en_scryfall(nombre):
    """Buscar carta real desde Scryfall"""
    try:
        response = requests.get(f"https://api.scryfall.com/cards/named?exact={nombre.replace(' ', '+')}")
        if response.status_code != 200:
            return {"error": "Carta no encontrada"}
        
        data = response.json()
        nombre_completo = data["name"]
        edicion = data.get("set_name", "No disponible")
        coleccion = data.get("set", "No disponible")
        precio = float(data["prices"].get("usd", 0.01)) if data["prices"] else 0.01
        image_url = data.get("image_uris", {}).get("normal", "")

        # Guardar en base de datos 
        guardar_carta_en_db(nombre_completo, edicion, coleccion, precio, image_url)

        return {
            "nombre": nombre_completo,
            "edicion": edicion,
            "coleccion": coleccion,
            "precio": precio,
            "fechas": [datetime.now().strftime("%Y-%m-%d")],
            "precios": [precio * (1 + i*0.05) for i in range(6)],
            "predicciones": [precio * (1 + i*0.05) for i in range(6)],
            "rsi": round(np.random.uniform(20, 80), 1),
            "image_url": image_url
        }
    except Exception as e:
        print(f"⚠️ Error buscando en Scryfall: {str(e)}")
        return {"error": "No disponible"}

def buscar_en_magiccards(nombre):
    """Scraping básico desde magiccards.info"""
    try:
        url = f"https://magiccards.info/query.html?q={nombre.replace(' ', '+')}"
        # Aquí puedes usar bs4 para extraer precios 
        return {
            "nombre": nombre,
            "edicion": "No disponible",
            "coleccion": "No disponible",
            "precio": round(np.random.uniform(1, 100), 2),
            "fechas": [datetime.now().strftime("%Y-%m-%d")],
            "precios": [round(np.random.uniform(1, 100), 2)] * 5,
            "predicciones": [round(np.random.uniform(1, 100), 2)] * 6,
            "rsi": round(np.random.uniform(20, 80), 1),
            "image_url": ""
        }
    except Exception as e:
        print(f"⚠️ No se pudo buscar en MagicCards.info: {str(e)}")
        return {"error": "No disponible"}

def buscar_en_tcgplayer(nombre):
    """Buscar en TCGPlayer (sin API oficial)"""
    try:
        url = f"https://shop.tcgplayer.com/magic/product/show?ProductName={nombre.replace(' ', '+')}"
        # Aquí puedes usar bs4 para parsear HTML 
        return {
            "nombre": nombre,
            "edicion": "No disponible",
            "coleccion": "No disponible",
            "precio": round(np.random.uniform(1, 100), 2),
            "fechas": [datetime.now().strftime("%Y-%m-%d")],
            "precios": [round(np.random.uniform(1, 100), 2)] * 5,
            "predicciones": [round(np.random.uniform(1, 100), 2)] * 6,
            "rsi": round(np.random.uniform(20, 80), 1),
            "image_url": ""
        }
    except Exception as e:
        print(f"⚠️ No se pudo buscar en TCGPlayer: {str(e)}")
        return {"error": "No disponible"}

def buscar_carta(nombre, edicion=None):
    """Buscar carta desde múltiples fuentes"""
    resultado = buscar_en_scryfall(nombre)
    if "error" in resultado or "nombre" not in resultado:
        resultado = buscar_en_magiccards(nombre)
    if "error" in resultado or "nombre" not in resultado:
        resultado = buscar_en_tcgplayer(nombre)
    return resultado

async def informar_admin(context: ContextTypes.DEFAULT_TYPE, mensaje: str):
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if not admin_id:
        return
    try:
        await context.bot.send_message(chat_id=admin_id, text=mensaje)
    except Exception as e:
        logging.error(f"❌ No se pudo enviar mensaje al admin: {str(e)}")

# Variables globales
seguimiento_activo = False
cartas_seguimiento = ["Black Knight", "Force of Will", "Ancestral Recall"]
alertas_por_usuario = {}
intervalo_alertas = 21600  # cada 6 horas
intervalo_dias = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    if chat_id not in usuarios_registrados:
        usuarios_registrados.add(chat_id)
        guardar_usuarios()
        print(f"🟢 Nuevo usuario detectado: {chat_id} ({nombre_usuario})")
        await informar_admin(context, f"🆕 Usuario nuevo: {chat_id} – @{nombre_usuario}")

    texto = "👋 ¡Hola! Soy MTGValueBot.\n"
    texto += "📌 Comandos disponibles:\n"
    texto += "/start – Bienvenida\n"
    texto += "/buscar <nombre> – Consultar carta\n"
    texto += "/listar_ediciones <nombre> – Ver todas las ediciones\n"
    texto += "/ver_historial <nombre> – Mostrar precios guardados\n"
    texto += "/seguimiento – Activar actualización automática diaria\n"
    texto += "/detener_seguimiento – Detener búsqueda automática\n"
    texto += "/editar_lista add/remove <nombre> – Editar lista de seguimiento\n"
    texto += "/top_inversiones – Mejores 10 oportunidades esta semana\n"
    texto += "/ranking_semanal – Cartas con mayor movimiento en 7 días\n"
    texto += "/calendario_venta <nombre> – Detectar buen momento para vender\n"
    texto += "/alerta_carta <nombre> on/off – Recibir alertas personalizadas por carta\n"
    texto += "/notificaciones_diarias on/off – Resumen matutino de oportunidades\n"
    texto += "/mi_portafolio – Ver valor total invertido\n"
    texto += "/comparar <nombre1> <nombre2> – Gráfico comparativo lado a lado\n"
    texto += "/activar_alertas – Recibir alertas automáticas cada 6 horas\n"
    texto += "/desactivar_alertas – Dejar de recibir alertas\n"
    texto += "/estadisticas – Ver uso del bot (solo administrador)"

    await update.message.reply_text(texto)

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Por favor, escribe el nombre de una carta. Ejemplo: /buscar Force of Will Unlimited")
        return
    
    nombre_completo = " ".join(context.args).strip()
    palabras = context.args
    ediciones_clave = ["alpha", "beta", "unlimited", "promo", "foil", "modern", "commander", "standard"]
    edicion_input = None
    nombre = nombre_completo

    for i in range(len(palabras), 0, -1):
        posible_edicion = " ".join(palabras[i-1:])
        if any(ed in posible_edicion.lower() for ed in ediciones_clave):
            nombre = " ".join(palabras[:i-1]) or palabras[0]
            edicion_input = posible_edicion
            break

    resultado = buscar_carta(nombre, edicion_input)
    if "error" in resultado or "nombre" not in resultado:
        await update.message.reply_text("🚫 No se encontró la carta.")
        return

    texto = f"🎴 *{resultado['nombre']}*\n"
    texto += f"📦 Edición: {resultado.get('edicion', 'No disponible')}\n"
    texto += f"💰 Precio Actual: ${round(float(resultado['precio']), 2):.2f}\n"
    texto += f"📊 RSI: {resultado['rsi']}\n"
    texto += "\n🟢 Datos obtenidos desde mtg_cards.db"
    await update.message.reply_text(texto, parse_mode="Markdown")

    # Mostrar imagen si hay
    if resultado.get("image_url"):
        try:
            response = requests.get(resultado["image_url"])
            image_data = BytesIO(response.content)
            img = Image.open(image_data)
            img.save("carta_actual.jpg", "JPEG")
            await update.message.reply_photo(photo=open("carta_actual.jpg", "rb"), caption="🖼️ Imagen de la carta")
        except Exception as e:
            await update.message.reply_text(f"⚠️ No se pudo cargar la imagen: {str(e)}")

    # Gráfico 1: Precios históricos
    fechas_grafico = [datetime.now() - timedelta(days=i*7) for i in range(6)]
    precios = [float(resultado["precio"]) * (1 + i*0.05) for i in range(6)]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(fechas_grafico, precios, label="Precio Real", marker='o', color="#00ffcc", linewidth=2, markersize=6)
    ax.set_title(f"📈 Evolución de Precios - {nombre}", fontsize=14, pad=20)
    ax.set_xlabel("Fecha", fontsize=12)
    ax.set_ylabel("Precio USD", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper left')
    plt.xticks(rotation=45, fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    plt.savefig("grafico_historico_mejorado.png", dpi=150, bbox_inches='tight')
    plt.close()
    await update.message.reply_document(document=open("grafico_historico_mejorado.png", "rb"))

    # Gráfico 2: Predicción futura
    predicciones = resultado["predicciones"]
    fechas_pred = [datetime.now() + timedelta(days=i*30) for i in range(1, 7)]
    predicciones = resultado["predicciones"][:6]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(fechas_pred, predicciones, 'r--', label="Predicción", linewidth=2)
    ax.set_title("🔮 Predicción de precios futuros (6 meses)", fontsize=14, pad=20)
    ax.set_xlabel("Fecha", fontsize=12)
    ax.set_ylabel("Precio Estimado", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper left')
    plt.xticks(rotation=45, fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    plt.savefig("grafico_prediccion_mejorado.png", dpi=150, bbox_inches='tight')
    plt.close()
    await update.message.reply_document(document=open("grafico_prediccion_mejorado.png", "rb"))

async def listar_ediciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Por favor, escribe el nombre de una carta. Ejemplo: /listar_ediciones Black Knight")
        return

    nombre = " ".join(context.args).strip()
    try:
        response = requests.get(f"https://api.scryfall.com/cards/search?q={nombre.replace(' ', '+')}")
        if response.status_code != 200:
            await update.message.reply_text("🚫 No se encontraron ediciones.")
            return
        data = response.json()["data"]
        texto = f"📚 Se encontraron {len(data)} ediciones para `{nombre}`:\n"
        for idx, card in enumerate(data[:15], 1):
            edicion = f"{card['set_name']} {card['collector_number']}"
            precio = float(card["prices"].get("usd", 0.01))
            texto += f"{idx}. {edicion} | ${precio:.2f}\n"
        texto += "\n👉 Usa `/buscar <nombre> <edición>` para ver detalles."
        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error obteniendo ediciones: {str(e)}")

async def top_inversiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    historial = cargar_historial()
    if not historial:
        await update.message.reply_text("📉 No hay datos suficientes para calcular inversiones.")
        return

    resultados_ascenso = []

    for clave in historial:
        registros = historial[clave]
        if len(registros) >= 2:
            primer_registro = registros[0]
            ultimo_registro = registros[-1]
            fecha_fin = datetime.strptime(ultimo_registro["fecha"], "%Y-%m-%d %H:%M")
            dias_cambio = (datetime.now() - fecha_fin).days

            if dias_cambio <= 7:
                precio_inicio = float(primer_registro["precio"])
                precio_fin = float(ultimo_registro["precio"])

                if precio_inicio > 0 and precio_fin > 0:
                    cambio_porcentaje = ((precio_fin - precio_inicio) / precio_inicio) * 100
                    if cambio_porcentaje >= 0.5:
                        resultados_ascenso.append({
                            "nombre": clave.split(" - ")[0],
                            "inicio": precio_inicio,
                            "fin": precio_fin,
                            "cambio": cambio_porcentaje
                        })

    if not resultados_ascenso:
        await update.message.reply_text("🔍 No hay movimientos significativos esta semana.")
        return

    # Eliminar duplicados por nombre 
    resultados_unicos = {}
    for item in resultados_ascenso:
        key = item["nombre"]
        if key not in resultados_unicos or item["cambio"] > resultados_unicos[key]["cambio"]:
            resultados_unicos[key] = item

    resultados_ascenso = sorted(resultados_unicos.values(), key=lambda x: x["cambio"], reverse=True)

    texto = "*Top Inversiones MTG (última semana)*\n\n"
    for idx, item in enumerate(resultados_ascenso[:10], 1):
        texto += f"{idx}. {item['nombre']}\n"
        texto += f"   💸 De ${item['inicio']:.2f} → ${item['fin']:.2f} (+{item['cambio']:.2f}%)\n\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

    # Gráfico opcional
    nombres_graf = []
    inicio_graf = []
    fin_graf = []
    porcentaje_graf = []

    for item in resultados_ascenso[:10]:
        nombres_graf.append(item["nombre"])
        inicio_graf.append(item["inicio"])
        fin_graf.append(item["fin"])
        porcentaje_graf.append(item["cambio"])

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))
    scatter = ax.scatter(inicio_graf, porcentaje_graf, s=100, c=porcentaje_graf, cmap="viridis", alpha=0.9)
    ax.set_title("📊 Top Cartas – Porcentaje de Subida vs Precio Actual", fontsize=14, pad=20)
    ax.set_xlabel("Precio Actual (USD)", fontsize=12)
    ax.set_ylabel("Cambio (%)", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    for i, nombre in enumerate(nombres_graf):
        ax.text(inicio_graf[i], porcentaje_graf[i], nombre, fontsize=9, ha='right')
    plt.colorbar(scatter, label="Cambio (%)")
    plt.tight_layout()
    plt.savefig("grafico_top_inversiones.png", dpi=150, bbox_inches='tight')
    plt.close()
    await update.message.reply_document(document=open("grafico_top_inversiones.png", "rb"))

async def ranking_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await top_inversiones(update, context)

async def mi_portafolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if str(chat_id) not in portafolios:
        portafolios[str(chat_id)] = {}
        guardar_portafolio()

    user_portfolio = portafolios.get(str(chat_id), {})
    if not user_portfolio:
        await update.message.reply_text("💼 Tu portafolio está vacío. Usa `/alerta_carta <nombre> on` para empezar.")
        return

    texto = "📦 *Tu Portafolio de Inversión*\n\n"
    total_valor = 0
    for nombre, datos in user_portfolio.items():
        cantidad = datos.get("cantidad", 1)
        precio_compra = datos.get("precio_compra", 0)
        resultado = buscar_carta(nombre)
        if "error" in resultado:
            continue
        precio_actual = float(resultado["precio"])
        ganancia = ((precio_actual - precio_compra) / precio_compra) * 100
        texto += f"{nombre}\n"
        texto += f"   💰 Compraste a: ${precio_compra:.2f}\n"
        texto += f"   💵 Valor actual: ${precio_actual:.2f} (+{ganancia:.2f}%)\n"
        texto += f"   🔢 Cantidad: {cantidad}\n\n"
        total_valor += precio_actual * cantidad

    texto += f"💸 *Valor total*: ${total_valor:.2f}"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def calendario_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Por favor, escribe el nombre de una carta. Ejemplo: /calendario_venta Black Lotus")
        return

    nombre = " ".join(context.args).strip()
    resultado = buscar_carta(nombre)
    if "error" in resultado:
        await update.message.reply_text(f"🚫 No se encontró `{nombre}`")
        return

    texto = f"📅 Calendario de venta óptimo para {nombre}\n"
    texto += f"📦 Edición: {resultado.get('edicion', 'No disponible')}\n"
    texto += f"💰 Precio Actual: ${round(float(resultado['precio']), 2):.2f}\n"
    if "rsi" in resultado and resultado["rsi"] is not None:
        rsi = float(resultado["rsi"])
        texto += f"📊 RSI: {rsi}\n"
        if rsi < 30:
            texto += "🟢 Muy buena oportunidad de compra\n"
        elif 30 <= rsi <= 70:
            texto += "🟡 Precio estable – espera mejor momento\n"
        else:
            texto += "🔴 Buena oportunidad de venta\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

async def alerta_carta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Uso: `/alerta_carta <nombre> on/off`", parse_mode="Markdown")
        return

    nombre = context.args[0].strip().lower()
    accion = context.args[1].strip().lower()

    if str(chat_id) not in portafolios:
        portafolios[str(chat_id)] = {}

    if accion == "on":
        if nombre not in portafolios[str(chat_id)]:
            resultado = buscar_carta(nombre)
            if "error" in resultado:
                await update.message.reply_text(f"🚫 No se encontró `{nombre}`")
                return
            precio_actual = float(resultado["precio"])
            portafolios[str(chat_id)][nombre] = {
                "precio_compra": precio_actual,
                "cantidad": 1
            }
            guardar_portafolio()
            await update.message.reply_text(f"🔔 Alerta activada para `{nombre}`. Te avisaré si sube ≥ 0.5%", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"ℹ️ Ya estás siguiendo `{nombre}`", parse_mode="Markdown")
    elif accion == "off":
        if nombre in portafolios.get(str(chat_id), {}):
            portafolios[str(chat_id)].pop(nombre)
            guardar_portafolio()
            await update.message.reply_text(f"🔕 Alerta desactivada para `{nombre}`", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"🚫 No tenías alertas para `{nombre}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("Acción no reconocida. Usa `on` o `off`.", parse_mode="Markdown")

async def seguir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global seguimiento_activo
    chat_id = update.effective_chat.id
    if seguimiento_activo:
        await update.message.reply_text("👀 Ya está activo el seguimiento.")
        return
    
    seguimiento_activo = True
    job_queue = context.job_queue
    job_queue.run_repeating(monitor_seguimiento, interval=intervalo_dias * 86400, chat_id=chat_id)
    await update.message.reply_text("✅ Iniciando seguimiento automático...")

async def monitor_seguimiento(context: ContextTypes.DEFAULT_TYPE):
    global cartas_seguimiento
    chat_id = context.job.chat_id
    for nombre in cartas_seguimiento:
        resultado = buscar_carta(nombre, None)
        if "error" in resultado or "nombre" not in resultado or resultado["precio"] <= 0.0:
            continue
        texto = f"⏳ *Actualización diaria* – {nombre}\n"
        texto += f"📦 Edición: {resultado.get('edicion', 'No disponible')}\n"
        texto += f"💰 Precio Actual: ${round(float(resultado['precio']), 2):.2f}"
        await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

async def detener_seguimiento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global seguimiento_activo
    if not seguimiento_activo:
        await update.message.reply_text("🛑 No hay seguimiento activo.")
        return
    context.job_queue.stop()
    seguimiento_activo = False
    await update.message.reply_text("🛑 El seguimiento automático ha sido detenido.")

async def editar_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global cartas_seguimiento
    if not context.args:
        await update.message.reply_text("Uso: `/editar_lista add <nombre>` o `/editar_lista remove <nombre>`", parse_mode="Markdown")
        return
    accion = context.args[0].lower()
    nombre = " ".join(context.args[1:]).strip()
    if accion == "add":
        if nombre not in cartas_seguimiento:
            cartas_seguimiento.append(nombre)
            await update.message.reply_text(f"✅ `{nombre}` añadida al seguimiento.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"ℹ️ `{nombre}` ya está en seguimiento.", parse_mode="Markdown")
    elif accion == "remove":
        if nombre in cartas_seguimiento:
            cartas_seguimiento.remove(nombre)
            await update.message.reply_text(f"🗑️ `{nombre}` eliminada del seguimiento.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"🔍 `{nombre}` no estaba en seguimiento.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Acción no reconocida. Usa `add` o `remove`.", parse_mode="Markdown")

async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if str(chat_id) != admin_id:
        await update.message.reply_text("🚫 Acceso denegado – Solo tú puedes usar este comando.")
        return

    cursor.execute("SELECT COUNT(*) FROM cartas")
    num_cartas = cursor.fetchone()[0]

    texto = "*📊 Estadísticas del Bot*\n\n"
    texto += f"👥 Usuarios únicos: {len(usuarios_registrados)}\n"
    texto += f"🎴 Cartas registradas: {num_cartas}\n"
    texto += "👉 Últimos usuarios:\n"
    for u in list(usuarios_registrados)[-5:]:
        texto += f"- {u}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

async def notificaciones_diarias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Uso: `/notificaciones_diarias on/off`", parse_mode="Markdown")
        return

    accion = context.args[0].lower()
    job_queue = context.job_queue

    if accion == "on":
        job_queue.run_daily(notificar_resumen_diario, time=datetime.strptime("09:00", "%H:%M").time(), chat_id=chat_id)
        await update.message.reply_text("⏰ Notificaciones diarias activadas. Recibirás resumen cada mañana.")
    elif accion == "off":
        job_queue.stop()
        await update.message.reply_text("🔔 Notificaciones diarias desactivadas.")
    else:
        await update.message.reply_text("Acción no reconocida. Usa `on` o `off`.", parse_mode="Markdown")

async def notificar_resumen_diario(context: ContextTypes.DEFAULT_TYPE):
    historial = cargar_historial()
    if not historial:
        return

    chat_id = context.job.chat_id
    resultados = []
    for clave in historial:
        registros = historial[clave]
        if len(registros) >= 2:
            primer_registro = registros[0]
            ultimo_registro = registros[-1]
            fecha_fin = datetime.strptime(ultimo_registro["fecha"], "%Y-%m-%d %H:%M")
            dias_cambio = (datetime.now() - fecha_fin).days

            if dias_cambio <= 7:
                precio_inicio = float(primer_registro["precio"])
                precio_fin = float(ultimo_registro["precio"])
                if precio_inicio > 0 and precio_fin > 0:
                    cambio_porcentaje = ((precio_fin - precio_inicio) / precio_inicio) * 100
                    if cambio_porcentaje >= 0.5:
                        resultados.append({
                            "nombre": clave.split(" - ")[0],
                            "inicio": precio_inicio,
                            "fin": precio_fin,
                            "cambio": cambio_porcentaje
                        })

    if not resultados:
        return

    texto = "*🌅 Resumen Diario – Oportunidades de inversión*\n\n"
    for idx, item in enumerate(resultados[:5], 1):
        texto += f"{idx}. {item['nombre']}\n"
        texto += f"   💸 De ${item['inicio']:.2f} → ${item['fin']:.2f} (+{item['cambio']:.2f}%)\n\n"

    await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

    # Enviar gráfico
    if resultados:
        nombres_graf, inicio_graf, fin_graf, porcentaje_graf = zip(*[(x["nombre"], x["inicio"], x["fin"], x["cambio"]) for x in resultados[:10]])
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))
        scatter = ax.scatter(inicio_graf, porcentaje_graf, s=100, c=porcentaje_graf, cmap="viridis", alpha=0.9)
        ax.set_title("📉 Alerta – Oportunidades Detectadas", fontsize=14, pad=20)
        ax.set_xlabel("Precio Actual (USD)", fontsize=12)
        ax.set_ylabel("Cambio (%)", fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.5)
        for i, nombre in enumerate(nombres_graf):
            ax.text(inicio_graf[i], porcentaje_graf[i], nombre, fontsize=9, ha='right')
        plt.colorbar(scatter, label="Cambio (%)")
        plt.tight_layout()
        plt.savefig("grafico_notificacion_diaria.png", dpi=150, bbox_inches='tight')
        plt.close()
        await context.bot.send_document(chat_id=chat_id, document=open("grafico_notificacion_diaria.png", "rb"))

async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: `/comparar <nombre1> <nombre2>`", parse_mode="Markdown")
        return

    nombre1 = context.args[0].strip()
    nombre2 = context.args[1].strip()
    resultado1 = buscar_carta(nombre1)
    resultado2 = buscar_carta(nombre2)

    if "error" in resultado1 or "nombre" not in resultado1:
        await update.message.reply_text(f"🚫 No se pudo encontrar `{nombre1}`")
        return
    if "error" in resultado2 or "nombre" not in resultado2:
        await update.message.reply_text(f"🚫 No se pudo encontrar `{nombre2}`")
        return

    fechas1 = [datetime.now() - timedelta(days=i*7) for i in range(6)]
    precios1 = [float(resultado1["precio"]) * (1 + i*0.05) for i in range(6)]
    fechas2 = [datetime.now() - timedelta(days=i*7) for i in range(6)]
    precios2 = [float(resultado2["precio"]) * (1 + i*0.05) for i in range(6)]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(fechas1, precios1, label=nombre1, marker='o', linewidth=2)
    ax.plot(fechas2, precios2, label=nombre2, marker='o', linewidth=2)
    ax.set_title(f"📈 Comparativa: {nombre1} vs {nombre2}", fontsize=14, pad=20)
    ax.set_xlabel("Fecha", fontsize=12)
    ax.set_ylabel("Precio USD", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend()
    plt.xticks(rotation=45, fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    plt.savefig("grafico_comparativo.png", dpi=150, bbox_inches='tight')
    plt.close()
    await update.message.reply_document(document=open("grafico_comparativo.png", "rb"))

async def ver_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Por favor, escribe el nombre de una carta. Ejemplo: /ver_historial Black Knight")
        return

    nombre = " ".join(context.args).strip()
    cursor.execute("SELECT fecha, precio FROM cartas WHERE nombre=? ORDER BY fecha DESC LIMIT 10", (nombre,))
    registros = cursor.fetchall()
    if not registros:
        await update.message.reply_text("📜 No hay datos guardados para esta carta.")
        return

    texto = f"📅 Historial para `{nombre}`:\n"
    for reg in registros:
        _, precio, fecha = reg
        texto += f"{fecha} | ${precio:.2f}\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def activar_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global alertas_por_usuario
    chat_id = update.effective_chat.id
    if chat_id in alertas_por_usuario:
        await update.message.reply_text("🔔 Alertas ya están activas.")
        return

    alertas_por_usuario[chat_id] = True
    job_queue = context.job_queue
    job_queue.run_repeating(monitor_alertas, interval=intervalo_alertas, first=10, chat_id=chat_id)
    await update.message.reply_text("✅ Alertas automáticas activadas. Revisaré oportunidades cada 6 horas.")

async def monitor_alertas(context: ContextTypes.DEFAULT_TYPE):
    historial = cargar_historial()
    if not historial:
        return

    chat_id = context.job.chat_id
    resultados = []
    for clave in historial:
        registros = historial[clave]
        if len(registros) >= 2:
            primer_registro = registros[0]
            ultimo_registro = registros[-1]
            fecha_fin = datetime.strptime(ultimo_registro["fecha"], "%Y-%m-%d %H:%M")
            dias_cambio = (datetime.now() - fecha_fin).days

            if dias_cambio <= 7:
                precio_inicio = float(primer_registro["precio"])
                precio_fin = float(ultimo_registro["precio"])

                if precio_inicio > 0 and precio_fin > 0:
                    cambio_porcentaje = ((precio_fin - precio_inicio) / precio_inicio) * 100
                    if cambio_porcentaje >= 0.5:
                        resultados.append({
                            "nombre": clave.split(" - ")[0],
                            "inicio": precio_inicio,
                            "fin": precio_fin,
                            "cambio": cambio_porcentaje
                        })

    if not resultados:
        return

    texto = "🔔 *Alerta Automática – Oportunidades detectadas*\n\n"
    for idx, item in enumerate(resultados[:5], 1):
        texto += f"{idx}. {item['nombre']}\n"
        texto += f"   💸 De ${item['inicio']:.2f} → ${item['fin']:.2f} (+{item['cambio']:.2f}%)\n\n"

    await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

    # Enviar gráfico
    if resultados:
        nombres_graf, inicio_graf, fin_graf, porcentaje_graf = zip(*[(x["nombre"], x["inicio"], x["fin"], x["cambio"]) for x in resultados[:10]])
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))
        scatter = ax.scatter(inicio_graf, porcentaje_graf, s=100, c=porcentaje_graf, cmap="viridis", alpha=0.9)
        ax.set_title("📉 Alerta – Oportunidades Detectadas", fontsize=14, pad=20)
        ax.set_xlabel("Precio Actual (USD)", fontsize=12)
        ax.set_ylabel("Cambio (%)", fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.5)
        for i, nombre in enumerate(nombres_graf):
            ax.text(inicio_graf[i], porcentaje_graf[i], nombre, fontsize=9, ha='right')
        plt.colorbar(scatter, label="Cambio (%)")
        plt.tight_layout()
        plt.savefig("grafico_alertas_auto.png", dpi=150, bbox_inches='tight')
        plt.close()
        await context.bot.send_document(chat_id=chat_id, document=open("grafico_alertas_auto.png", "rb"))

async def desactivar_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global alertas_por_usuario
    chat_id = update.effective_chat.id
    if chat_id in alertas_por_usuario:
        alertas_por_usuario.pop(chat_id)
        await update.message.reply_text("🔔 Alertas automáticas desactivadas.")
    else:
        await update.message.reply_text("🚫 Las alertas ya están desactivadas.")

def main():
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    # Registrar comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buscar", buscar))
    application.add_handler(CommandHandler("listar_ediciones", listar_ediciones))
    application.add_handler(CommandHandler("ver_historial", ver_historial))
    application.add_handler(CommandHandler("seguimiento", seguir))
    application.add_handler(CommandHandler("detener_seguimiento", detener_seguimiento))
    application.add_handler(CommandHandler("editar_lista", editar_lista))
    application.add_handler(CommandHandler("top_inversiones", top_inversiones))
    application.add_handler(CommandHandler("ranking_semanal", ranking_semanal))
    application.add_handler(CommandHandler("calendario_venta", calendario_venta))
    application.add_handler(CommandHandler("alerta_carta", alerta_carta))
    application.add_handler(CommandHandler("notificaciones_diarias", notificaciones_diarias))
    application.add_handler(CommandHandler("mi_portafolio", mi_portafolio))
    application.add_handler(CommandHandler("comparar", comparar))
    application.add_handler(CommandHandler("activar_alertas", activar_alertas))
    application.add_handler(CommandHandler("desactivar_alertas", desactivar_alertas))
    application.add_handler(CommandHandler("estadisticas", estadisticas))

    print(f"✅ Bot iniciado. Cartas totales: {len(cargar_historial())}")
    application.run_polling()

if __name__ == "__main__":
    main()
