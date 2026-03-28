import discord
from discord.ext import commands
import aiohttp
from datetime import datetime

# Import de la config (optionnel, pour d'autres clés futures)
try:
    import config
except ImportError:
    config = None


class Meteo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

        # URLs Open-Meteo (100% gratuit, aucune clé API requise)
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
        self.weather_url = "https://api.open-meteo.com/v1/forecast"

    async def cog_load(self):
        """Initialise la session HTTP"""
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Ferme la session HTTP"""
        if self.session:
            await self.session.close()

    def get_weather_emoji(self, wmo_code: int) -> str:
        """Retourne un emoji basé sur le code météo WMO d'Open-Meteo"""
        if wmo_code == 0:
            return "☀️"
        elif wmo_code in (1, 2):
            return "⛅"
        elif wmo_code == 3:
            return "☁️"
        elif wmo_code in (45, 48):
            return "🌫️"
        elif wmo_code in (51, 53, 55, 56, 57):
            return "🌦️"
        elif wmo_code in (61, 63, 65, 66, 67, 80, 81, 82):
            return "🌧️"
        elif wmo_code in (71, 73, 75, 77, 85, 86):
            return "❄️"
        elif wmo_code in (95, 96, 99):
            return "⛈️"
        else:
            return "🌤️"

    def wmo_to_description(self, wmo_code: int) -> str:
        """Convertit le code WMO en description française"""
        descriptions = {
            0: "Ciel dégagé",
            1: "Principalement dégagé",
            2: "Partiellement nuageux",
            3: "Couvert",
            45: "Brouillard",
            48: "Brouillard givrant",
            51: "Bruine légère",
            53: "Bruine modérée",
            55: "Bruine dense",
            56: "Bruine verglaçante légère",
            57: "Bruine verglaçante dense",
            61: "Pluie légère",
            63: "Pluie modérée",
            65: "Pluie forte",
            66: "Pluie verglaçante légère",
            67: "Pluie verglaçante forte",
            71: "Neige légère",
            73: "Neige modérée",
            75: "Neige forte",
            77: "Grains de neige",
            80: "Averses légères",
            81: "Averses modérées",
            82: "Averses violentes",
            85: "Averses de neige légères",
            86: "Averses de neige fortes",
            95: "Orage",
            96: "Orage avec grêle légère",
            99: "Orage avec forte grêle",
        }
        return descriptions.get(wmo_code, "Conditions inconnues")

    def get_wind_direction(self, degrees: float) -> str:
        """Convertit les degrés en direction cardinale"""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
        index = round(degrees / 22.5) % 16
        return directions[index]

    async def geocode_city(self, city: str):
        """Recherche les coordonnées d'une ville via Open-Meteo Geocoding"""
        try:
            params = {
                'name': city,
                'count': 1,
                'language': 'fr',
                'format': 'json'
            }
            async with self.session.get(self.geocoding_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get('results')
                    if results:
                        r = results[0]
                        # Construction du nom de ville affiché
                        parts = [r.get('name', city)]
                        if r.get('admin1'):
                            parts.append(r['admin1'])
                        if r.get('country'):
                            parts.append(r['country'])
                        display_name = ', '.join(parts)
                        return r['latitude'], r['longitude'], display_name
            return None, None, None
        except Exception as e:
            print(f"Erreur géocodage: {e}")
            return None, None, None

    async def get_open_meteo_weather(self, city: str):
        """Obtient les données météo actuelles depuis Open-Meteo"""
        lat, lon, display_name = await self.geocode_city(city)
        if lat is None:
            return None

        try:
            params = {
                'latitude': lat,
                'longitude': lon,
                'current': [
                    'temperature_2m',
                    'apparent_temperature',
                    'relative_humidity_2m',
                    'precipitation',
                    'weather_code',
                    'wind_speed_10m',
                    'wind_direction_10m',
                    'surface_pressure',
                    'uv_index',
                ],
                'wind_speed_unit': 'kmh',
                'timezone': 'auto',
                'forecast_days': 1
            }

            async with self.session.get(self.weather_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data.get('current', {})

                    wmo_code = current.get('weather_code', 0)

                    return {
                        'city': display_name,
                        'temperature': current.get('temperature_2m', 0),
                        'feels_like': current.get('apparent_temperature', 0),
                        'condition': self.wmo_to_description(wmo_code),
                        'wmo_code': wmo_code,
                        'humidity': current.get('relative_humidity_2m', 0),
                        'wind_speed': current.get('wind_speed_10m', 0),
                        'wind_direction': self.get_wind_direction(
                            current.get('wind_direction_10m', 0)
                        ),
                        'pressure': current.get('surface_pressure', 0),
                        'uv_index': current.get('uv_index', 'N/A'),
                        'precipitation': current.get('precipitation', 0),
                        'source': 'Open-Meteo'
                    }
            return None
        except Exception as e:
            print(f"Erreur Open-Meteo: {e}")
            return None

    @commands.command(name='meteo', aliases=['weather'])
    async def meteo_command(self, ctx, *, ville: str = None):
        """
        Affiche la météo pour une ville donnée : .meteo [ville]
        """
        if not ville:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Veuillez spécifier une ville.\nUsage: `.meteo Montreal`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Message de chargement
        loading_msg = await ctx.send("🔄 Recherche des données météo...")

        weather_data = await self.get_open_meteo_weather(ville)

        await loading_msg.delete()

        if not weather_data:
            embed = discord.Embed(
                title="❌ Erreur",
                description=(
                    f"Impossible de trouver les données météo pour **'{ville}'**.\n"
                    "Vérifiez l'orthographe ou essayez une ville différente."
                ),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Création de l'embed
        emoji = self.get_weather_emoji(weather_data['wmo_code'])

        embed = discord.Embed(
            title=f"{emoji} Météo — {weather_data['city']}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="🌡️ Température",
            value=f"**{weather_data['temperature']:.1f}°C**\nRessenti: {weather_data['feels_like']:.1f}°C",
            inline=True
        )

        embed.add_field(
            name="🌤️ Conditions",
            value=weather_data['condition'],
            inline=True
        )

        embed.add_field(
            name="💨 Vent",
            value=f"{weather_data['wind_speed']:.1f} km/h {weather_data['wind_direction']}",
            inline=True
        )

        embed.add_field(
            name="💧 Humidité",
            value=f"{weather_data['humidity']}%",
            inline=True
        )

        embed.add_field(
            name="📊 Pression",
            value=f"{weather_data['pressure']:.1f} hPa",
            inline=True
        )

        embed.add_field(
            name="🌧️ Précipitations",
            value=f"{weather_data['precipitation']} mm",
            inline=True
        )

        if weather_data['uv_index'] != 'N/A':
            embed.add_field(
                name="☀️ Index UV",
                value=str(weather_data['uv_index']),
                inline=True
            )

        embed.set_footer(text=f"Source: {weather_data['source']} • Données en temps réel")

        await ctx.send(embed=embed)

    @meteo_command.error
    async def meteo_error(self, ctx, error):
        """Gestion des erreurs pour la commande météo"""
        if isinstance(error, commands.CommandInvokeError):
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors de la récupération des données météo.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Meteo(bot))