import discord
from discord.ext import commands
from config import BOT_PREFIX, COLORS
from utils.permissions import is_admin_member, is_user_member


class Help(commands.Cog):
    """Commande d'aide principale du bot."""

    def __init__(self, bot):
        self.bot = bot

    def _build_section_value(self, commands_list):
        return "\n".join(commands_list)

    async def _send_help_embed(self, ctx, embed: discord.Embed):
        """Envoie l'aide en privé, avec fallback si les MP sont fermés."""
        try:
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ Impossible d'envoyer le menu en privé. Vérifie que tes MP sont ouverts.")

    @commands.command(name="help")
    async def help_command(self, ctx, command_name: str = None):
        """Affiche l'aide principale du bot."""
        if command_name:
            command = self.bot.get_command(command_name)
            if command is None:
                await ctx.send(f"❌ Commande inconnue : `{command_name}`")
                return

            signature = f"{BOT_PREFIX}{command.qualified_name}"
            if command.signature:
                signature += f" {command.signature}"

            description = command.help or command.brief or "Aucune description disponible."
            aliases = ", ".join(f"`{alias}`" for alias in command.aliases) or "Aucun"

            embed = discord.Embed(
                title=f"📖 Aide — `{BOT_PREFIX}{command.qualified_name}`",
                color=COLORS.get("info", discord.Color.blue()),
            )
            embed.add_field(name="Syntaxe", value=f"`{signature}`", inline=False)
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Alias", value=aliases, inline=False)
            if self.bot.user:
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(text="PythonBot Help")
            await self._send_help_embed(ctx, embed)
            return

        is_admin = is_admin_member(ctx.author) or await self.bot.is_owner(ctx.author)
        is_user = is_user_member(ctx.author) or is_admin

        embed = discord.Embed(
            title="📖 Commandes disponibles",
            description=(
                f"Préfixe actuel : `{BOT_PREFIX}`\n"
                "Voici les commandes disponibles selon vos permissions."
            ),
            color=COLORS.get("info", discord.Color.blue()),
        )

        embed.add_field(
            name="🛡️ Administration",
            value=self._build_section_value(
                [
                    f"`{BOT_PREFIX}shutdown` — Éteint proprement le bot.",
                    f"`{BOT_PREFIX}restart` — Redémarre le bot.",
                    f"`{BOT_PREFIX}setgame <jeu>` — Change le statut du bot.",
                    f"`{BOT_PREFIX}setnick <pseudo>` — Change le pseudo du bot.",
                    f"`{BOT_PREFIX}purge <nombre>` — Supprime des messages.",
                    f"`{BOT_PREFIX}cogs` — Gère les modules (cogs).",
                    f"`{BOT_PREFIX}nslookup <domain> [record_type]` — Résolution DNS.",
                    f"`{BOT_PREFIX}ping <ip/domaine>` — Ping compact en 1 requête.",
                    f"`{BOT_PREFIX}nmap_help` — Aide des commandes réseau.",
                    f"`{BOT_PREFIX}freegames removechannel` — Retire le canal d'annonces.",
                    f"`{BOT_PREFIX}freegames setchannel [#canal]` — Définit le canal d'annonces.",
                    f"`{BOT_PREFIX}freegames channel` — Affiche le canal configuré.",
                    f"`{BOT_PREFIX}config_jellyfin <url> <api_key>` — Configuration Jellyfin.",
                    f"`{BOT_PREFIX}test_jellyfin` — Teste la connexion à Jellyfin.",
                ]
            ),
            inline=False,
        )

        embed.add_field(
            name="ℹ️ Informations",
            value=self._build_section_value(
                [
                    f"`{BOT_PREFIX}sysinfo` — Affiche les informations système complètes.",
                    f"`{BOT_PREFIX}botinfo` — Affiche uniquement les informations du bot.",
                    f"`{BOT_PREFIX}prefix` — Affiche le préfixe du bot.",
                    f"`{BOT_PREFIX}serverinfo` — Informations sur le serveur.",
                    f"`{BOT_PREFIX}whois [membre]` — Informations sur un utilisateur.",
                    f"`{BOT_PREFIX}geo` — Géolocalise une adresse IP.",
                    f"`{BOT_PREFIX}meteo [ville]` — Affiche la météo pour une ville donnée.",
                ]
            ),
            inline=False,
        )

        embed.add_field(
            name="🔹 QBittorrent",
            value=self._build_section_value(
                [
                    f"`{BOT_PREFIX}torrents [filtre]` — Affiche la liste des torrents.",
                    f"`{BOT_PREFIX}qbstatus` — Affiche le statut global de qBittorrent.",
                ]
            ),
            inline=False,
        )

        embed.add_field(
            name="🎮 Jeux",
            value=self._build_section_value(
                [
                    f"`{BOT_PREFIX}setsteam` — Definir votre utilisateur steam.",
                    f"`{BOT_PREFIX}steam` — Affiche profile steam.",
                    f"`{BOT_PREFIX}steamhelp` — Commandes steam.",
                    f"`{BOT_PREFIX}freegames` — Affiche les jeux gratuits Epic Games.",
                ]
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 TarkovBoss",
            value=self._build_section_value(
                [
                    f"`{BOT_PREFIX}boss` — Affiche les boss qui spawnt à 100% actuellement.",
                    f"`{BOT_PREFIX}pve` — Affiche les spawns de boss spécifiques au mode PVE.",
                    f"`{BOT_PREFIX}bosslist` — Liste tous les boss de Tarkov avec leurs cartes (PVE focus).",
                ]
            ),
            inline=False,
        )

        if is_user:
            embed.add_field(
                name="🖥️ Monitoring",
                value=self._build_section_value(
                    [
                        f"`{BOT_PREFIX}beszel` — Affiche le statut, la charge et l'uptime de tous les systèmes Beszel.",
                        f"`{BOT_PREFIX}uptime` — Affiche l'uptime de la machine locale style SSH Linux.",
                        f"`{BOT_PREFIX}system` — Infos système rapides: hostname, OS, CPU, RAM, swap, IP locales.",
                        f"`{BOT_PREFIX}network` — Affiche l'état des interfaces réseau.",
                        f"`{BOT_PREFIX}top [1-10]` — Affiche les processus les plus gourmands.",
                        f"`{BOT_PREFIX}health` — Affiche un résumé santé du serveur.",
                        f"`{BOT_PREFIX}status` — Résumé complet du serveur.",
                        f"`{BOT_PREFIX}temps` — Affiche la température CPU.",
                        f"`{BOT_PREFIX}disk` — Affiche l'utilisation des disques.",
                        f"`{BOT_PREFIX}services` — Affiche l'état des services systemd.",
                        f"`{BOT_PREFIX}docker` — Affiche les conteneurs Docker actifs.",
                        f"`{BOT_PREFIX}update` — Affiche les paquets APT à mettre à jour.",
                        f"`{BOT_PREFIX}journal <service> [lignes]` — Affiche les dernières lignes journalctl d'un service.",
                    ]
                ),
                inline=False,
            )

            embed.add_field(
                name="🎬 Médias",
                value=self._build_section_value(
                    [
                        f"`{BOT_PREFIX}jellyfin view` — Streams actifs sur Jellyfin.",
                        f"`{BOT_PREFIX}jellyfin stats <day|week|month>` — Stats Jellyfin.",
                        f"`{BOT_PREFIX}radarr` — Affiche les statistiques Radarr.",
                        f"`{BOT_PREFIX}sonarr` — Affiche les statistiques Sonarr.",
                        f"`{BOT_PREFIX}lastmovie [nombre]` — Affiche le dernier film ajouté.",
                        f"`{BOT_PREFIX}lastseries [nombre]` — Affiche la dernière série ajoutée.",
                    ]
                ),
                inline=False,
            )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Utilise {BOT_PREFIX}help <commande> pour plus de détails sur une commande spécifique")
        await self._send_help_embed(ctx, embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
