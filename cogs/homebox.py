import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
import json

class homebox(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Configuration Jellyfin
        self.jellyfin_url = "http://192.168.2.113:8096"
        self.api_key = "6903502dc64c45009719e27c85fa8396"
        self.user_id = None
        
        # Configuration Sonarr
        self.sonarr_url = "http://192.168.2.113:8989"
        self.sonarr_api_key = "b510c49ada25474fb23be54a11c2a225"
        
        # Configuration Radarr
        self.radarr_url = "http://192.168.2.113:7878"
        self.radarr_api_key = "67071cbd878e4496b9f047d053f92184"
        
    async def get_jellyfin_user_id(self):
        """Obtient l'ID utilisateur Jellyfin"""
        if self.user_id:
            return self.user_id
            
        url = f"{self.jellyfin_url}/Users"
        headers = {"X-Emby-Token": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        users = await response.json()
                        admin_user = next((user for user in users if user.get("Policy", {}).get("IsAdministrator")), None)
                        self.user_id = admin_user["Id"] if admin_user else users[0]["Id"]
                        return self.user_id
                    else:
                        return None
            except Exception as e:
                print(f"Erreur lors de la récupération de l'ID utilisateur: {e}")
                return None

    def get_image_url(self, item_id, image_type="Primary", width=300, height=450):
        """Génère l'URL pour l'image d'un élément avec authentification"""
        return f"{self.jellyfin_url}/Items/{item_id}/Images/{image_type}?width={width}&height={height}&X-Emby-Token={self.api_key}"

    async def get_latest_movies(self, limit=1):
        """Récupère les derniers films ajoutés"""
        user_id = await self.get_jellyfin_user_id()
        if not user_id:
            return None
            
        url = f"{self.jellyfin_url}/Users/{user_id}/Items"
        params = {
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "Fields": "DateCreated,Overview,Genres,ProductionYear,CommunityRating,ImageTags",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "Limit": limit
        }
        headers = {"X-Emby-Token": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("Items", [])
                    else:
                        return None
            except Exception as e:
                print(f"Erreur lors de la récupération des films: {e}")
                return None

    async def get_latest_series(self, limit=1):
        """Récupère les dernières séries ajoutées"""
        user_id = await self.get_jellyfin_user_id()
        if not user_id:
            return None
            
        url = f"{self.jellyfin_url}/Users/{user_id}/Items"
        params = {
            "IncludeItemTypes": "Series",
            "Recursive": "true",
            "Fields": "DateCreated,Overview,Genres,ProductionYear,CommunityRating,ImageTags",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "Limit": limit
        }
        headers = {"X-Emby-Token": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("Items", [])
                    else:
                        return None
            except Exception as e:
                print(f"Erreur lors de la récupération des séries: {e}")
                return None

    async def get_radarr_stats(self):
        """Récupère les statistiques Radarr"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Api-Key": self.radarr_api_key}
                
                # Récupérer les films manquants (wanted)
                wanted_url = f"{self.radarr_url}/api/v3/wanted/missing"
                params = {"pageSize": 1}
                async with session.get(wanted_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        wanted_data = await response.json()
                        wanted_count = wanted_data.get("totalRecords", 0)
                    else:
                        wanted_count = 0
                
                # Récupérer la file d'attente
                queue_url = f"{self.radarr_url}/api/v3/queue"
                async with session.get(queue_url, headers=headers) as response:
                    if response.status == 200:
                        queue_data = await response.json()
                        queued_count = queue_data.get("totalRecords", 0)
                    else:
                        queued_count = 0
                
                # Récupérer le nombre total de films
                movies_url = f"{self.radarr_url}/api/v3/movie"
                async with session.get(movies_url, headers=headers) as response:
                    if response.status == 200:
                        movies_data = await response.json()
                        total_movies = len(movies_data)
                    else:
                        total_movies = 0
                
                return {
                    "wanted": wanted_count,
                    "queued": queued_count,
                    "total": total_movies,
                    "success": True
                }
        except Exception as e:
            print(f"Erreur Radarr: {e}")
            return {"success": False, "error": str(e)}

    async def get_sonarr_stats(self):
        """Récupère les statistiques Sonarr"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Api-Key": self.sonarr_api_key}
                
                # Récupérer les épisodes manquants (wanted)
                wanted_url = f"{self.sonarr_url}/api/v3/wanted/missing"
                params = {"pageSize": 1}
                async with session.get(wanted_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        wanted_data = await response.json()
                        wanted_count = wanted_data.get("totalRecords", 0)
                    else:
                        wanted_count = 0
                
                # Récupérer la file d'attente
                queue_url = f"{self.sonarr_url}/api/v3/queue"
                async with session.get(queue_url, headers=headers) as response:
                    if response.status == 200:
                        queue_data = await response.json()
                        queued_count = queue_data.get("totalRecords", 0)
                    else:
                        queued_count = 0
                
                # Récupérer le nombre total de séries
                series_url = f"{self.sonarr_url}/api/v3/series"
                async with session.get(series_url, headers=headers) as response:
                    if response.status == 200:
                        series_data = await response.json()
                        total_series = len(series_data)
                    else:
                        total_series = 0
                
                return {
                    "wanted": wanted_count,
                    "queued": queued_count,
                    "total": total_series,
                    "success": True
                }
        except Exception as e:
            print(f"Erreur Sonarr: {e}")
            return {"success": False, "error": str(e)}

    def format_movie_info(self, movie):
        """Formate les informations d'un film"""
        title = movie.get("Name", "Titre inconnu")
        year = movie.get("ProductionYear", "Année inconnue")
        rating = movie.get("CommunityRating")
        genres = movie.get("Genres", [])
        overview = movie.get("Overview", "")
        date_added = movie.get("DateCreated", "")
        
        if date_added:
            try:
                date_obj = datetime.fromisoformat(date_added.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime("%d/%m/%Y à %H:%M")
            except:
                formatted_date = "Date inconnue"
        else:
            formatted_date = "Date inconnue"
        
        rating_text = f" ⭐ {rating}/10" if rating else ""
        genres_text = ", ".join(genres[:3]) if genres else "Genres inconnus"
        
        if overview and len(overview) > 150:
            overview = overview[:150] + "..."
        
        return {
            "title": title,
            "year": year,
            "rating": rating_text,
            "genres": genres_text,
            "overview": overview or "Pas de description disponible",
            "date_added": formatted_date,
            "full_overview": movie.get("Overview", "Pas de description disponible")
        }

    def format_series_info(self, series):
        """Formate les informations d'une série"""
        title = series.get("Name", "Titre inconnu")
        year = series.get("ProductionYear", "Année inconnue")
        rating = series.get("CommunityRating")
        genres = series.get("Genres", [])
        overview = series.get("Overview", "")
        date_added = series.get("DateCreated", "")
        
        if date_added:
            try:
                date_obj = datetime.fromisoformat(date_added.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime("%d/%m/%Y à %H:%M")
            except:
                formatted_date = "Date inconnue"
        else:
            formatted_date = "Date inconnue"
        
        rating_text = f" ⭐ {rating}/10" if rating else ""
        genres_text = ", ".join(genres[:3]) if genres else "Genres inconnus"
        
        if overview and len(overview) > 150:
            overview = overview[:150] + "..."
        
        return {
            "title": title,
            "year": year,
            "rating": rating_text,
            "genres": genres_text,
            "overview": overview or "Pas de description disponible",
            "date_added": formatted_date,
            "full_overview": series.get("Overview", "Pas de description disponible")
        }

    @commands.command(name="radarr")
    async def radarr_stats(self, ctx):
        """Affiche les statistiques Radarr"""
        await ctx.send("🎬 Récupération des statistiques Radarr...")
        
        stats = await self.get_radarr_stats()
        
        if not stats["success"]:
            embed = discord.Embed(
                title="❌ Erreur Radarr",
                description=f"Impossible de se connecter à Radarr.\n```{stats.get('error', 'Erreur inconnue')}```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🎬 Statistiques Radarr",
            description=f"**{stats['wanted']} Wanted • {stats['queued']} Queued • {stats['total']} Movies**",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🔥 Films manquants",
            value=f"**{stats['wanted']}** films recherchés",
            inline=True
        )
        
        embed.add_field(
            name="⏳ En file d'attente",
            value=f"**{stats['queued']}** téléchargements",
            inline=True
        )
        
        embed.add_field(
            name="🎞️ Bibliothèque totale",
            value=f"**{stats['total']}** films",
            inline=True
        )
        
        embed.set_footer(text=f"Radarr • {self.radarr_url}", icon_url="https://radarr.video/img/logo.png")
        await ctx.send(embed=embed)

    @commands.command(name="sonarr")
    async def sonarr_stats(self, ctx):
        """Affiche les statistiques Sonarr"""
        await ctx.send("📺 Récupération des statistiques Sonarr...")
        
        stats = await self.get_sonarr_stats()
        
        if not stats["success"]:
            embed = discord.Embed(
                title="❌ Erreur Sonarr",
                description=f"Impossible de se connecter à Sonarr.\n```{stats.get('error', 'Erreur inconnue')}```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📺 Statistiques Sonarr",
            description=f"**{stats['wanted']} Wanted • {stats['queued']} Queued • {stats['total']} Series**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🔥 Épisodes manquants",
            value=f"**{stats['wanted']}** épisodes recherchés",
            inline=True
        )
        
        embed.add_field(
            name="⏳ En file d'attente",
            value=f"**{stats['queued']}** téléchargements",
            inline=True
        )
        
        embed.add_field(
            name="📺 Bibliothèque totale",
            value=f"**{stats['total']}** séries",
            inline=True
        )
        
        embed.set_footer(text=f"Sonarr • {self.sonarr_url}", icon_url="https://sonarr.tv/img/logo.png")
        await ctx.send(embed=embed)

    @commands.command(name="lastmovie", aliases=["latest_movies", "films"])
    async def latest_movies_command(self, ctx, nombre: int = 1):
        """Affiche le dernier film ajouté !lastmovie [nombre]"""
        if nombre < 1 or nombre > 10:
            await ctx.send("❌ Le nombre doit être entre 1 et 10.")
            return
            
        await ctx.send("🎬 Récupération des derniers films...")
        
        movies = await self.get_latest_movies(nombre)
        
        if movies is None:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Impossible de se connecter à Jellyfin. Vérifiez la configuration.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        if not movies:
            embed = discord.Embed(
                title="🎞️ Aucun film trouvé",
                description="Aucun film n'a été trouvé sur votre serveur Jellyfin.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        if nombre == 1:
            movie = movies[0]
            movie_info = self.format_movie_info(movie)
            
            embed = discord.Embed(
                title=f"🎬 {movie_info['title']} ({movie_info['year']})",
                description=movie_info['full_overview'],
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🎭 Genres", value=movie_info['genres'], inline=True)
            if movie_info['rating']:
                embed.add_field(name="📊 Note", value=movie_info['rating'], inline=True)
            embed.add_field(name="📅 Ajouté le", value=movie_info['date_added'], inline=True)
            
            if movie.get("ImageTags", {}).get("Primary"):
                poster_url = self.get_image_url(movie["Id"])
                embed.set_image(url=poster_url)
            
            embed.set_footer(text="Jellyfin Bot", icon_url="https://jellyfin.org/images/favicon.ico")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"🎬 Les {len(movies)} derniers films ajoutés",
                description=f"Sur le serveur Jellyfin: `{self.jellyfin_url}`",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for i, movie in enumerate(movies, 1):
                movie_info = self.format_movie_info(movie)
                
                field_name = f"{i}. {movie_info['title']} ({movie_info['year']}){movie_info['rating']}"
                field_value = f"**Genres:** {movie_info['genres']}\n"
                field_value += f"**Ajouté le:** {movie_info['date_added']}\n"
                field_value += f"**Description:** {movie_info['overview']}"
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )
            
            embed.set_footer(text="Jellyfin Bot", icon_url="https://jellyfin.org/images/favicon.ico")
            await ctx.send(embed=embed)

    @commands.command(name="lastseries", aliases=["latest_series", "series"])
    async def latest_series_command(self, ctx, nombre: int = 1):
        """Affiche la dernière série ajoutée: !lastseries [nombre]"""
        if nombre < 1 or nombre > 10:
            await ctx.send("❌ Le nombre doit être entre 1 et 10.")
            return
            
        await ctx.send("📺 Récupération des dernières séries...")
        
        series = await self.get_latest_series(nombre)
        
        if series is None:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Impossible de se connecter à Jellyfin. Vérifiez la configuration.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        if not series:
            embed = discord.Embed(
                title="📺 Aucune série trouvée",
                description="Aucune série n'a été trouvée sur votre serveur Jellyfin.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        if nombre == 1:
            show = series[0]
            series_info = self.format_series_info(show)
            
            embed = discord.Embed(
                title=f"📺 {series_info['title']} ({series_info['year']})",
                description=series_info['full_overview'],
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🎭 Genres", value=series_info['genres'], inline=True)
            if series_info['rating']:
                embed.add_field(name="📊 Note", value=series_info['rating'], inline=True)
            embed.add_field(name="📅 Ajouté le", value=series_info['date_added'], inline=True)
            
            if show.get("ImageTags", {}).get("Primary"):
                poster_url = self.get_image_url(show["Id"])
                embed.set_image(url=poster_url)
            
            embed.set_footer(text="Jellyfin Bot", icon_url="https://jellyfin.org/images/favicon.ico")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"📺 Les {len(series)} dernières séries ajoutées",
                description=f"Sur le serveur Jellyfin: `{self.jellyfin_url}`",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            
            for i, show in enumerate(series, 1):
                series_info = self.format_series_info(show)
                
                field_name = f"{i}. {series_info['title']} ({series_info['year']}){series_info['rating']}"
                field_value = f"**Genres:** {series_info['genres']}\n"
                field_value += f"**Ajouté le:** {series_info['date_added']}\n"
                field_value += f"**Description:** {series_info['overview']}"
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )
            
            embed.set_footer(text="Jellyfin Bot", icon_url="https://jellyfin.org/images/favicon.ico")
            await ctx.send(embed=embed)

    @commands.command(name="config_jellyfin")
    @commands.has_permissions(administrator=True)
    async def config_jellyfin(self, ctx, url: str = None, api_key: str = None):
        """Configuration Jellyfin: !config_jellyfin <url> <api_key>"""
        if url:
            self.jellyfin_url = url.rstrip('/')
        if api_key:
            self.api_key = api_key
            self.user_id = None
        
        embed = discord.Embed(
            title="⚙️ Configuration mise à jour",
            description=f"**URL Jellyfin:** `{self.jellyfin_url}`\n**API Key:** `{'*' * len(self.api_key) if self.api_key else 'Non définie'}`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="test_jellyfin")
    async def test_jellyfin(self, ctx):
        """Teste la connexion à Jellyfin"""
        await ctx.send("🔍 Test de connexion à Jellyfin...")
        
        user_id = await self.get_jellyfin_user_id()
        if user_id:
            embed = discord.Embed(
                title="✅ Connexion réussie",
                description=f"Connecté à Jellyfin sur `{self.jellyfin_url}`\nUtilisateur ID: `{user_id}`",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Échec de la connexion",
                description="Vérifiez l'URL du serveur et la clé API.",
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @latest_movies_command.error
    async def latest_movies_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Veuillez fournir un nombre valide.")
        else:
            await ctx.send(f"❌ Une erreur s'est produite: {str(error)}")

    @latest_series_command.error
    async def latest_series_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Veuillez fournir un nombre valide.")
        else:
            await ctx.send(f"❌ Une erreur s'est produite: {str(error)}")

    @config_jellyfin.error
    async def config_jellyfin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Vous devez être administrateur pour utiliser cette commande.")

async def setup(bot):
    await bot.add_cog(homebox(bot))