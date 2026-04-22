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

# Servarr / Jellyfin (via .env)
JELLYFIN_URL = os.getenv("JELLYFIN_URL")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")
SONARR_URL = os.getenv("SONARR_URL")
SONARR_API_KEY = os.getenv("SONARR_API_KEY")
RADARR_URL = os.getenv("RADARR_URL")
RADARR_API_KEY = os.getenv("RADARR_API_KEY")

# Monitoring / Beszel (via .env)
BESZEL_URL = os.getenv("BESZEL_URL")
BESZEL_EMAIL = os.getenv("BESZEL_EMAIL")
BESZEL_PASSWORD = os.getenv("BESZEL_PASSWORD")

# qBittorrent (via .env)
QBITTORRENT_URL = os.getenv("QBITTORRENT_URL")
QBITTORRENT_USERNAME = os.getenv("QBITTORRENT_USERNAME")
QBITTORRENT_PASSWORD = os.getenv("QBITTORRENT_PASSWORD")
