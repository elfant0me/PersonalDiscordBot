# cogs/serverinfo.py

import discord
from discord.ext import commands
from datetime import datetime
from config import COLORS, MESSAGES, BOT_PREFIX

class Serverinfo(commands.Cog):
    """Commandes d'information du serveur et du bot"""
    
    def __init__(self, bot):
        self.bot = bot

    # Affiche les informations sur le serveur
    @commands.command()
    async def serverinfo(self, ctx):
        """Informations sur le serveur"""
        guild = ctx.guild
        
        embed = discord.Embed(
            title=f"📊 Informations sur {guild.name}",
            color=COLORS['info'],
            timestamp=datetime.now()
        )
        
        try:
            owner = guild.owner.mention if guild.owner else f"<@{guild.owner_id}>"
        except:
            owner = "Inconnu"
        
        embed.add_field(name="👑 Propriétaire", value=owner, inline=True)
        embed.add_field(name="📅 Créé le", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="👥 Membres", value=f"{guild.member_count}", inline=True)
        embed.add_field(name="💬 Canaux", value=f"{len(guild.text_channels)} texte, {len(guild.voice_channels)} vocal", inline=True)
        embed.add_field(name="🏷️ Rôles", value=f"{len(guild.roles) - 1}", inline=True)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"ID: {guild.id}")
        
        await ctx.send(embed=embed)

    # Affiche les informations d'un utilisateur
    @commands.command(aliases=['userinfo', 'ui'])
    async def whois(self, ctx, member: discord.Member = None):
        """Informations sur un utilisateur"""
        if member is None:
            member = ctx.author
        
        # Création de l'embed principal
        embed = discord.Embed(
            title=f"👤 {member.display_name}",
            color=member.color if member.color != discord.Color.default() else COLORS['info'],
            timestamp=datetime.now()
        )
        
        # Avatar de l'utilisateur
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Informations de base
        embed.add_field(
            name="📅 Rejoint le serveur", 
            value=member.joined_at.strftime("%d/%m/%Y à %H:%M") if member.joined_at else "Inconnu", 
            inline=True
        )
        embed.add_field(
            name="📅 Compte créé le", 
            value=member.created_at.strftime("%d/%m/%Y à %H:%M"), 
            inline=True
        )
        
        # Statut
        status_emoji = {
            'online': '🟢',
            'idle': '🟡', 
            'dnd': '🔴',
            'offline': '⚫'
        }
        embed.add_field(
            name="📱 Statut", 
            value=f"{status_emoji.get(str(member.status), '⚫')} {str(member.status).title()}", 
            inline=True
        )
        
        # Rôles (excluant @everyone)
        roles = [role.mention for role in member.roles[1:]]  # [1:] pour exclure @everyone
        if roles:
            # Limiter l'affichage si trop de rôles
            if len(roles) > 10:
                roles_display = ", ".join(roles[:10]) + f"\n... et {len(roles) - 10} autres"
            else:
                roles_display = ", ".join(roles)
            embed.add_field(
                name=f"🏷️ Rôles [{len(roles)}]", 
                value=roles_display, 
                inline=False
            )
        else:
            embed.add_field(name="🏷️ Rôles", value="Aucun rôle", inline=False)
        
        # Permissions clés
        key_permissions = []
        perms = member.guild_permissions
        
        # Liste des permissions importantes à vérifier
        important_perms = {
            'administrator': '🔧 Administrateur',
            'manage_guild': '⚙️ Gérer le serveur',
            'manage_roles': '🎭 Gérer les rôles',
            'manage_channels': '📝 Gérer les canaux',
            'manage_messages': '💬 Gérer les messages',
            'manage_webhooks': '🔗 Gérer les webhooks',
            'manage_nicknames': '📝 Gérer les pseudos',
            'manage_emojis': '😀 Gérer les emojis',
            'kick_members': '👢 Expulser des membres',
            'ban_members': '🔨 Bannir des membres',
            'mention_everyone': '📢 Mentionner @everyone',
            'mute_members': '🔇 Rendre muet',
            'deafen_members': '🔇 Rendre sourd',
            'move_members': '🔄 Déplacer des membres'
        }
        
        for perm, display_name in important_perms.items():
            if getattr(perms, perm, False):
                key_permissions.append(display_name)
        
        if key_permissions:
            if len(key_permissions) > 8:
                perms_display = ", ".join(key_permissions[:8]) + f"\n... et {len(key_permissions) - 8} autres"
            else:
                perms_display = ", ".join(key_permissions)
            embed.add_field(
                name="🔑 Permissions clés", 
                value=perms_display, 
                inline=False
            )
        else:
            embed.add_field(name="🔑 Permissions clés", value="Aucune permission spéciale", inline=False)
        
        # Informations supplémentaires
        if member.premium_since:
            embed.add_field(
                name="💎 Boost depuis", 
                value=member.premium_since.strftime("%d/%m/%Y"), 
                inline=True
            )
        
        # Reconnaissance spéciale
        acknowledgments = []
        if member.id == ctx.guild.owner_id:
            acknowledgments.append("👑 Propriétaire du serveur")
        if member.bot:
            acknowledgments.append("🤖 Bot")
        if member.premium_since:
            acknowledgments.append("💎 Booster du serveur")
        
        if acknowledgments:
            embed.add_field(
                name="🏆 Reconnaissance", 
                value="\n".join(acknowledgments), 
                inline=False
            )
        
        # Footer avec l'ID
        embed.set_footer(text=f"ID: {member.id}")
        
        await ctx.send(embed=embed)

# Fonction pour charger le cog
async def setup(bot):
    if not hasattr(bot, 'start_time'):
        bot.start_time = datetime.now()
    
    await bot.add_cog(Serverinfo(bot))