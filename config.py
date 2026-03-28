import os
from dotenv import load_dotenv

load_dotenv()

# Configuration du bot
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = '.'
BOT_DESCRIPTION = "eLFantome Python Discord Bot"

# Messages
MESSAGES = {
    'bot_ready': 'Bot démarré avec succès ! 🚀',
    'error_generic': 'Une erreur est survenue. 😞',
    'no_permission': 'Vous n\'avez pas la permission d\'utiliser cette commande. 🚫'
}

# Couleurs
COLORS = {
    'success': 0x00ff00,
    'error': 0xff0000,
    'info': 0x0099ff,
    'warning': 0xffaa00
}

# API KEYS (via .env)
STEAM_API = os.getenv("STEAM_API")
TRN_API_KEY = os.getenv("TRN_API_KEY")
ITAD_API_KEY = os.getenv("ITAD_API_KEY")