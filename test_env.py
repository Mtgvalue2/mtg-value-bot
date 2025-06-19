import os
from dotenv import load_dotenv

# Forzar carga desde ruta absoluta
env_path = os.path.join(os.getcwd(), '.env')
print(f"📄 Cargando desde: {env_path}")

if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    print("❌ Archivo .env NO encontrado")

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

print(f"🔑 TOKEN LEÍDO: {token}")
print(f"🆔 CHAT ID LEÍDO: {chat_id}")
