import os
from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
import requests
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Cargar variables de entorno
load_dotenv()

# Importar funciones del backend
from backend.mtg_core import buscar_carta, obtener_todas_ediciones, cargar_historial

# Variables globales para seguimiento
seguimiento_activo = False
cartas_seguimiento = ["Black Knight", "Force of Will", "Ancestral Recall"]
intervalo_dias = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "👋 ¡Hola! Soy MTGValueBot.\n\n"
    texto += "📌 Comandos disponibles:\n"
    texto += "/buscar <nombre> [edición] – Consultar carta\n"
    texto += "/listar_ediciones <nombre> – Ver todas las ediciones\n"
    texto += "/ver_historial <nombre> – Mostrar precios guardados\n"
    texto += "/seguimiento – Activar actualización automática\n"
    texto += "/detener_seguimiento – Detener búsqueda automática\n"
    texto += "/editar_lista add/remove <nombre> – Editar lista de seguimiento\n"
    await update.message.reply_text(texto)

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Por favor, escribe el nombre de una carta. Ejemplo: /buscar Force of Will Unlimited")
        return

    nombre_completo = " ".join(context.args).strip()
    palabras = context.args

    # Detectar edición
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

            plt.figure(figsize=(10, 5))
            plt.plot(resultado["fechas"], y, label="Precio Real", marker='o', color="#00ffcc")
            plt.xticks(rotation=45)
            plt.title(f"Evolución de Precios - {resultado['nombre']}")
            plt.xlabel("Fecha")
            plt.ylabel("Precio USD")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plt.savefig("grafico_historico.png")
            plt.close()

            await update.message.reply_document(document=open("grafico_historico.png", "rb"), filename="grafico_historico.png")
        except Exception as e:
            await update.message.reply_text(f"⚠️ No se pudo generar el gráfico histórico: {str(e)}")

    # Gráfico 2: Predicción futura
    if "predicciones" in resultado and isinstance(resultado["predicciones"], list) and len(resultado["predicciones"]) >= 6:
        try:
            fechas_pred = [datetime.now() + timedelta(days=i*30) for i in range(1, 7)]
            predicciones = resultado["predicciones"][:6]

            plt.figure(figsize=(10, 5))
            plt.plot(fechas_pred, predicciones, 'r--', label="Predicción")
            plt.title("🔮 Predicción de precios futuros (6 meses)")
            plt.xlabel("Fecha")
            plt.ylabel("Precio Estimado")
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.legend()
            plt.tight_layout()
            plt.savefig("grafico_prediccion.png")
            plt.close()

            await update.message.reply_document(document=open("grafico_prediccion.png", "rb"), filename="grafico_prediccion.png")
        except Exception as e:
            await update.message.reply_text(f"⚠️ No se pudo generar el gráfico de predicción: {str(e)}")

async def listar_ediciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

                plt.figure(figsize=(10, 5))
                plt.plot(fechas_pred, predicciones, 'r--', label="Predicción")
                plt.title(f"🔮 Predicción de precios futuros - {nombre}")
                plt.xlabel("Fecha")
                plt.ylabel("Precio Estimado")
                plt.grid(True)
                plt.xticks(rotation=45)
                plt.legend()
                plt.tight_layout()
                plt.savefig("grafico_prediccion_auto.png")
                plt.close()

                await context.bot.send_document(chat_id=chat_id, document=open("grafico_prediccion_auto.png", "rb"))
            except Exception as e:
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ No se pudo generar el gráfico: {str(e)}")

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
        await update.message.reply_text("Acción no reconocida. Usa `add` o `remove`.")

def main():
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buscar", buscar))
    application.add_handler(CommandHandler("listar_ediciones", listar_ediciones))
    application.add_handler(CommandHandler("ver_historial", ver_historial))
    application.add_handler(CommandHandler("seguimiento", seguir))
    application.add_handler(CommandHandler("detener_seguimiento", detener_seguimiento))
    application.add_handler(CommandHandler("editar_lista", editar_lista))

    print("✅ Bot iniciado. Esperando comandos...")
    application.run_polling()

if __name__ == "__main__":
    main()
