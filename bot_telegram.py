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
import json

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Cargar variables de entorno
load_dotenv()

# Archivos del sistema
HISTORIAL_FILE = "precios_historicos.json"
CACHE_FILE = "data/cache_cards.json"
USUARIOS_FILE = "usuarios_activos.json"

# Importar funciones del backend
from backend.mtg_core import buscar_carta, obtener_todas_ediciones, cargar_historial

# Variables globales
seguimiento_activo = False
cartas_seguimiento = ["Black Knight", "Force of Will", "Ancestral Recall"]
alertas_activas = False
intervalo_dias = 1

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

async def informar_admin(context: ContextTypes.DEFAULT_TYPE, mensaje: str):
    """Enviar mensaje al admin si se define ADMIN_CHAT_ID"""
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if not admin_id:
        return
    try:
        await context.bot.send_message(chat_id=admin_id, text=mensaje)
    except Exception as e:
        print(f"❌ No se pudo enviar mensaje al admin: {str(e)}")

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
    texto += "/buscar <nombre> [edición] – Consultar carta\n"
    texto += "/listar_ediciones <nombre> – Ver todas las ediciones\n"
    texto += "/ver_historial <nombre> – Mostrar precios guardados\n"
    texto += "/seguimiento – Activar actualización automática\n"
    texto += "/detener_seguimiento – Detener búsqueda automática\n"
    texto += "/editar_lista add/remove <nombre> – Editar lista de seguimiento\n"
    texto += "/top_inversiones – Ver las mejores inversiones de la semana\n"
    texto += "/activar_alertas – Recibir notificaciones automáticas\n"
    texto += "/desactivar_alertas – Dejar de recibir notificaciones\n"
    texto += "/estadisticas – Ver uso del bot (solo administrador)"
    await update.message.reply_text(texto)

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    logging.info(f"🧾 Usuario '{nombre_usuario}' ({chat_id}) usó /buscar `{context.args}`")
    await informar_admin(context, f"🧾 {nombre_usuario} ({chat_id}) usó /buscar `{context.args}`")

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

    if "error" in resultado and "nombre" not in resultado:
        todas_ediciones = obtener_todas_ediciones(nombre)
        if not todas_ediciones:
            await update.message.reply_text("🚫 No se encontró la carta ni en línea ni en caché.")
            return
        texto = f"📚 Se encontraron {len(todas_ediciones)} ediciones para `{nombre}`:\n"
        for idx, edic in enumerate(todas_ediciones[:15], 1):
            texto += f"{idx}. {edic['edicion']} | ${float(edic['precio']):.2f}\n"
        texto += "\n👉 Usa `/buscar <nombre> <edición>` para ver detalles."
        await update.message.reply_text(texto, parse_mode="Markdown")
        return

    texto = f"🎴 *{resultado['nombre']}*\n"
    texto += f"📦 Edición: {resultado.get('edicion', 'No disponible')}\n"
    texto += f"💰 Precio Actual: ${round(float(resultado['precio']), 2):.2f}\n"
    if "rsi" in resultado and resultado["rsi"] is not None:
        texto += f"📊 RSI: {resultado['rsi']}\n"
    if "predicciones" in resultado and isinstance(resultado["predicciones"], list) and len(resultado["predicciones"]) >= 6:
        texto += "\n🔮 Predicción de precios futuros (6 meses):\n"
        for i, p in enumerate(resultado["predicciones"][:6], 1):
            fecha_pred = datetime.now() + timedelta(days=i*30)
            texto += f"{fecha_pred.strftime('%Y-%m-%d')}: ${float(p):.2f}\n"
    else:
        texto += "\n📉 Datos insuficientes para predicción."

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
    if "fechas" in resultado and "precios" in resultado and len(resultado["precios"]) >= 2:
        try:
            x = np.array(range(len(resultado["precios"]))).reshape(-1, 1)
            y = np.array([float(p) for p in resultado["precios"]]).reshape(-1, 1)
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(resultado["fechas"], y, label="Precio Real", marker='o', color="#00ffcc", linewidth=2, markersize=6)
            ax.set_title(f"📈 Evolución de Precios - {resultado['nombre']}", fontsize=14, pad=20)
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
        except Exception as e:
            await update.message.reply_text(f"⚠️ No se pudo generar el gráfico histórico: {str(e)}")

    # Gráfico 2: Predicción futura
    if "predicciones" in resultado and isinstance(resultado["predicciones"], list) and len(resultado["predicciones"]) >= 6:
        try:
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
        except Exception as e:
            await update.message.reply_text(f"⚠️ No se pudo generar el gráfico de predicción: {str(e)}")

async def listar_ediciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    logging.info(f"🧾 Usuario '{nombre_usuario}' ({chat_id}) usó /listar_ediciones `{context.args}`")
    await informar_admin(context, f"🧾 {nombre_usuario} ({chat_id}) usó /listar_ediciones `{context.args}`")

    if not context.args:
        await update.message.reply_text("Por favor, escribe el nombre de una carta. Ejemplo: /listar_ediciones Black Knight")
        return

    nombre = " ".join(context.args).strip()
    todas_ediciones = obtener_todas_ediciones(nombre)
    if not todas_ediciones:
        await update.message.reply_text("🚫 No se encontraron ediciones.")
        return

    texto = f"📚 Se encontraron {len(todas_ediciones)} ediciones para `{nombre}`:\n"
    for idx, edic in enumerate(todas_ediciones[:15], 1):
        texto += f"{idx}. {edic['edicion']} | ${float(edic['precio']):.2f}\n"
    texto += "\n👉 Usa `/buscar <nombre> <edición>` para ver detalles."
    await update.message.reply_text(texto, parse_mode="Markdown")

async def ver_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    logging.info(f"🧾 Usuario '{nombre_usuario}' ({chat_id}) usó /ver_historial `{context.args}`")
    await informar_admin(context, f"🧾 {nombre_usuario} ({chat_id}) usó /ver_historial `{context.args}`")

    if not context.args:
        await update.message.reply_text("Por favor, escribe el nombre de una carta. Ejemplo: /ver_historial Black Knight")
        return

    nombre = " ".join(context.args).strip()
    historial = cargar_historial()
    claves = [k for k in historial.keys() if nombre.lower() in k.lower()]
    if not claves:
        await update.message.reply_text("📜 No hay datos guardados para esta carta.")
        return

    for clave in claves:
        registros = historial[clave]
        texto = f"📅 Historial para `{clave}`:\n"
        for reg in registros[-10:]:
            texto += f"{reg['fecha']} | ${float(reg['precio']):.2f}\n"
        await update.message.reply_text(texto, parse_mode="Markdown")

async def seguir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global seguimiento_activo
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    logging.info(f"🧾 Usuario '{nombre_usuario}' ({chat_id}) usó /seguimiento")
    await informar_admin(context, f"🧾 {nombre_usuario} ({chat_id}) activó /seguimiento")

    if seguimiento_activo:
        await update.message.reply_text("👀 Ya está activo el seguimiento.")
        return

    seguimiento_activo = True
    await update.message.reply_text("✅ Iniciando seguimiento automático...")
    job_queue = context.job_queue
    job_queue.run_repeating(monitor_seguimiento, interval=intervalo_dias * 86400, chat_id=update.effective_chat.id)

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
        if "predicciones" in resultado and len(resultado["predicciones"]) >= 6:
            try:
                fechas_pred = [datetime.now() + timedelta(days=i*30) for i in range(1, 7)]
                predicciones = resultado["predicciones"][:6]
                plt.style.use('dark_background')
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.plot(fechas_pred, predicciones, 'r--', label="Predicción", linewidth=2)
                ax.set_title(f"🔮 Predicción de precios futuros - {nombre}", fontsize=14, pad=20)
                ax.set_xlabel("Fecha", fontsize=12)
                ax.set_ylabel("Precio Estimado", fontsize=12)
                ax.grid(True, linestyle='--', alpha=0.5)
                ax.legend(loc='upper left')
                plt.xticks(rotation=45, fontsize=10)
                plt.yticks(fontsize=10)
                plt.tight_layout()
                plt.savefig("grafico_prediccion_auto.png", dpi=150, bbox_inches='tight')
                plt.close()
                await context.bot.send_document(chat_id=chat_id, document=open("grafico_prediccion_auto.png", "rb"))
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ No se pudo generar el gráfico: {str(e)}")

async def detener_seguimiento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global seguimiento_activo
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    logging.info(f"🧾 Usuario '{nombre_usuario}' ({chat_id}) usó /detener_seguimiento")
    await informar_admin(context, f"🧾 {nombre_usuario} ({chat_id}) desactivó el seguimiento")

    if not seguimiento_activo:
        await update.message.reply_text("🛑 No hay seguimiento activo.")
        return

    context.job_queue.stop()
    seguimiento_activo = False
    await update.message.reply_text("🛑 El seguimiento automático ha sido detenido.")

async def editar_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global cartas_seguimiento
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
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
        await update.message.reply_text("Acción no reconocida. Usa `add` o `remove`.")

async def top_inversiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar las 10 cartas con mayor aumento de precio esta semana"""
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    logging.info(f"🧾 Usuario '{nombre_usuario}' ({chat_id}) usó /top_inversiones")
    await informar_admin(context, f"🧾 {nombre_usuario} ({chat_id}) usó /top_inversiones")

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

            if dias_cambio > 7:
                continue

            precio_inicio = float(primer_registro["precio"])
            precio_fin = float(ultimo_registro["precio"])

            if precio_inicio > 0 and precio_fin > 0:
                cambio_porcentaje = ((precio_fin - precio_inicio) / precio_inicio) * 100
                resultados_ascenso.append({
                    "nombre": clave.split(" - ")[0],
                    "inicio": precio_inicio,
                    "fin": precio_fin,
                    "cambio": cambio_porcentaje
                })

    if not resultados_ascenso:
        await update.message.reply_text("🔍 No hay movimientos significativos esta semana.")
        return

    # Ordenar por porcentaje descendente
    resultados_ascenso.sort(key=lambda x: x["cambio"], reverse=True)

    texto = "📈 *Top Inversiones MTG (última semana)*\n\n"
    for idx, item in enumerate(resultados_ascenso[:10], 1):
        texto += f"{idx}. {item['nombre']}\n"
        texto += f"   💸 De ${item['inicio']:.2f} → ${item['fin']:.2f} (+{item['cambio']:.2f}%)\n\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

    # Gráfico opcional
    nombres_graf, inicio_graf, fin_graf, porcentaje_graf = [], [], [], []

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

async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nombre_usuario = update.effective_user.username or f"user_{chat_id}"
    logging.info(f"🧾 Usuario '{nombre_usuario}' ({chat_id}) usó /estadisticas")
    await informar_admin(context, f"🧾 {nombre_usuario} ({chat_id}) consultó /estadisticas")

    admin_id = os.getenv("ADMIN_CHAT_ID")
    if str(chat_id) != admin_id:
        await update.message.reply_text("🚫 Acceso denegado.")
        return

    historial = cargar_historial()
    num_cartas = len(historial)
    usuarios_unicos = len(usuarios_registrados)

    texto = "📊 *Estadísticas del Bot*\n\n"
    texto += f"👥 Usuarios únicos: {usuarios_unicos}\n"
    texto += f"🎴 Cartas registradas: {num_cartas}\n"
    texto += "\n👉 Últimos usuarios:\n"
    for u in list(usuarios_registrados)[-5:]:
        texto += f"- {u}\n"
    
    await update.message.reply_text(texto, parse_mode="Markdown")

def main():
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buscar", buscar))
    application.add_handler(CommandHandler("listar_ediciones", listar_ediciones))
    application.add_handler(CommandHandler("ver_historial", ver_historial))
    application.add_handler(CommandHandler("seguimiento", seguir))
    application.add_handler(CommandHandler("detener_seguimiento", detener_seguimiento))
    application.add_handler(CommandHandler("editar_lista", editar_lista))
    application.add_handler(CommandHandler("top_inversiones", top_inversiones))
    application.add_handler(CommandHandler("estadisticas", estadisticas))

    print(f"✅ Bot iniciado. Usuarios únicos hasta ahora: {len(usuarios_registrados)}")
    application.run_polling()

if __name__ == "__main__":
    main()
