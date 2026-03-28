# cogs/admin.py

import discord
from discord.ext import commands
from utils.permissions import require_admin
import os
import sys
from config import BOT_PREFIX, COLORS

class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    

    ########################
    ## shutdown, restart  ##
    ########################

    @commands.command(name="shutdown")
    @commands.is_owner()
    async def shutdown(self, ctx):
        """Éteint proprement le bot."""
        await ctx.send("🛑 Extinction en cours...")
        await self.bot.close()

    @commands.command(name="restart")
    @commands.is_owner()
    async def restart(self, ctx):
        """Redémarre le bot."""
        await ctx.send("🔁 Redémarrage en cours...")

        # Arrête le bot proprement
        await self.bot.close()

        # Redémarre le processus courant (équivalent à relancer `python bot.py`)
        os.execv(sys.executable, [sys.executable] + sys.argv)


    ########################
    ## Commande .setgame  ##
    ########################
    @commands.command(name='setgame')
    @require_admin()
    async def set_game(self, ctx, *, game_name: str = None):
        """Change ou supprime le statut 'joue à' du bot."""
            
        if game_name:
            game = discord.Game(game_name)
            await self.bot.change_presence(activity=game)
            embed = discord.Embed(
                title="🎮 Statut modifié",
                description=f"Nouveau statut: **{game_name}**",
                color=COLORS.get('success', discord.Color.green())
            )
        else:
            await self.bot.change_presence(activity=None)
            embed = discord.Embed(
                title="🎮 Statut retiré",
                description="Le bot n'affiche plus de jeu en cours.",
                color=COLORS.get('warning', discord.Color.orange())
            )
        await ctx.send(embed=embed)

    ########################
    ## Commande .purge    ##
    ########################
    @commands.command(name='purge')
    @require_admin()
    async def purge_messages(self, ctx, amount: int = None):
        """Supprime un nombre spécifié de messages."""
        
        # Vérification du paramètre
        if amount is None:
            await ctx.send(f"❌ Syntaxe : `{BOT_PREFIX}purge <nombre>`")
            return
        
        # Vérification des limites
        if amount <= 0:
            await ctx.send("❌ Le nombre de messages à supprimer doit être supérieur à 0!")
            return
        
        if amount > 100:
            await ctx.send("❌ Impossible de supprimer plus de 100 messages à la fois!")
            return
        
        try:
            # Supprime les messages (+ 1 pour inclure la commande elle-même)
            await ctx.channel.purge(limit=amount + 1)
            
        except discord.Forbidden:
            await ctx.send("❌ Je n'ai pas les permissions pour supprimer les messages dans ce canal!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Erreur lors de la suppression des messages: {e}")
        except Exception as e:
            await ctx.send(f"❌ Une erreur inattendue s'est produite: {e}")
            

    ########################
    ## Commande .setnick  ##
    ########################
    @commands.command(name='setnick')
    @require_admin()
    async def set_nick(self, ctx, *, nickname: str = None):
        """Change le pseudo du bot sur ce serveur."""
        
        try:
            # Récupère le membre bot sur ce serveur
            bot_member = ctx.guild.get_member(self.bot.user.id)
            
            if nickname:
                # Change le pseudo
                await bot_member.edit(nick=nickname)
                embed = discord.Embed(
                    title="🏷️ Pseudo modifié",
                    description=f"Nouveau pseudo: **{nickname}**",
                    color=COLORS.get('success', discord.Color.green())
                )
            else:
                # Remet le pseudo par défaut (nom d'utilisateur)
                await bot_member.edit(nick=None)
                embed = discord.Embed(
                    title="🏷️ Pseudo réinitialisé",
                    description=f"Le bot utilise maintenant son nom par défaut: **{self.bot.user.name}**",
                    color=COLORS.get('warning', discord.Color.orange())
                )
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ Je n'ai pas les permissions pour changer mon pseudo sur ce serveur!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Erreur lors du changement de pseudo: {e}")
        except Exception as e:
            await ctx.send(f"❌ Une erreur inattendue s'est produite: {e}")

########################
### GESTION DES COGS ###
########################

### GROUPE PRINCIPAL `.cogs`
    @commands.group(name="cogs", invoke_without_command=True)
    @require_admin()
    async def cogs_group(self, ctx):
        """Geré les modules (cogs)"""
            
        await ctx.send(
            f"📦 Utilisation :\n"
            f"`{BOT_PREFIX}cogs list` – Voir les cogs chargés\n"
            f"`{BOT_PREFIX}cogs reload <nom>` – Recharger un cog\n"
            f"`{BOT_PREFIX}cogs load <nom>` – Charger un cog\n"
            f"`{BOT_PREFIX}cogs reloadall` – Recharger tous les cogs"
        )

    ### Liste des cogs chargés
    @cogs_group.command(name="list")
    async def cogs_list(self, ctx):
            
        loaded = list(self.bot.extensions.keys())
        if loaded:
            msg = "\n".join(f"• `{ext}`" for ext in loaded)
            await ctx.send(f"📦 Cogs actuellement chargés :\n{msg}")
        else:
            await ctx.send("⚠️ Aucun cog chargé.")

    ### Charger un cog
    @cogs_group.command(name="load")
    async def cogs_load(self, ctx, extension: str = None):
            
        if not extension:
            await ctx.send(f"❌ Syntaxe : `{BOT_PREFIX}cogs load <nom>`")
            return
        try:
            await self.bot.load_extension(f"cogs.{extension}")
            await ctx.send(f"✅ Cog `{extension}` chargé avec succès.")
        except Exception as e:
            await ctx.send(f"❌ Erreur lors du chargement de `{extension}` : `{e}`")

    ### Recharger un seul cog
    @cogs_group.command(name="reload")
    async def cogs_reload(self, ctx, extension: str = None):
            
        if not extension:
            await ctx.send(f"❌ Syntaxe : `{BOT_PREFIX}cogs reload <nom>`")
            return
        try:
            await self.bot.reload_extension(f"cogs.{extension}")
            await ctx.send(f"♻️ Cog `{extension}` rechargé avec succès.")
        except Exception as e:
            await ctx.send(f"❌ Erreur lors du rechargement de `{extension}` : `{e}`")

    ### Recharger tous les cogs chargés
    @cogs_group.command(name="reloadall")
    async def cogs_reloadall(self, ctx):
            
        loaded = list(self.bot.extensions.keys())
        success, failed = [], []

        for ext in loaded:
            try:
                await self.bot.reload_extension(ext)
                success.append(ext)
            except Exception as e:
                failed.append(f"{ext} : {e}")

        msg = ""
        if success:
            msg += f"✅ Rechargés ({len(success)}) :\n" + "\n".join(f"• `{c}`" for c in success)
        if failed:
            msg += f"\n❌ Erreurs :\n" + "\n".join(f"• {f}" for f in failed)

        await ctx.send(msg or "⚠️ Aucun cog chargé.")
    

    ### Décharger un cog
    @cogs_group.command(name="unload")
    async def cogs_unload(self, ctx, extension: str = None):
        if not extension:
            await ctx.send(f"❌ Syntaxe : `{BOT_PREFIX}cogs unload <nom>`")
            return
        try:
            await self.bot.unload_extension(f"cogs.{extension}")
            await ctx.send(f"🗑️ Cog `{extension}` déchargé avec succès.")
        except Exception as e:
            await ctx.send(f"❌ Erreur lors du déchargement de `{extension}` : `{e}`")

# Fonction obligatoire pour charger le cog
async def setup(bot):
    await bot.add_cog(Admin(bot))

# Fonction pour décharger le cog (optionnel)
async def teardown(bot):
    await bot.remove_cog("Admin")