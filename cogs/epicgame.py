import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
import os
from datetime import datetime, timedelta
import logging

class EpicGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.channels_file = "free_games_channels.json"
        self.history_file = "games_history.json"
        self.channels = self.load_channels()
        self.games_history = self.load_history()
        self.check_free_games.start()
        
    def load_channels(self):
        """Charge les canaux configurés depuis un fichier JSON"""
        if os.path.exists(self.channels_file):
            try:
                with open(self.channels_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erreur chargement canaux: {e}")
                return {}
        return {}
    
    def save_channels(self):
        """Sauvegarde les canaux configurés dans un fichier JSON"""
        try:
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump(self.channels, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Erreur sauvegarde canaux: {e}")
    
    def load_history(self):
        """Charge l'historique des jeux pour détecter les changements"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erreur chargement historique: {e}")
                return {"epic": [], "last_check": None}
        return {"epic": [], "last_check": None}
    
    def save_history(self):
        """Sauvegarde l'historique des jeux"""
        try:
            self.games_history["last_check"] = datetime.now().isoformat()
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.games_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Erreur sauvegarde historique: {e}")
    
    async def get_session(self):
        """Obtient une session aiohttp réutilisable"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def fetch_epic_games(self):
        """Récupère les jeux gratuits d'Epic Games"""
        url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
        
        try:
            session = await self.get_session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return self.parse_epic_games(data)
                else:
                    logging.error(f"Erreur API Epic Games: {response.status}")
                    return []
        except asyncio.TimeoutError:
            logging.error("Timeout lors de la récupération des jeux Epic")
            return []
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des jeux Epic: {e}")
            return []
    
    def parse_epic_games(self, data):
        """Parse les données de l'API Epic Games"""
        free_games = []
        
        try:
            games = data.get('data', {}).get('Catalog', {}).get('searchStore', {}).get('elements', [])
            
            for game in games:
                # Vérifier si le jeu est gratuit
                price = game.get('price', {})
                if price.get('totalPrice', {}).get('discountPrice', 0) == 0:
                    # Vérifier les promotions
                    promotions = game.get('promotions', {})
                    promotional_offers = promotions.get('promotionalOffers', [])
                    upcoming_offers = promotions.get('upcomingPromotionalOffers', [])
                    
                    # Jeu actuellement gratuit
                    if promotional_offers:
                        for offer_set in promotional_offers:
                            for offer in offer_set.get('promotionalOffers', []):
                                game_info = self.extract_epic_game_info(game, offer, "current")
                                if game_info:
                                    free_games.append(game_info)
                    
                    # Jeu qui sera gratuit bientôt
                    elif upcoming_offers:
                        for offer_set in upcoming_offers:
                            for offer in offer_set.get('promotionalOffers', []):
                                game_info = self.extract_epic_game_info(game, offer, "upcoming")
                                if game_info:
                                    free_games.append(game_info)
        
        except Exception as e:
            logging.error(f"Erreur lors du parsing des jeux Epic: {e}")
        
        return free_games
    
    def extract_epic_game_info(self, game, offer, status):
        """Extrait les informations importantes d'un jeu Epic"""
        try:
            title = game.get('title', 'Titre inconnu')
            description = game.get('description', 'Pas de description')
            
            # Images
            images = game.get('keyImages', [])
            thumbnail = None
            for img in images:
                if img.get('type') in ['Thumbnail', 'OfferImageWide', 'OfferImageTall']:
                    thumbnail = img.get('url')
                    break
            
            # Dates
            start_date = offer.get('startDate')
            end_date = offer.get('endDate')
            
            # URL du jeu
            store_url = self.generate_epic_store_url(game)
            
            return {
                'id': f"epic_{game.get('id', '')}",
                'title': title,
                'description': description[:500] + "..." if len(description) > 500 else description,
                'thumbnail': thumbnail,
                'start_date': start_date,
                'end_date': end_date,
                'store_url': store_url,
                'status': status,
                'platform': 'Epic Games',
                'original_price': game.get('price', {}).get('totalPrice', {}).get('originalPrice', 0),
                'namespace': game.get('namespace'),
                'offer_id': game.get('id')
            }
        except Exception as e:
            logging.error(f"Erreur extraction info jeu Epic: {e}")
            return None
    
    def generate_epic_store_url(self, game):
        """Génère l'URL du store Epic Games"""
        namespace = game.get('namespace')
        offer_id = game.get('id')
        
        if namespace and offer_id:
            return f"https://store.epicgames.com/purchase?offers=1-{namespace}-{offer_id}"
        
        url_slug = game.get('urlSlug', '')
        if url_slug:
            return f"https://store.epicgames.com/fr/p/{url_slug}"
        
        product_slug = game.get('productSlug', '')
        if product_slug:
            return f"https://store.epicgames.com/fr/p/{product_slug}"
        
        return "https://store.epicgames.com/fr/free-games"
    
    def create_game_embed(self, game, is_new=False):
        """Crée un embed Discord pour un jeu"""
        status_text = {
            'current': '✅ **GRATUIT MAINTENANT**',
            'upcoming': '⏰ **BIENTÔT GRATUIT**'
        }
        
        # Titre avec badge "NOUVEAU" si c'est un nouveau jeu
        title = f"🎮 {game['title']}"
        if is_new:
            title = f"🆕 {game['title']}"
        
        embed = discord.Embed(
            title=title,
            description=game['description'],
            color=0x00FF00 if is_new else 0x313131,
            url=game['store_url']
        )
        
        embed.add_field(
            name="Plateforme",
            value="Epic Games Store",
            inline=True
        )
        
        embed.add_field(
            name="Statut",
            value=status_text.get(game['status'], 'Inconnu'),
            inline=True
        )
        
        # Dates
        if game['start_date']:
            try:
                start_date = datetime.fromisoformat(game['start_date'].replace('Z', '+00:00'))
                embed.add_field(
                    name="Début",
                    value=f"<t:{int(start_date.timestamp())}:F>",
                    inline=True
                )
            except:
                pass
        
        if game['end_date']:
            try:
                end_date = datetime.fromisoformat(game['end_date'].replace('Z', '+00:00'))
                embed.add_field(
                    name="Fin",
                    value=f"<t:{int(end_date.timestamp())}:F>",
                    inline=True
                )
            except:
                pass
        
        if game.get('original_price', 0) > 0:
            price = game['original_price'] / 100
            embed.add_field(
                name="Prix original",
                value=f"{price:.2f} CAD",
                inline=True
            )
        
        if game['thumbnail']:
            embed.set_image(url=game['thumbnail'])
        
        footer_text = "Epic Games Store"
        if is_new:
            footer_text += " • 🆕 Nouveau jeu gratuit !"
        embed.set_footer(text=footer_text)
        
        return embed
    
    def detect_changes(self, new_games):
        """Détecte les nouveaux jeux par rapport à l'historique"""
        old_games = self.games_history.get('epic', [])
        old_ids = set(game.get('id', '') for game in old_games)
        
        new_games_list = []
        for game in new_games:
            game_id = game.get('id', '')
            if game_id and game_id not in old_ids:
                new_games_list.append(game)
                logging.info(f"Nouveau jeu détecté: {game.get('title', 'Inconnu')}")
        
        return new_games_list
    
    async def send_to_configured_channel(self, guild, games, new_only=False):
        """Envoie les jeux gratuits au canal configuré pour ce serveur"""
        guild_id = str(guild.id)
        
        # Vérifier si un canal est configuré pour ce serveur
        if guild_id not in self.channels:
            logging.info(f"Aucun canal configuré pour {guild.name}")
            return
        
        channel_id = self.channels[guild_id]
        channel = guild.get_channel(channel_id)
        
        if not channel:
            logging.warning(f"Canal {channel_id} non trouvé sur {guild.name}")
            return
        
        try:
            if games:
                # Message d'en-tête différent selon le contexte
                if new_only:
                    await channel.send("🆕 **Nouveaux jeux gratuits Epic Games détectés !**")
                else:
                    await channel.send("🎮 **Jeux gratuits Epic Games disponibles !**")
                
                for game in games:
                    embed = self.create_game_embed(game, is_new=new_only)
                    await channel.send(embed=embed)
            else:
                logging.info(f"Aucun nouveau jeu à envoyer pour {guild.name}")
                    
        except Exception as e:
            logging.error(f"Erreur envoi dans canal pour {guild.name}: {e}")
    
    @commands.group(name='freegames', aliases=['fg'])
    async def freegames(self, ctx):
        """Affiche les jeux gratuits Epic Games"""
        if ctx.invoked_subcommand is None:
            # Afficher directement les jeux Epic Games
            await self.epic_games_command(ctx)
    
    @freegames.command(name='setchannel')
    @commands.has_permissions(manage_channels=True)
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """Définit le canal pour les annonces de jeux gratuits"""
        if channel is None:
            # Si aucun canal n'est mentionné, utiliser le canal actuel
            channel = ctx.channel
        
        guild_id = str(ctx.guild.id)
        self.channels[guild_id] = channel.id
        self.save_channels()
        
        embed = discord.Embed(
            title="✅ Canal configuré",
            description=f"Les annonces de jeux gratuits seront envoyées dans {channel.mention}",
            color=0x00ff00
        )
        await ctx.send(embed=embed)
    
    @freegames.command(name='removechannel')
    @commands.has_permissions(manage_channels=True)
    async def remove_channel(self, ctx):
        """Retire le canal configuré pour les annonces"""
        guild_id = str(ctx.guild.id)
        
        if guild_id in self.channels:
            del self.channels[guild_id]
            self.save_channels()
            
            embed = discord.Embed(
                title="✅ Canal retiré",
                description="Les annonces automatiques ont été désactivées pour ce serveur.",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="ℹ️ Aucun canal configuré",
                description="Il n'y a pas de canal configuré pour ce serveur.",
                color=0x3498db
            )
            await ctx.send(embed=embed)
    
    @freegames.command(name='channel')
    async def show_channel(self, ctx):
        """Affiche le canal actuellement configuré"""
        guild_id = str(ctx.guild.id)
        
        if guild_id in self.channels:
            channel_id = self.channels[guild_id]
            channel = ctx.guild.get_channel(channel_id)
            
            if channel:
                embed = discord.Embed(
                    title="📢 Canal configuré",
                    description=f"Les annonces sont envoyées dans {channel.mention}",
                    color=0x3498db
                )
                # Ajouter info sur la dernière vérification
                if self.games_history.get("last_check"):
                    last_check = datetime.fromisoformat(self.games_history["last_check"])
                    embed.add_field(
                        name="Dernière vérification",
                        value=f"<t:{int(last_check.timestamp())}:R>",
                        inline=False
                    )
            else:
                embed = discord.Embed(
                    title="⚠️ Canal introuvable",
                    description=f"Le canal configuré (ID: {channel_id}) n'existe plus.",
                    color=0xff9900
                )
        else:
            embed = discord.Embed(
                title="ℹ️ Aucun canal configuré",
                description="Utilisez `.freegames setchannel #canal` pour configurer un canal.",
                color=0x3498db
            )
        
        await ctx.send(embed=embed)
    
    @freegames.command(name='epic')
    async def epic_games_command(self, ctx):
        """Affiche les jeux gratuits Epic Games actuels"""
        async with ctx.typing():
            try:
                free_games = await self.fetch_epic_games()
                
                if not free_games:
                    embed = discord.Embed(
                        title="Aucun jeu gratuit trouvé sur Epic Games",
                        description="Il n'y a actuellement aucun jeu gratuit sur Epic Games Store.",
                        color=0xff0000
                    )
                    await ctx.send(embed=embed)
                    return
                
                for game in free_games:
                    embed = self.create_game_embed(game)
                    await ctx.send(embed=embed)
                    
            except Exception as e:
                logging.error(f"Erreur commande epic: {e}")
                await ctx.send("❌ Une erreur s'est produite lors de la récupération des jeux Epic Games.")
    
    @freegames.command(name='forcechek')
    @commands.has_permissions(administrator=True)
    async def force_check(self, ctx):
        """Force une vérification immédiate des jeux gratuits (Admin seulement)"""
        async with ctx.typing():
            try:
                logging.info(f"Vérification forcée par {ctx.author}")
                
                # Récupérer les jeux Epic Games
                epic_games = await self.fetch_epic_games()
                
                if epic_games:
                    # Détecter les NOUVEAUX jeux
                    new_games = self.detect_changes(epic_games)
                    
                    if new_games:
                        embed = discord.Embed(
                            title="🆕 Nouveaux jeux détectés !",
                            description=f"{len(new_games)} nouveau(x) jeu(x) trouvé(s)",
                            color=0x00ff00
                        )
                        await ctx.send(embed=embed)
                        
                        # Envoyer aux canaux configurés
                        for guild in self.bot.guilds:
                            await self.send_to_configured_channel(guild, new_games, new_only=True)
                    else:
                        embed = discord.Embed(
                            title="ℹ️ Aucun nouveau jeu",
                            description=f"Tous les {len(epic_games)} jeu(x) sont déjà dans l'historique",
                            color=0x3498db
                        )
                        await ctx.send(embed=embed)
                    
                    # Mettre à jour l'historique
                    self.games_history['epic'] = epic_games
                    self.save_history()
                else:
                    embed = discord.Embed(
                        title="❌ Aucun jeu trouvé",
                        description="Impossible de récupérer les jeux Epic Games",
                        color=0xff0000
                    )
                    await ctx.send(embed=embed)
                    
            except Exception as e:
                logging.error(f"Erreur vérification forcée: {e}")
                await ctx.send(f"❌ Erreur: {str(e)}")
    
    @freegames.command(name='test')
    @commands.is_owner()
    async def test_command(self, ctx):
        """Test de base pour vérifier si le cog répond"""
        embed = discord.Embed(
            title="✅ Test Réussi",
            description="Le cog Epic Games fonctionne correctement !",
            color=0x00ff00
        )
        
        # Info sur l'historique
        epic_count = len(self.games_history.get('epic', []))
        embed.add_field(name="Jeux en historique", value=str(epic_count), inline=True)
        embed.add_field(name="Canaux configurés", value=str(len(self.channels)), inline=True)
        
        await ctx.send(embed=embed)
     
    @tasks.loop(hours=6)
    async def check_free_games(self):
        """Vérifie automatiquement les jeux gratuits Epic Games toutes les 6h"""
        try:
            logging.info("Vérification automatique des jeux gratuits Epic Games...")
            
            # Récupérer les jeux Epic Games
            epic_games = await self.fetch_epic_games()
            
            if epic_games:
                logging.info(f"Jeux Epic Games trouvés: {len(epic_games)}")
                
                # Détecter les NOUVEAUX jeux
                new_games = self.detect_changes(epic_games)
                
                if new_games:
                    logging.info(f"Nouveaux jeux détectés: {len(new_games)}")
                    
                    # Envoyer SEULEMENT les nouveaux jeux aux serveurs configurés
                    for guild in self.bot.guilds:
                        await self.send_to_configured_channel(guild, new_games, new_only=True)
                else:
                    logging.info("Aucun nouveau jeu détecté")
                
                # Mettre à jour l'historique avec TOUS les jeux actuels
                self.games_history['epic'] = epic_games
                self.save_history()
            else:
                logging.info("Aucun jeu Epic Games trouvé")
        
        except Exception as e:
            logging.error(f"Erreur vérification automatique: {e}")
    
    @check_free_games.before_loop
    async def before_check_free_games(self):
        """Attend que le bot soit prêt avant de démarrer les vérifications"""
        await self.bot.wait_until_ready()
        logging.info("Bot prêt, vérification initiale des jeux Epic Games...")
        
        # VÉRIFICATION IMMÉDIATE au démarrage
        try:
            epic_games = await self.fetch_epic_games()
            
            if epic_games:
                # Si l'historique est vide, initialiser sans envoyer de notifications
                if not self.games_history.get('epic'):
                    logging.info(f"Initialisation de l'historique avec {len(epic_games)} jeu(x)")
                    self.games_history['epic'] = epic_games
                    self.save_history()
                else:
                    # Sinon, vérifier les nouveaux jeux normalement
                    new_games = self.detect_changes(epic_games)
                    if new_games:
                        logging.info(f"Nouveaux jeux détectés au démarrage: {len(new_games)}")
                        for guild in self.bot.guilds:
                            await self.send_to_configured_channel(guild, new_games, new_only=True)
                    
                    self.games_history['epic'] = epic_games
                    self.save_history()
        except Exception as e:
            logging.error(f"Erreur lors de la vérification initiale: {e}")
        
        logging.info("Démarrage de la vérification automatique (toutes les 6h)")
    
    async def cog_unload(self):
        """Nettoie les ressources quand le cog est déchargé"""
        self.check_free_games.cancel()
        if self.session and not self.session.closed:
            await self.session.close()

async def setup(bot):
    await bot.add_cog(EpicGames(bot))