import discord
from discord.ext import commands
import aiohttp
import ipaddress
import json

class Geolocation(commands.Cog):
    """Cog pour la géolocalisation d'adresses IP"""
    
    def __init__(self, bot):
        self.bot = bot
        self.session = None
    
    async def cog_load(self):
        """Initialise la session HTTP lors du chargement du cog"""
        self.session = aiohttp.ClientSession()
    
    async def cog_unload(self):
        """Ferme la session HTTP lors du déchargement du cog"""
        if self.session:
            await self.session.close()
    
    def is_valid_ip(self, ip_string):
        """Vérifie si l'adresse IP est valide"""
        try:
            ipaddress.ip_address(ip_string)
            return True
        except ValueError:
            return False
    
    def is_private_ip(self, ip_string):
        """Vérifie si l'adresse IP est privée"""
        try:
            ip = ipaddress.ip_address(ip_string)
            return ip.is_private
        except ValueError:
            return False
    
    async def get_ip_info(self, ip):
        """Récupère les informations de géolocalisation d'une IP"""
        # Utilisation de l'API gratuite ip-api.com
        url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return None
        except Exception as e:
            print(f"Erreur lors de la requête API: {e}")
            return None
    
    def create_embed(self, ip_info, ip):
        """Crée un embed Discord avec les informations de géolocalisation"""
        if not ip_info or ip_info.get('status') == 'fail':
            embed = discord.Embed(
                title="❌ Erreur de géolocalisation",
                description=f"Impossible de géolocaliser l'IP: `{ip}`",
                color=discord.Color.red()
            )
            if ip_info and ip_info.get('message'):
                embed.add_field(name="Raison", value=ip_info['message'], inline=False)
            return embed
        
        # Création de l'embed avec les informations
        embed = discord.Embed(
            title="🌍 Géolocalisation IP",
            description=f"Informations pour l'adresse IP: `{ip}`",
            color=discord.Color.blue()
        )
        
        # Informations géographiques
        location_parts = []
        if ip_info.get('city'):
            location_parts.append(ip_info['city'])
        if ip_info.get('regionName'):
            location_parts.append(ip_info['regionName'])
        if ip_info.get('country'):
            location_parts.append(ip_info['country'])
        
        location = ", ".join(location_parts) if location_parts else "Non disponible"
        embed.add_field(name="📍 Localisation", value=location, inline=False)
        
        # Code pays et région
        if ip_info.get('countryCode'):
            embed.add_field(name="🏳️ Code pays", value=ip_info['countryCode'], inline=True)
        
        if ip_info.get('zip'):
            embed.add_field(name="📮 Code postal", value=ip_info['zip'], inline=True)
        
        # Coordonnées GPS
        if ip_info.get('lat') and ip_info.get('lon'):
            coordinates = f"{ip_info['lat']}, {ip_info['lon']}"
            embed.add_field(name="🗺️ Coordonnées", value=coordinates, inline=False)
        
        # Fuseau horaire
        if ip_info.get('timezone'):
            embed.add_field(name="🕐 Fuseau horaire", value=ip_info['timezone'], inline=True)
        
        # Informations réseau
        if ip_info.get('isp'):
            embed.add_field(name="🌐 Fournisseur (ISP)", value=ip_info['isp'], inline=False)
        
        if ip_info.get('org'):
            embed.add_field(name="🏢 Organisation", value=ip_info['org'], inline=False)
        
        if ip_info.get('as'):
            embed.add_field(name="🔢 AS Number", value=ip_info['as'], inline=True)
        
        # Footer avec avertissement
        embed.set_footer(text="⚠️ Ces informations sont approximatives et peuvent ne pas être exactes")
        
        return embed
    
    @commands.command(name='geo', aliases=['geoip', 'locate'])
    async def geolocate_ip(self, ctx, ip: str = None):
        """
        Géolocalise une adresse IP
        """
        if not ip:
            embed = discord.Embed(
                title="❓ Usage de la commande",
                description="Veuillez fournir une adresse IP à géolocaliser.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Utilisation", 
                value="`.geo <adresse_ip>`", 
                inline=False
            )
            embed.add_field(
                name="Exemple", 
                value="`.geo 8.8.8.8`", 
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Vérification de la validité de l'IP
        if not self.is_valid_ip(ip):
            embed = discord.Embed(
                title="❌ Adresse IP invalide",
                description=f"`{ip}` n'est pas une adresse IP valide.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Vérification si l'IP est privée
        if self.is_private_ip(ip):
            embed = discord.Embed(
                title="⚠️ Adresse IP privée",
                description=f"`{ip}` est une adresse IP privée. La géolocalisation n'est pas possible pour les adresses privées.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Adresses privées", 
                value="• 10.0.0.0/8\n• 172.16.0.0/12\n• 192.168.0.0/16\n• 127.0.0.0/8 (localhost)", 
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Message de chargement
        loading_embed = discord.Embed(
            title="🔍 Géolocalisation en cours...",
            description=f"Recherche des informations pour `{ip}`",
            color=discord.Color.yellow()
        )
        message = await ctx.send(embed=loading_embed)
        
        # Récupération des informations
        ip_info = await self.get_ip_info(ip)
        
        # Création et envoi de l'embed final
        final_embed = self.create_embed(ip_info, ip)
        await message.edit(embed=final_embed)
    
    @geolocate_ip.error
    async def geo_error(self, ctx, error):
        """Gestion des erreurs de la commande geo"""
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❓ Argument manquant",
                description="Veuillez fournir une adresse IP à géolocaliser.",
                color=discord.Color.red()
            )
            embed.add_field(name="Usage", value="`.geo <adresse_ip>`", inline=False)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur inattendue s'est produite.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            print(f"Erreur dans la commande geo: {error}")

# Fonction pour ajouter le cog au bot
async def setup(bot):
    await bot.add_cog(Geolocation(bot))

# Fonction pour retirer le cog du bot (optionnel)
async def teardown(bot):
    await bot.remove_cog("Geolocation")