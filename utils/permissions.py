import discord
from discord.ext import commands


# Noms de rôles attendus sur le serveur
ADMIN_ROLE_NAME = "Administrateur"
USER_ROLE_NAME = "Utilisateur"


def member_has_role_by_name(member: discord.Member, role_name: str) -> bool:
    """Retourne True si le membre possède un rôle portant exactement ce nom."""
    if not member or not hasattr(member, "roles"):
        return False
    return any(role.name == role_name for role in member.roles)


def is_admin_member(member: discord.Member) -> bool:
    """Est-ce que le membre est Administrateur (via rôle explicite) ?"""
    return member_has_role_by_name(member, ADMIN_ROLE_NAME)


def is_user_member(member: discord.Member) -> bool:
    """Est-ce que le membre est Utilisateur (ou Administrateur) ?"""
    return member_has_role_by_name(member, USER_ROLE_NAME) or is_admin_member(member)


async def is_owner_or_admin(ctx: commands.Context) -> bool:
    """Autorise le propriétaire du bot ou un membre Administrateur."""
    if await ctx.bot.is_owner(ctx.author):
        return True
    return is_admin_member(ctx.author)


def require_admin():
    """Décorateur de commande: exige Proprio du bot OU rôle Administrateur."""
    async def predicate(ctx: commands.Context) -> bool:
        return await is_owner_or_admin(ctx)

    return commands.check(predicate)


def require_user():
    """Décorateur de commande: exige rôle Utilisateur (ou Administrateur ou Proprio)."""
    async def predicate(ctx: commands.Context) -> bool:
        return is_user_member(ctx.author) or await ctx.bot.is_owner(ctx.author)

    return commands.check(predicate)