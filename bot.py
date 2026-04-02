import discord
from discord.ext import commands
import asyncio
import os
import sys
from datetime import datetime
from config import BOT_TOKEN, BOT_PREFIX, BOT_DESCRIPTION, MESSAGES, COLORS

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class CustomBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shutdown_requested = False
        self.start_time = None
        
    async def close(self):
        """Fermeture propre du bot"""
        if self.shutdown_requested:
            return
            
        self.shutdown_requested = True
        print("🛑 Fermeture du bot en cours...")
        
        # Annuler toutes les tâches en cours
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        if tasks:
            print(f"Annulation de {len(tasks)} tâches en cours...")
            for task in tasks:
                task.cancel()
            
            # Attendre que les tâches se terminent (avec timeout)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), 
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                print("Timeout lors de la fermeture des tâches")
        
        # Fermer la connexion Discord
        await super().close()
        print("✅ Bot fermé proprement")

# Désactiver la commande help par défaut
bot = commands.Bot(
    command_prefix=BOT_PREFIX,
    help_command=None,    # ⚠️ Ligne cruciale
    intents=discord.Intents.all()
)

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    bot.start_time = datetime.now()
    print(f'{bot.user} est connecté!')
    print(f'Démarrage à: {bot.start_time.strftime("%d/%m/%Y à %H:%M:%S")}')
    
    # Définir le jeu personnalisé
    game = discord.Game("Python | .help")
    await bot.change_presence(activity=game)
    print("🎮 Statut défini: Learning Python")

@bot.event
async def on_disconnect():
    """Événement de déconnexion"""
    print("🔌 Déconnecté de Discord.")

@bot.event
async def on_close():
    """Événement de fermeture"""
    print("🛑 Fermeture du bot...")

async def load_extensions():
    """Charge toutes les extensions du bot"""
    extensions = [
        'cogs.admin',             # Fichier: cogs/admin.py
        'cogs.botinfo',           # Fichier: cogs/botinfo.py
        'cogs.serverinfo',        # Fichier: cogs/serverinfo.py
        'cogs.help',              # Fichier: cogs/help.py
        'cogs.steam',             # Fichier: cogs/steam.py
        'cogs.tarkov',            # Fichier: cogs/tarkov.py
        'cogs.epicgame',          # Fichier: cogs/epicgame.py
        'cogs.nmap',              # Fichier: cogs/nmap.py
        'cogs.reminder',          # Fichier: cogs/reminder.py
        'cogs.geo',               # Fichier: cogs/geo.py
        'cogs.meteo',             # Fichier: cogs/meteo.py
        'cogs.homebox',          # Fichier: cogs/homebox.py 
        'cogs.qbittorrent',          # Fichier: cogs/qbittorrent.py 
    ]
    
    print("📦 Chargement des extensions...")
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            print(f'✅ Extension {extension} chargée')
        except Exception as e:
            print(f'❌ Erreur lors du chargement de {extension}: {e}')
    
    print(f"📦 {len(bot.cogs)} extensions chargées au total")

async def main():
    """Fonction principale avec gestion des erreurs"""
    try:
        print("🚀 Démarrage du bot...")
        
        # Charger les extensions avant de démarrer
        await load_extensions()
        
        # Démarrer le bot avec gestion automatique des ressources
        async with bot:
            await bot.start(BOT_TOKEN)
            
    except KeyboardInterrupt:
        print("\n⏹️ Ctrl+C détecté, arrêt du bot...")
    except discord.LoginFailure:
        print("❌ Erreur de connexion: Token invalide")
    except discord.HTTPException as e:
        print(f"❌ Erreur HTTP Discord: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
    finally:
        # S'assurer que le bot est fermé
        if not bot.is_closed():
            await bot.close()
        
        # Attendre un peu pour que toutes les tâches se terminent
        await asyncio.sleep(1)
        
        # Nettoyer les tâches restantes
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        if tasks:
            print(f"🧹 Nettoyage de {len(tasks)} tâches restantes...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == '__main__':
    try:
        # Utiliser la politique d'événements appropriée pour Windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Ignore l'interruption clavier
    except Exception as e:
        print(f"💥 Erreur fatale : {e}")
    finally:
        print("👋 Programme terminé")
