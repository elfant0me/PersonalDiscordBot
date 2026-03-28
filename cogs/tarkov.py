# cogs/tarkov.py

import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime, timezone

class TarkovBoss(commands.Cog):
    """Cog pour afficher les boss Tarkov qui spawnt à 100%"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.tarkov.dev/graphql"
        
    @commands.command(name='boss', aliases=['bosses', 'spawn'])
    async def show_boss_spawns(self, ctx):
        """Affiche les boss qui spawnt à 100% actuellement"""
        
        loading_embed = discord.Embed(
            title="🔍 Recherche des boss spawns...",
            description="Récupération des données depuis l'API Tarkov...",
            color=0xFFD700
        )
        message = await ctx.send(embed=loading_embed)
        
        try:
            # Requête GraphQL simplifiée
            query = """
            query {
                maps {
                    name
                    bosses {
                        name
                        spawnChance
                        spawnLocations {
                            name
                        }
                    }
                }
            }
            """
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={"query": query},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status != 200:
                        await message.edit(embed=discord.Embed(
                            title="❌ Erreur API",
                            description="Impossible de récupérer les données de l'API Tarkov.",
                            color=0xFF0000
                        ))
                        return
                    
                    data = await response.json()
                    
                    if 'errors' in data:
                        # Si l'API GraphQL ne fonctionne pas, utiliser des données statiques
                        await self.show_static_boss_data(message)
                        return
                    
                    # Analyser les données pour trouver les boss à spawn élevé
                    high_spawn_bosses = []
                    
                    for map_data in data['data']['maps']:
                        if map_data.get('bosses'):
                            for boss in map_data['bosses']:
                                spawn_chance = boss.get('spawnChance', 0)
                                # Boss avec spawn >= 80% (proche de 100%)
                                if spawn_chance >= 0.8:
                                    locations = [loc['name'] for loc in boss.get('spawnLocations', [])]
                                    high_spawn_bosses.append({
                                        'name': boss['name'],
                                        'map': map_data['name'],
                                        'spawn_chance': spawn_chance * 100,
                                        'locations': locations[:2]  # Max 2 locations
                                    })
            
            # Créer l'embed de réponse
            if high_spawn_bosses:
                embed = discord.Embed(
                    title="🎯 Boss Tarkov PVE - Spawns Élevés (≥80%)",
                    description=f"**Mode PVE** - **{len(high_spawn_bosses)} boss** avec des chances de spawn élevées !",
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc)
                )
                
                # Grouper par map
                maps_data = {}
                for boss in high_spawn_bosses:
                    map_name = boss['map']
                    if map_name not in maps_data:
                        maps_data[map_name] = []
                    maps_data[map_name].append(boss)
                
                # Ajouter les champs par map
                for map_name, bosses in maps_data.items():
                    boss_info = []
                    for boss in bosses:
                        chance_emoji = "🎯" if boss['spawn_chance'] >= 95 else "🔥"
                        boss_line = f"{chance_emoji} **{boss['name']}** - {boss['spawn_chance']:.0f}%"
                        
                        if boss['locations']:
                            boss_line += f"\n   📍 {', '.join(boss['locations'])}"
                        
                        boss_info.append(boss_line)
                    
                    embed.add_field(
                        name=f"🗺️ {map_name}",
                        value="\n\n".join(boss_info),
                        inline=True
                    )
                
                embed.set_footer(text="🎮 Mode PVE - Données fournies par tarkov.dev")
                
            else:
                embed = discord.Embed(
                    title="😔 Aucun Boss à Spawn Élevé",
                    description="**Mode PVE** - Aucun boss avec un spawn ≥80% trouvé actuellement via l'API.\n\n"
                               "💡 Données PVE ",
                    color=0xFFA500,
                    timestamp=datetime.now(timezone.utc)
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            print(f"Erreur dans tarkov_boss: {e}")
            await self.show_static_boss_data(message)
    
    async def show_static_boss_data(self, message):
        """Affiche des données PVE si l'API ne fonctionne pas"""
        embed = discord.Embed(
            title="🎯 Boss Tarkov PVE - Spawns Élevés",
            description="**Mode PVE** - Boss avec spawns élevés (≥40%) :",
            color=0x00FF00,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Données PVE basées sur tarkovbot.eu et autres sources
        pve_data = {
            "Lighthouse": [
                "🎯 **Zryachiy** - 100% (Island Sniper)",
                "🔥 **Knight** - 39% (Water Treatment)",
                "🔥 **exUsec** - 40% (Various locations)"
            ],
            "Interchange": [
                "🎯 **Killa** - 49% (Mall, KIBA, Brutal)"
            ],
            "Streets of Tarkov": [
                "🎯 **Kaban** - 49% (Concordia)",
                "🎯 **Kaban Guard** - 100% (Sniper)"
            ],
            "Factory": [
                "🎯 **Tagilla** - 45% (Various locations)"
            ],
            "Reserve": [
                "🔥 **Glukhar** - 39% (K Buildings)",
                "🔥 **Raiders** - 40% (Various)"
            ],
            "Customs": [
                "🔥 **Reshala** - 39% (Dorms, Gas, Fortress)"
            ],
            "Woods": [
                "🔥 **Shturman** - 39% (Sawmill)"
            ],
            "Shoreline": [
                "🔥 **Sanitar** - 30% (Resort, Pier, Village)"
            ]
        }
        
        for map_name, bosses in pve_data.items():
            embed.add_field(
                name=f"🗺️ {map_name}",
                value="\n".join(bosses),
                inline=True
            )
        
        embed.set_footer(text="🎮 Mode PVE - Données basées sur tarkovbot.eu")
        await message.edit(embed=embed)
    
    @commands.command(name='pve', aliases=['pveboss'])
    async def pve_boss_spawns(self, ctx):
        """Affiche les spawns de boss spécifiques au mode PVE"""
        embed = discord.Embed(
            title="🎮 Boss Tarkov - Mode PVE",
            description="**Spawns de boss en mode PVE** :",
            color=0x00AA00,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Données PVE avec spawns élevés
        pve_spawns = [
            "🎯 **Zryachiy** - Lighthouse - **100%** (Island Sniper)",
            "🎯 **Kaban Guard** - Streets - **100%** (Sniper)",
            "🔥 **Killa** - Interchange - **49%** (Mall)",
            "🔥 **Kaban** - Streets - **49%** (Concordia)",
            "🔥 **Tagilla** - Factory - **45%** (Various)",
            "🔥 **exUsec** - Lighthouse - **40%** (Water Treatment)",
            "🔥 **Knight** - Lighthouse - **39%** (Goons)",
            "🔥 **Glukhar** - Reserve - **39%** (K Buildings)",
            "🔥 **Reshala** - Customs - **39%** (Dorms)",
            "🔥 **Shturman** - Woods - **39%** (Sawmill)",
            "🔥 **Sanitar** - Shoreline - **30%** (Resort)"
        ]
        
        embed.add_field(
            name="📊 Boss avec Spawns Élevés",
            value="\n".join(pve_spawns),
            inline=False
        )
        
        embed.set_footer(text="🎮 Données spécifiques au mode PVE")
        await ctx.send(embed=embed)
    @commands.command(name='bosslist', aliases=['bl'])
    async def boss_list(self, ctx):
        """Liste tous les boss de Tarkov avec leurs cartes (PVE focus)"""
        embed = discord.Embed(
            title="📋 Liste des Boss Tarkov (PVE)",
            description="**Mode PVE** - Tous les boss avec leurs spawns :",
            color=0x0099FF,
            timestamp=datetime.now(timezone.utc)
        )
        
        boss_data = {
            "🎯 **Boss Garantis/Très Élevés**": [
                "🎯 **Zryachiy** - Lighthouse (100%)",
                "🎯 **Kaban Guard** - Streets (100%)"
            ],
            "🔥 **Boss Fréquents (≥40%)**": [
                "🔥 **Killa** - Interchange (49%)",
                "🔥 **Kaban** - Streets (49%)",
                "🔥 **Tagilla** - Factory (45%)",
                "🔥 **exUsec** - Lighthouse (40%)"
            ],
            "⚡ **Boss Moyens (30-39%)**": [
                "⚡ **Knight** - Lighthouse (39%)",
                "⚡ **Glukhar** - Reserve (39%)",
                "⚡ **Reshala** - Customs (39%)",
                "⚡ **Shturman** - Woods (39%)",
                "⚡ **Sanitar** - Shoreline (30%)"
            ],
            "🌙 **Événements Spéciaux**": [
                "🌙 **Cultists** - Various maps (Night)",
                "🌙 **Raiders** - Labs/Reserve",
                "🌙 **Partisan** - Multiple maps (15%)"
            ]
        }
        
        for category, bosses in boss_data.items():
            embed.add_field(
                name=category,
                value="\n".join(bosses),
                inline=False
            )
        
        embed.set_footer(text="🎮 Mode PVE - Utilisez !boss ou !pve pour plus de détails")
        await ctx.send(embed=embed)

# Fonction pour setup le cog
async def setup(bot):
    await bot.add_cog(TarkovBoss(bot))