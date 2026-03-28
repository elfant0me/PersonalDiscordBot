# cogs/steam.py

import discord
from discord.ext import commands
import aiohttp
import json
from datetime import datetime
import re
import config
import os
from bs4 import BeautifulSoup  # pip install beautifulsoup4

class Steam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.steam_api_key = config.STEAM_API
        self.user_steam_data = {}
        self.load_user_data()

    def load_user_data(self):
        try:
            with open('userdata/steam_data.json', 'r', encoding='utf-8') as f:
                self.user_steam_data = json.load(f)
        except:
            self.user_steam_data = {}

    def save_user_data(self):
        os.makedirs('userdata', exist_ok=True)
        with open('userdata/steam_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.user_steam_data, f, indent=4, ensure_ascii=False)

    async def get_steam_id_from_url(self, custom_url):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?key={self.steam_api_key}&vanityurl={custom_url}"
                async with session.get(url) as response:
                    data = await response.json()
                    if data['response']['success'] == 1:
                        return data['response']['steamid']
                    return None
        except Exception as e:
            print(f"Erreur lors de la résolution de l'URL: {e}")
            return None

    async def get_steam_profile(self, steam_id):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={self.steam_api_key}&steamids={steam_id}"
                async with session.get(url) as response:
                    data = await response.json()
                    if data['response']['players']:
                        return data['response']['players'][0]
                    return None
        except Exception as e:
            print(f"Erreur lors de la récupération du profil: {e}")
            return None

    async def get_recent_games(self, steam_id):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/?key={self.steam_api_key}&steamid={steam_id}&format=json"
                async with session.get(url) as response:
                    data = await response.json()
                    if 'response' in data and 'games' in data['response']:
                        return data['response']['games']
                    return []
        except Exception as e:
            print(f"Erreur lors de la récupération des jeux récents: {e}")
            return []

    async def get_owned_games(self, steam_id):
        """Récupère la liste des jeux possédés par l'utilisateur"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={self.steam_api_key}&steamid={steam_id}&format=json&include_appinfo=1"
                async with session.get(url) as response:
                    data = await response.json()
                    if 'response' in data and 'games' in data['response']:
                        return data['response']['games']
                    return []
        except Exception as e:
            print(f"Erreur lors de la récupération des jeux possédés: {e}")
            return []

    async def get_game_collector_info(self, steam_id):
        """Récupère les informations pour la section Game Collector"""
        owned_games = await self.get_owned_games(steam_id)
        
        if not owned_games:
            return None
        
        # Calcul du temps total de jeu
        total_playtime = sum(game.get('playtime_forever', 0) for game in owned_games)
        
        # Jeux les plus joués (top 3)
        top_games = sorted(owned_games, key=lambda x: x.get('playtime_forever', 0), reverse=True)[:3]
        
        # Jeux récemment ajoutés (derniers ajouts basés sur rtime_last_played)
        recent_additions = []
        for game in owned_games:
            if game.get('rtime_last_played', 0) > 0:
                recent_additions.append(game)
        recent_additions = sorted(recent_additions, key=lambda x: x.get('rtime_last_played', 0), reverse=True)[:3]
        
        # Jeux non joués
        unplayed_games = [game for game in owned_games if game.get('playtime_forever', 0) == 0]
        
        return {
            'total_games': len(owned_games),
            'total_playtime_hours': total_playtime // 60,  # Conversion en heures
            'top_games': top_games,
            'recent_additions': recent_additions,
            'unplayed_count': len(unplayed_games)
        }

    def is_valid_steam_id(self, steam_id):
        return steam_id.isdigit() and len(steam_id) == 17

    def extract_custom_url(self, url):
        patterns = [
            r'steamcommunity\.com/id/([^/]+)',
            r'steamcommunity\.com/profiles/(\d+)',
            r'^([a-zA-Z0-9_-]+)$'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return url

    @commands.command(name='setsteam', help='Definir votre utilisateur steam')
    async def set_steam(self, ctx, *, steam_info):
        user_id = str(ctx.author.id)
        steam_info = self.extract_custom_url(steam_info.strip())

        if self.is_valid_steam_id(steam_info):
            steam_id = steam_info
        else:
            steam_id = await self.get_steam_id_from_url(steam_info)
            if not steam_id:
                await ctx.send(embed=discord.Embed(title="❌ Erreur", description="Profil Steam non trouvé.", color=discord.Color.red()))
                return

        profile = await self.get_steam_profile(steam_id)
        if not profile:
            await ctx.send(embed=discord.Embed(title="❌ Erreur", description="Profil Steam privé ou inaccessible.", color=discord.Color.red()))
            return

        self.user_steam_data[user_id] = {'steam_id': steam_id, 'profile': profile}
        self.save_user_data()

        embed = discord.Embed(
            title="✅ Steam ID configuré",
            description=f"Profil Steam lié: **{profile['personaname']}**",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=profile['avatarmedium'])
        await ctx.send(embed=embed)

    @commands.command(name='steam', help='Affiche profile steam')
    async def steam_profile(self, ctx, member: discord.Member = None):
        target_user = member or ctx.author
        user_id = str(target_user.id)

        if user_id not in self.user_steam_data:
            await ctx.send(embed=discord.Embed(
                title="❌ Erreur",
                description="Ce membre n'a pas encore lié son compte Steam.",
                color=discord.Color.red()))
            return

        steam_id = self.user_steam_data[user_id]['steam_id']
        profile = await self.get_steam_profile(steam_id)
        recent_games = await self.get_recent_games(steam_id)
        collector_info = await self.get_game_collector_info(steam_id)

        embed = discord.Embed(
            title=f"🎮 {profile['personaname']}",
            url=profile['profileurl'],
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=profile['avatarfull'])

        status_map = {
            0: "🔴 Hors ligne", 1: "🟢 En ligne", 2: "🟡 Occupé", 3: "🔴 Absent",
            4: "🟡 Endormi", 5: "🔵 Cherche à jouer", 6: "🔵 Cherche à échanger"
        }
        embed.add_field(name="Statut", value=status_map.get(profile.get('personastate', 0), "❓ Inconnu"), inline=True)

        if 'timecreated' in profile:
            created = datetime.fromtimestamp(profile['timecreated']).strftime("%d/%m/%Y")
            embed.add_field(name="Compte créé", value=created, inline=True)

        if 'gameextrainfo' in profile:
            embed.add_field(name="Jeu actuel", value=profile['gameextrainfo'], inline=False)

        if recent_games:
            games_text = ""
            for game in recent_games[:5]:
                hours = game.get('playtime_2weeks', 0) / 60
                games_text += f"**{game['name']}** - {hours:.1f}h\n"
            embed.add_field(name="🎮 Jeux récents", value=games_text, inline=False)

        # Section Game Collector (remplace les achievements)
        if collector_info:
            collector_text = f"📚 **{collector_info['total_games']}** jeux possédés\n"
            collector_text += f"⏱️ **{collector_info['total_playtime_hours']:,}** heures de jeu\n"
            collector_text += f"🎯 **{collector_info['unplayed_count']}** jeux non joués\n"
            embed.add_field(name="🏆 Game Collector", value=collector_text, inline=False)

            # Top 3 des jeux les plus joués
            if collector_info['top_games']:
                top_text = ""
                for i, game in enumerate(collector_info['top_games'], 1):
                    hours = game.get('playtime_forever', 0) / 60
                    if hours > 0:
                        top_text += f"{i}. **{game['name']}** - {hours:.1f}h\n"
                if top_text:
                    embed.add_field(name="🥇 Jeux les plus joués", value=top_text, inline=False)

        embed.set_footer(text=f"Steam ID: {steam_id}")
        await ctx.send(embed=embed)

    async def fetch_charts_top10(self):
        url = "https://steamcharts.com/top"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                html = await resp.text()
        
        # Utilise html.parser au lieu de lxml pour éviter les dépendances
        soup = BeautifulSoup(html, 'html.parser')

        # Essaye plusieurs sélecteurs
        rows = soup.select("table.rankings tbody tr")
        if not rows:
            rows = soup.select("table.table-ranking tbody tr")
        if not rows:
            rows = soup.find_all("tr")[1:11]  # Ignore header

        top = []
        for row in rows[:10]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            name = cols[1].text.strip()
            current = cols[2].text.strip().replace(",", "")
            if current.isdigit():
                current = int(current)
            else:
                current = 0
            top.append({"name": name, "current_players": current})
        return top

    async def fetch_steamcharts_stats(self, appid: int):
        url = f"https://steamcharts.com/app/{appid}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        
        # Utilise html.parser au lieu de lxml
        soup = BeautifulSoup(html, 'html.parser')
        stats = {}
        
        try:
            # Cherche le titre du jeu
            title_elem = soup.find('h1')
            if title_elem:
                game_title = title_elem.text.strip()
                stats['game_title'] = game_title

            # Cherche les stats dans les spans avec des IDs spécifiques
            current_span = soup.find("span", {"class": "num"})
            if current_span:
                current_text = current_span.text.strip().replace(",", "")
                if current_text.isdigit():
                    stats['current_players'] = int(current_text)

            # Cherche le pic de 24h
            peak_spans = soup.find_all("span", {"class": "num"})
            if len(peak_spans) >= 2:
                peak_text = peak_spans[1].text.strip().replace(",", "")
                if peak_text.isdigit():
                    stats['peak_24h'] = int(peak_text)

            # Cherche le record absolu
            record_elem = soup.find("div", {"class": "app-stat"})
            if record_elem:
                record_span = record_elem.find("span", {"class": "num"})
                if record_span:
                    record_text = record_span.text.strip().replace(",", "")
                    if record_text.isdigit():
                        stats['all_time_peak'] = int(record_text)

            # Alternative: cherche dans les tableaux de stats
            if not stats.get('current_players'):
                stat_divs = soup.find_all("div", {"class": "app-stat"})
                for div in stat_divs:
                    span = div.find("span", {"class": "num"})
                    if span:
                        text = span.text.strip().replace(",", "")
                        if text.isdigit():
                            if 'current_players' not in stats:
                                stats['current_players'] = int(text)
                            elif 'peak_24h' not in stats:
                                stats['peak_24h'] = int(text)
                            elif 'all_time_peak' not in stats:
                                stats['all_time_peak'] = int(text)

        except Exception as e:
            print(f"Erreur scraping stats SteamCharts pour {appid} : {e}")
        
        return stats if stats else None

    async def search_steam_game(self, game_name):
        """Recherche un jeu Steam par nom et retourne son AppID"""
        try:
            async with aiohttp.ClientSession() as session:
                # Utilise l'API Steam pour chercher le jeu
                url = f"https://store.steampowered.com/api/storesearch/?term={game_name}&l=english&cc=US"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'items' in data and data['items']:
                            # Retourne le premier résultat
                            first_result = data['items'][0]
                            return {
                                'appid': first_result['id'],
                                'name': first_result['name'],
                                'type': first_result.get('type', 'game')
                            }
                    return None
        except Exception as e:
            print(f"Erreur lors de la recherche de jeu: {e}")
            return None

    async def fetch_steamcharts_record(self, appid: int):
        """Récupère spécifiquement le record de joueurs simultanés"""
        url = f"https://steamcharts.com/app/{appid}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        
        # Utilise html.parser au lieu de lxml
        soup = BeautifulSoup(html, 'html.parser')
        record_info = {}
        
        try:
            # Cherche le titre du jeu
            title_elem = soup.find('h1')
            if title_elem:
                record_info['game_title'] = title_elem.text.strip()

            # Cherche le record dans différents endroits possibles
            # Méthode 1: Cherche "All-time peak" ou "Record"
            peak_text_elements = soup.find_all(text=re.compile(r'All-time peak|Record|Peak'))
            for element in peak_text_elements:
                parent = element.parent
                if parent:
                    # Cherche le nombre dans le parent ou les éléments suivants
                    nums = parent.find_all("span", {"class": "num"})
                    if nums:
                        record_text = nums[0].text.strip().replace(",", "")
                        if record_text.isdigit():
                            record_info['all_time_peak'] = int(record_text)
                            break

            # Méthode 2: Cherche dans les statistiques principales
            if 'all_time_peak' not in record_info:
                stat_rows = soup.find_all("tr")
                for row in stat_rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label = cells[0].text.strip().lower()
                        if 'peak' in label or 'record' in label:
                            value_text = cells[1].text.strip().replace(",", "")
                            if value_text.isdigit():
                                record_info['all_time_peak'] = int(value_text)
                                break

            # Méthode 3: Prend le plus grand nombre trouvé (souvent le record)
            if 'all_time_peak' not in record_info:
                all_nums = soup.find_all("span", {"class": "num"})
                max_val = 0
                for num_span in all_nums:
                    num_text = num_span.text.strip().replace(",", "")
                    if num_text.isdigit():
                        val = int(num_text)
                        if val > max_val:
                            max_val = val
                if max_val > 0:
                    record_info['all_time_peak'] = max_val

        except Exception as e:
            print(f"Erreur scraping record SteamCharts pour {appid} : {e}")
        
        return record_info if record_info else None

    @commands.command(name='steamtop', help='Tops des jeux steam')
    async def steam_top(self, ctx):
        user_id = str(ctx.author.id)
        if user_id not in self.user_steam_data:
            return await ctx.send("❌ Tu dois d'abord lier ton compte Steam avec `.setsteam <id>` pour utiliser cette commande.")

        try:
            ranks = await self.fetch_charts_top10()
            if not ranks:
                return await ctx.send("❌ Impossible de récupérer le top des jeux SteamCharts pour le moment.")
            embed = discord.Embed(title="🔥 Top 10 des jeux SteamCharts", color=discord.Color.gold())
            for i, game in enumerate(ranks, 1):
                name = game.get("name", "Inconnu")
                curr = game.get("current_players", 0)
                embed.add_field(name=f"{i}. 🎮 {name}", value=f"👥 Joueurs actuels: `{curr:,}`", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Erreur lors de la récupération du top SteamCharts : {e}")

    @commands.command(name='steamstats', help='Statistiques détaillées d\'un jeu Steam')
    async def steam_stats(self, ctx, *, game_input=None):
        if not game_input:
            embed = discord.Embed(
                title="❓ Utilisation de .steamstats",
                description="Obtenez les statistiques détaillées d'un jeu Steam",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="📝 Syntaxe",
                value="`.steamstats <nom du jeu>`\n`.steamstats <appid>`",
                inline=False
            )
            embed.add_field(
                name="💡 Exemples",
                value="`.steamstats Counter-Strike 2`\n`.steamstats 730`\n`.steamstats Dota 2`",
                inline=False
            )
            embed.add_field(
                name="ℹ️ Info",
                value="• Vous pouvez utiliser le nom du jeu ou son AppID\n• La recherche fonctionne en anglais principalement",
                inline=False
            )
            return await ctx.send(embed=embed)

        try:
            # Vérifie si c'est un AppID (nombre) ou un nom de jeu
            if game_input.isdigit():
                appid = int(game_input)
                game_name = None
            else:
                # Recherche le jeu par nom
                search_result = await self.search_steam_game(game_input)
                if not search_result:
                    return await ctx.send(f"❌ Aucun jeu trouvé pour '{game_input}'. Essayez avec un nom plus précis ou l'AppID.")
                
                appid = search_result['appid']
                game_name = search_result['name']

            # Récupère les stats
            stats = await self.fetch_steamcharts_stats(appid)
            if not stats:
                return await ctx.send(f"❌ Aucune donnée SteamCharts trouvée pour {'le jeu' if game_name else f'l\'appid {appid}'}.")

            # Utilise le nom trouvé via la recherche ou celui de SteamCharts
            display_name = game_name or stats.get('game_title', f'Jeu AppID {appid}')
            
            embed = discord.Embed(
                title=f"📊 {display_name}",
                color=discord.Color.dark_purple()
            )
            
            if 'current_players' in stats:
                embed.add_field(name="👥 Joueurs actuels", value=f"`{stats['current_players']:,}`", inline=True)
            
            if 'peak_24h' in stats:
                embed.add_field(name="📈 Pic 24h", value=f"`{stats['peak_24h']:,}`", inline=True)
            
            if 'all_time_peak' in stats:
                embed.add_field(name="🏆 Record absolu", value=f"`{stats['all_time_peak']:,}`", inline=True)

            url = f"https://steamcharts.com/app/{appid}"
            embed.url = url
            embed.set_footer(text=f"AppID: {appid} | Source: steamcharts.com")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Erreur lors de la récupération des stats SteamCharts : {e}")

    @commands.command(name='steamrecord', help='Record de joueurs simultanés d\'un jeu Steam')
    async def steam_record(self, ctx, *, game_input=None):
        if not game_input:
            embed = discord.Embed(
                title="❓ Utilisation de .steamrecord",
                description="Obtenez le record de joueurs simultanés d'un jeu Steam",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="📝 Syntaxe",
                value="`.steamrecord <nom du jeu>`\n`.steamrecord <appid>`",
                inline=False
            )
            embed.add_field(
                name="💡 Exemples",
                value="`.steamrecord Counter-Strike 2`\n`.steamrecord 730`\n`.steamrecord Among Us`",
                inline=False
            )
            embed.add_field(
                name="ℹ️ Info",
                value="• Vous pouvez utiliser le nom du jeu ou son AppID\n• Affiche le record de tous les temps",
                inline=False
            )
            return await ctx.send(embed=embed)

        try:
            # Vérifie si c'est un AppID (nombre) ou un nom de jeu
            if game_input.isdigit():
                appid = int(game_input)
                game_name = None
            else:
                # Recherche le jeu par nom
                search_result = await self.search_steam_game(game_input)
                if not search_result:
                    return await ctx.send(f"❌ Aucun jeu trouvé pour '{game_input}'. Essayez avec un nom plus précis ou l'AppID.")
                
                appid = search_result['appid']
                game_name = search_result['name']

            # Récupère le record
            record_info = await self.fetch_steamcharts_record(appid)
            if not record_info:
                return await ctx.send(f"❌ Aucune donnée de record trouvée pour {'le jeu' if game_name else f'l\'appid {appid}'}.")

            # Utilise le nom trouvé via la recherche ou celui de SteamCharts
            display_name = game_name or record_info.get('game_title', f'Jeu AppID {appid}')
            record_count = record_info.get('all_time_peak', 0)

            embed = discord.Embed(
                title=f"🏆 Record de {display_name}",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="🎯 Joueurs simultanés (Record)",
                value=f"`{record_count:,}` joueurs",
                inline=False
            )

            # Ajoute une comparaison visuelle
            if record_count > 1000000:
                embed.add_field(name="💫 Niveau", value="🌟 LÉGENDAIRE (1M+)", inline=True)
            elif record_count > 500000:
                embed.add_field(name="💫 Niveau", value="🔥 ÉPIQUE (500K+)", inline=True)
            elif record_count > 100000:
                embed.add_field(name="💫 Niveau", value="⭐ POPULAIRE (100K+)", inline=True)
            elif record_count > 10000:
                embed.add_field(name="💫 Niveau", value="✨ CONNU (10K+)", inline=True)
            else:
                embed.add_field(name="💫 Niveau", value="🎮 NICHE (<10K)", inline=True)

            url = f"https://steamcharts.com/app/{appid}"
            embed.url = url
            embed.set_footer(text=f"AppID: {appid} | Source: steamcharts.com | Record de tous les temps")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Erreur lors de la récupération du record SteamCharts : {e}")

    @commands.command(name='steamhelp', help='Commandes steam')
    async def steam_help(self, ctx):
        embed = discord.Embed(title="🎮 Commandes Steam", color=discord.Color.blue())
        embed.add_field(name="`.setsteam <id|url>`", value="Lie ton compte Steam", inline=False)
        embed.add_field(name="`.steam`", value="Affiche ton profil Steam", inline=False)
        embed.add_field(name="`.steam @membre`", value="Affiche le Steam d'un autre", inline=False)
        embed.add_field(name="`.steamtop`", value="Top 10 jeux les plus joués (SteamCharts)", inline=False)
        embed.add_field(name="`.steamstats <jeu|appid>`", value="Stats détaillées d'un jeu Steam", inline=False)
        embed.add_field(name="`.steamrecord <jeu|appid>`", value="Record de joueurs simultanés d'un jeu", inline=False)
        embed.add_field(name="ℹ️ Notes", value="• Profil public requis\n• Game Collector affiche vos statistiques de collection\n• Vous pouvez utiliser le nom du jeu ou son AppID\n• La recherche fonctionne mieux en anglais", inline=False)
        embed.add_field(name="💡 Exemples", value="`.steamstats Counter-Strike 2`\n`.steamrecord 730`\n`.steamstats Among Us`", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Steam(bot))