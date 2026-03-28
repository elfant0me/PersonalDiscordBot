# cogs/help.py

import discord
from discord.ext import commands
from config import BOT_PREFIX, COLORS
from utils.permissions import is_admin_member


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def has_admin_role(self, member):
        """Utilise le rôle centralisé 'Administrateur'."""
        return is_admin_member(member)

    def get_admin_commands(self):
        """Récupère toutes les commandes des cogs Admin, nmap, certaines de Movies et EpicGames"""
        admin_commands = []
        
        # Commandes du cog Admin
        admin_cog = self.bot.get_cog("Admin")
        if admin_cog:
            for cmd in admin_cog.get_commands():
                if not cmd.hidden:
                    admin_commands.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
        
        # Commandes du cog nmap
        nmap_cog = self.bot.get_cog("nmap")
        if nmap_cog:
            for cmd in nmap_cog.get_commands():
                if not cmd.hidden:
                    admin_commands.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
        
        # Commandes spécifiques du cog Movies (config et test Jellyfin)
        movies_cog = self.bot.get_cog("Movies")
        if movies_cog:
            admin_movie_commands = ["config_jellyfin", "test_jellyfin"]
            for cmd in movies_cog.get_commands():
                if not cmd.hidden and cmd.name in admin_movie_commands:
                    admin_commands.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
        
        # Commandes spécifiques du cog EpicGames (gestion des canaux)
        epicgames_cog = self.bot.get_cog("EpicGames")
        if epicgames_cog:
            admin_epicgames_commands = ["setchannel", "removechannel", "channel"]
            freegames_group = epicgames_cog.freegames
            if freegames_group:
                for cmd in freegames_group.commands:
                    if not cmd.hidden and cmd.name in admin_epicgames_commands:
                        admin_commands.append(f"`{BOT_PREFIX}freegames {cmd.name}` — {cmd.help or 'Aucune description'}")
        
        return admin_commands

    def get_botinfo_commands(self):
        """Récupère les commandes des cogs Botinfo, Serverinfo et speedtest du cog Movies"""
        botinfo_commands = []
        botinfo_cogs = ["Botinfo", "Serverinfo"]
        
        for cog_name in botinfo_cogs:
            cog = self.bot.get_cog(cog_name)
            if cog:
                for cmd in cog.get_commands():
                    if not cmd.hidden:
                        botinfo_commands.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
        
        # Ajouter la commande speedtest du cog Movies
        movies_cog = self.bot.get_cog("Movies")
        if movies_cog:
            for cmd in movies_cog.get_commands():
                if not cmd.hidden and cmd.name == "speedtest":
                    botinfo_commands.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
        
        return botinfo_commands

    def get_games_commands(self):
        """Récupère les commandes des cogs Steam, EpicGames et Assetto"""
        games_commands = []
        games_cogs = ["Steam", "EpicGames", "Assetto"]
        
        for cog_name in games_cogs:
            cog = self.bot.get_cog(cog_name)
            if cog:
                for cmd in cog.get_commands():
                    if not cmd.hidden:
                        games_commands.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
        
        return games_commands

    def get_autres_commands(self):
        """Récupère les commandes des cogs Geolocation, Meteo, Gemini"""
        autres_commands = []
        autres_cogs = ["Geolocation", "Meteo", "Gemini"]
        
        for cog_name in autres_cogs:
            cog = self.bot.get_cog(cog_name)
            if cog:
                for cmd in cog.get_commands():
                    if not cmd.hidden:
                        autres_commands.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
        
        return autres_commands

    @commands.command(name="help", aliases=["aide", "h"])
    async def help_command(self, ctx, *, command_name=None):
        """Affiche la liste des commandes du bot, regroupées par catégorie (cog)."""
        
        # Si une commande spécifique est demandée
        if command_name:
            cmd = self.bot.get_command(command_name)
            if cmd:
                embed = discord.Embed(
                    title=f"📖 Aide pour `{BOT_PREFIX}{cmd.qualified_name}`",
                    description=cmd.help or "Aucune description disponible",
                    color=COLORS.get("info", discord.Color.blue())
                )
                
                # Ajouter les alias si ils existent
                if cmd.aliases:
                    embed.add_field(
                        name="Alias",
                        value=", ".join([f"`{alias}`" for alias in cmd.aliases]),
                        inline=False
                    )
                
                # Ajouter l'usage si disponible
                if cmd.usage:
                    embed.add_field(
                        name="Usage",
                        value=f"`{BOT_PREFIX}{cmd.qualified_name} {cmd.usage}`",
                        inline=False
                    )
                
                await ctx.author.send(embed=embed)
                return
            else:
                embed = discord.Embed(
                    title="❌ Commande introuvable",
                    description=f"La commande `{command_name}` n'existe pas.",
                    color=COLORS.get("error", discord.Color.red())
                )
                await ctx.author.send(embed=embed)
                return

        # Affichage général des commandes
        embed = discord.Embed(
            title="📖 Aide du bot",
            description=f"Préfixe : `{BOT_PREFIX}`\n",
            color=COLORS.get("info", discord.Color.blue())
        )
        
        # Vérifier si l'utilisateur a les permissions admin (inclut le propriétaire)
        is_owner = await self.bot.is_owner(ctx.author)
        is_admin = self.has_admin_role(ctx.author) or is_owner
        
        # Section Administration (Admin + nmap combinés)
        if is_admin:
            admin_commands = self.get_admin_commands()
            if admin_commands:
                embed.add_field(
                    name="🛡️ Administration",
                    value="\n".join(admin_commands),
                    inline=False
                )
        
        # Section BotInfo (regroupement Botinfo + Serverinfo + Homebox)
        botinfo_commands = self.get_botinfo_commands()
        if botinfo_commands:
            embed.add_field(
                name="🤖 Informations Bot & Serveur",
                value="\n".join(botinfo_commands),
                inline=False
            )
        
        # Section Games (regroupement Steam, EpicGames, Assetto)
        games_commands = self.get_games_commands()
        if games_commands:
            embed.add_field(
                name="🎮 Jeux",
                value="\n".join(games_commands),
                inline=False
            )
        
        # Cogs à exclure de l'affichage normal
        excluded_cogs = ["Help", "Admin", "nmap", "Botinfo", "Serverinfo", "Geolocation", "Meteo", "Gemini", "Steam", "EpicGames", "Assetto"]
        
        # Trier les autres cogs par ordre alphabétique
        sorted_cogs = sorted([
            (cog_name, cog) for cog_name, cog in self.bot.cogs.items() 
            if cog_name not in excluded_cogs
        ])
        
        for cog_name, cog in sorted_cogs:
            cmds = []
            for cmd in cog.get_commands():
                if not cmd.hidden:
                    # Pour le cog Movies, exclure les commandes déjà dans Administration et Informations
                    if cog_name == "Movies" and cmd.name in ["config_jellyfin", "test_jellyfin", "speedtest"]:
                        continue
                    cmds.append(f"`{BOT_PREFIX}{cmd.qualified_name}` — {cmd.help or 'Aucune description'}")
            
            if cmds:
                # Définir les icônes spécifiques pour certains cogs
                icon = "🔹"  # Icône par défaut
                if cog_name == "Fun":
                    icon = "🎲"
                elif cog_name == "Movies":
                    icon = "🎬"
                elif cog_name == "Reminder":
                    icon = "⏰"
                elif cog_name == "TarkovBoss":
                    icon = "🎯"
                
                embed.add_field(
                    name=f"{icon} {cog_name}",
                    value="\n".join(cmds),
                    inline=False
                )
        
        # Section Autres (regroupement Geolocation, Meteo, Gemini)
        autres_commands = self.get_autres_commands()
        if autres_commands:
            embed.add_field(
                name="🔧 Autres",
                value="\n".join(autres_commands),
                inline=False
            )

        # Commandes sans cog (non catégorisées)
        uncategorized = [
            f"`{BOT_PREFIX}{cmd.name}` — {cmd.help or 'Aucune description'}"
            for cmd in self.bot.commands
            if cmd.cog is None and not cmd.hidden
        ]
        if uncategorized:
            embed.add_field(
                name="🔹 Autres commandes",
                value="\n".join(uncategorized),
                inline=False
            )

        embed.set_footer(text=f"Utilise {BOT_PREFIX}help <commande> pour plus de détails sur une commande spécifique")
        
        try:
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            # Si l'utilisateur a bloqué les MP, envoyer dans le canal
            await ctx.send("❌ Je ne peux pas t'envoyer de message privé. Voici l'aide :")
            await ctx.send(embed=embed)


# Fonction obligatoire pour charger le cog
async def setup(bot):
    await bot.add_cog(Help(bot))