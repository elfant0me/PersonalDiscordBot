import discord
from discord.ext import commands
import aiohttp
import asyncio
import os
from typing import Optional
import config

class QBittorrent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.qb_url = getattr(config, "QBITTORRENT_URL", None) or os.getenv("QBITTORRENT_URL")
        self.username = getattr(config, "QBITTORRENT_USERNAME", None) or os.getenv("QBITTORRENT_USERNAME")
        self.password = getattr(config, "QBITTORRENT_PASSWORD", None) or os.getenv("QBITTORRENT_PASSWORD")
        self.cookie = None
        
    async def login(self):
        """Se connecter à qBittorrent API"""
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('username', self.username)
            data.add_field('password', self.password)
            
            async with session.post(f"{self.qb_url}/api/v2/auth/login", data=data) as resp:
                if resp.status == 200:
                    self.cookie = resp.cookies.get('SID')
                    return True
                return False
    
    async def get_torrents(self):
        """Récupérer la liste des torrents"""
        if not self.cookie:
            await self.login()
        
        headers = {'Cookie': f'SID={self.cookie.value}'}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.qb_url}/api/v2/torrents/info", headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    
    async def get_server_state(self):
        """Récupérer l'état du serveur"""
        if not self.cookie:
            await self.login()
        
        headers = {'Cookie': f'SID={self.cookie.value}'}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.qb_url}/api/v2/transfer/info", headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    
    def format_bytes(self, bytes_value):
        """Formater les bytes en unités lisibles"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    def get_state_emoji(self, state):
        """Retourner un emoji selon l'état"""
        states = {
            'downloading': '⬇️',
            'uploading': '⬆️',
            'pausedDL': '⏸️',
            'pausedUP': '⏸️',
            'stalledDL': '⏳',
            'stalledUP': '⏳',
            'checkingDL': '🔍',
            'checkingUP': '🔍',
            'queuedDL': '⏳',
            'queuedUP': '⏳',
            'completedDL': '✅',
            'error': '❌',
            'missingFiles': '⚠️',
            'allocating': '📝'
        }
        return states.get(state, '❓')
    
    @commands.command(name="torrents", help="Affiche la liste des torrents")
    async def torrents(self, ctx, filter: Optional[str] = None):
        """Affiche tous les torrents ou filtrés par état"""
        async with ctx.typing():
            torrents = await self.get_torrents()
            
            if not torrents:
                await ctx.send("❌ Impossible de récupérer les torrents. Vérifiez la connexion.")
                return
            
            # Filtrer si nécessaire
            if filter:
                torrents = [t for t in torrents if filter.lower() in t['state'].lower()]
            
            if not torrents:
                await ctx.send(f"Aucun torrent trouvé{f' avec le filtre: {filter}' if filter else ''}.")
                return
            
            # Créer l'embed
            embed = discord.Embed(
                title="📊 Torrents qBittorrent",
                color=discord.Color.blue(),
                description=f"Total: {len(torrents)} torrent(s)"
            )
            
            # Limiter à 10 torrents pour éviter de dépasser la limite
            for torrent in torrents[:10]:
                state = self.get_state_emoji(torrent['state'])
                progress = torrent['progress'] * 100
                
                info = (
                    f"{state} **{torrent['state']}** - {progress:.1f}%\n"
                    f"📥 {self.format_bytes(torrent['dlspeed'])}/s | "
                    f"📤 {self.format_bytes(torrent['upspeed'])}/s\n"
                    f"💾 {self.format_bytes(torrent['size'])} | "
                    f"Ratio: {torrent['ratio']:.2f}"
                )
                
                name = torrent['name'][:100]  # Limiter la longueur
                embed.add_field(name=name, value=info, inline=False)
            
            if len(torrents) > 10:
                embed.set_footer(text=f"Affichage de 10/{len(torrents)} torrents")
            
            await ctx.send(embed=embed)
    
    @commands.command(name="qbstatus", help="Affiche le statut global de qBittorrent")
    async def status(self, ctx):
        """Affiche les statistiques globales"""
        async with ctx.typing():
            state = await self.get_server_state()
            torrents = await self.get_torrents()
            
            if not state:
                await ctx.send("❌ Impossible de récupérer le statut.")
                return
            
            # Compter les torrents par état
            downloading = len([t for t in torrents if 'downloading' in t['state'].lower()])
            seeding = len([t for t in torrents if 'uploading' in t['state'].lower()])
            paused = len([t for t in torrents if 'paused' in t['state'].lower()])
            
            embed = discord.Embed(
                title="🖥️ Statut qBittorrent",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Torrents",
                value=f"Total: {len(torrents)}\n⬇️ Téléchargement: {downloading}\n⬆️ Seed: {seeding}\n⏸️ Pause: {paused}",
                inline=True
            )
            
            embed.add_field(
                name="🌐 Vitesses",
                value=f"📥 Download: {self.format_bytes(state['dl_info_speed'])}/s\n📤 Upload: {self.format_bytes(state['up_info_speed'])}/s",
                inline=True
            )
            
            embed.add_field(
                name="📦 Données",
                value=f"⬇️ Total DL: {self.format_bytes(state['dl_info_data'])}\n⬆️ Total UP: {self.format_bytes(state['up_info_data'])}",
                inline=True
            )
            
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(QBittorrent(bot))
