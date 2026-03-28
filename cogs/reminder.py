# cogs/reminder.py

import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta
import asyncio
import re

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders_file = 'data/reminders.json'
        self.reminders = self.load_reminders()
        self.check_reminders.start()
        
        # Créer le dossier data s'il n'existe pas
        if not os.path.exists('data'):
            os.makedirs('data')
    
    def load_reminders(self):
        """Charge les rappels depuis le fichier JSON"""
        try:
            if os.path.exists(self.reminders_file):
                with open(self.reminders_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Erreur lors du chargement des rappels: {e}")
            return {}
    
    def save_reminders(self):
        """Sauvegarde les rappels dans le fichier JSON"""
        try:
            with open(self.reminders_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des rappels: {e}")
    
    def parse_datetime(self, date_str, time_str):
        """Parse une date et une heure en format datetime"""
        try:
            # Formats acceptés pour la date: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
            date_formats = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']
            parsed_date = None
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            
            if not parsed_date:
                return None
            
            # Formats acceptés pour l'heure: HH:MM, HH.MM, HHMM
            time_formats = ['%H:%M', '%H.%M', '%H%M']
            parsed_time = None
            
            for fmt in time_formats:
                try:
                    parsed_time = datetime.strptime(time_str, fmt).time()
                    break
                except ValueError:
                    continue
            
            if not parsed_time:
                return None
            
            return datetime.combine(parsed_date, parsed_time)
        
        except Exception:
            return None
    
    # Commande d'aide générale pour les rappels
    @commands.command(name='helpreminder', aliases=['reminderhelp', 'rhelp'])
    async def help_reminder(self, ctx):
        """Affiche l'aide complète pour toutes les commandes de rappel"""
        embed = discord.Embed(
            title="🔔 Aide - Système de Rappels",
            description="Voici toutes les commandes disponibles pour gérer vos rappels :",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📅 `.setreminder` (ou `.sr`)",
            value="Crée un rappel à une date/heure précise\n"
                  "**Usage:** `.setreminder DD/MM/YYYY HH:MM [dm/#channel] message`\n"
                  "**Exemple:** `.setreminder 25/12/2024 15:30 #general Joyeux Noël!`",
            inline=False
        )
        
        embed.add_field(
            name="⏰ `.remindme` (ou `.rm`)",
            value="Crée un rappel dans X temps\n"
                  "**Usage:** `.remindme durée message`\n"
                  "**Formats:** s=secondes, m=minutes, h=heures, d=jours\n"
                  "**Exemples:** `.remindme 30m Pause!` ou `.remindme 2h30m Réunion`",
            inline=False
        )
        
        embed.add_field(
            name="📋 `.myreminders`",
            value="Affiche tous vos rappels actifs\n"
                  "**Alias:** `.reminders`, `.listreminders`",
            inline=False
        )
        
        embed.add_field(
            name="🗑️ `.deletereminder`",
            value="Supprime un rappel par son ID\n"
                  "**Usage:** `.deletereminder ID`\n"
                  "**Alias:** `.delreminder`, `.removereminder`",
            inline=False
        )
        
        embed.set_footer(text="Tapez une commande sans paramètres pour voir son aide spécifique")
        await ctx.send(embed=embed)
    
    @commands.command(name='setreminder', aliases=['sr'])
    async def set_reminder(self, ctx, date: str = None, time: str = None, destination: str = None, *, message: str = None):
        """
        DD/MM/YYYY HH:MM [#channel/dm] message
        """
        # Si aucun paramètre n'est fourni, afficher l'aide
        if not date or not time:
            embed = discord.Embed(
                title="📅 Aide - Créer un rappel à date fixe",
                description="Cette commande vous permet de créer un rappel pour une date et heure précise.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="💡 Syntaxe",
                value="`.setreminder DD/MM/YYYY HH:MM [destination] message`\n"
                      "**Alias:** `.sr`",
                inline=False
            )
            embed.add_field(
                name="📝 Formats acceptés",
                value="**Date:** DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY\n"
                      "**Heure:** HH:MM, HH.MM, HHMM",
                inline=False
            )
            embed.add_field(
                name="📍 Destinations",
                value="• `dm` = Message privé\n"
                      "• `#channel` = Channel spécifique\n"
                      "• *Rien* = Channel actuel (par défaut)",
                inline=False
            )
            embed.add_field(
                name="✨ Exemples",
                value="• `.setreminder 25/12/2024 15:30 Joyeux Noël!`\n"
                      "• `.sr 01-01-2025 00.00 dm Bonne année!`\n"
                      "• `.setreminder 15.03.2024 14:30 #general Réunion`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Parser la destination et le message (même logique que remindme)
        dest_type = "current"
        dest_id = ctx.channel.id
        
        if destination:
            if destination.lower() == "dm":
                dest_type = "dm"
                dest_id = None
            elif destination.startswith("#"):
                channel_name = destination[1:]
                found_channel = discord.utils.get(ctx.guild.channels, name=channel_name)
                if found_channel:
                    dest_type = "channel"
                    dest_id = found_channel.id
                else:
                    embed = discord.Embed(
                        title="❌ Channel introuvable",
                        description=f"Le channel `{destination}` n'existe pas sur ce serveur.",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    return
            elif destination.startswith("<#") and destination.endswith(">"):
                try:
                    channel_id = int(destination[2:-1])
                    found_channel = ctx.guild.get_channel(channel_id)
                    if found_channel:
                        dest_type = "channel"
                        dest_id = channel_id
                    else:
                        embed = discord.Embed(
                            title="❌ Channel inaccessible",
                            description="Le channel mentionné n'est pas accessible.",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=embed)
                        return
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Format invalide",
                        description="Format de channel invalide. Utilisez `#nom-du-channel` ou `dm`.",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    return
            else:
                # Si la destination n'est ni dm ni un channel, c'est le début du message
                message = f"{destination} {message}" if message else destination
        
        # Si pas de message, utiliser un message par défaut
        if not message:
            message = "Rappel personnalisé"
        
        reminder_datetime = self.parse_datetime(date, time)
        
        if not reminder_datetime:
            embed = discord.Embed(
                title="❌ Format invalide",
                description="Le format de date ou d'heure n'est pas correct.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="📝 Formats acceptés",
                value="**Date:** DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY\n"
                      "**Heure:** HH:MM, HH.MM, HHMM",
                inline=False
            )
            embed.add_field(
                name="✨ Exemples",
                value="• `.setreminder 25/12/2024 15:30 Joyeux Noël!`\n"
                      "• `.setreminder 01-01-2025 00.00 Bonne année!`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Vérifier que la date n'est pas dans le passé
        if reminder_datetime <= datetime.now():
            embed = discord.Embed(
                title="❌ Date invalide", 
                description="La date et l'heure doivent être dans le futur!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Générer un ID unique pour le rappel
        reminder_id = f"{ctx.author.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Stocker le rappel
        self.reminders[reminder_id] = {
            'user_id': ctx.author.id,
            'channel_id': ctx.channel.id,
            'guild_id': ctx.guild.id if ctx.guild else None,
            'message': message,
            'datetime': reminder_datetime.isoformat(),
            'created_at': datetime.now().isoformat(),
            'dest_type': dest_type,
            'dest_id': dest_id
        }
        
        self.save_reminders()
        
        # Préparer le texte de destination pour la confirmation
        if dest_type == "dm":
            dest_text = "en message privé"
        elif dest_type == "channel":
            dest_channel = ctx.guild.get_channel(dest_id)
            dest_text = f"dans {dest_channel.mention}" if dest_channel else "dans un channel"
        else:
            dest_text = "dans ce channel"
        
        # Confirmation
        embed = discord.Embed(
            title="✅ Rappel créé",
            description=f"**Message:** {message}\n"
                       f"**Date:** {reminder_datetime.strftime('%d/%m/%Y à %H:%M')}\n"
                       f"**Destination:** {dest_text}\n"
                       f"**ID:** `{reminder_id}`",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
        await ctx.send(embed=embed)
    
    @commands.command(name='remindme', aliases=['rm'])
    async def remind_me(self, ctx, duration: str = None, destination: str = None, *, message: str = None):
        """
        Usage: .remindme 1h30m [#channel/dm] message
        """
        # Si aucun paramètre n'est fourni, afficher l'aide
        if not duration:
            embed = discord.Embed(
                title="⏰ Aide - Créer un rappel temporisé",
                description="Cette commande vous permet de créer un rappel qui se déclenchera dans un délai spécifique.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="💡 Syntaxe",
                value="`.remindme durée [destination] message`\n"
                      "**Alias:** `.rm`",
                inline=False
            )
            embed.add_field(
                name="⏱️ Unités de temps",
                value="• `s` = secondes\n"
                      "• `m` = minutes\n"
                      "• `h` = heures\n"
                      "• `d` = jours\n"
                      "*Vous pouvez les combiner !*",
                inline=False
            )
            embed.add_field(
                name="📍 Destinations",
                value="• `dm` = Message privé\n"
                      "• `#channel` = Channel spécifique\n"
                      "• *Rien* = Channel actuel (par défaut)",
                inline=False
            )
            embed.add_field(
                name="✨ Exemples",
                value="• `.remindme 30s Dans 30 secondes` (ici)\n"
                      "• `.remindme 5m dm Pause privée` (en DM)\n"
                      "• `.remindme 2h #general Réunion` (dans #general)\n"
                      "• `.remindme 1d #annonces Rappel important`\n"
                      "• `.rm 1h30m dm Rendez-vous médecin`",
                inline=False
            )
            embed.set_footer(text="Le message est optionnel - un message par défaut sera utilisé si omis")
            await ctx.send(embed=embed)
            return
        
        # Parser la destination et le message
        dest_type = "current"  # Par défaut: channel actuel
        dest_id = ctx.channel.id
        
        # Si destination est spécifiée
        if destination:
            if destination.lower() == "dm":
                dest_type = "dm"
                dest_id = None
            elif destination.startswith("#"):
                # Chercher le channel par nom
                channel_name = destination[1:]  # Enlever le #
                found_channel = discord.utils.get(ctx.guild.channels, name=channel_name)
                if found_channel:
                    dest_type = "channel"
                    dest_id = found_channel.id
                else:
                    embed = discord.Embed(
                        title="❌ Channel introuvable",
                        description=f"Le channel `{destination}` n'existe pas sur ce serveur.",
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="💡 Conseil",
                        value="Vérifiez l'orthographe du nom du channel ou utilisez `dm` pour un message privé.",
                        inline=False
                    )
                    await ctx.send(embed=embed)
                    return
            elif destination.startswith("<#") and destination.endswith(">"):
                # Mention de channel (#channel)
                try:
                    channel_id = int(destination[2:-1])
                    found_channel = ctx.guild.get_channel(channel_id)
                    if found_channel:
                        dest_type = "channel"
                        dest_id = channel_id
                    else:
                        embed = discord.Embed(
                            title="❌ Channel inaccessible",
                            description="Le channel mentionné n'est pas accessible.",
                            color=discord.Color.red()
                        )
                        await ctx.send(embed=embed)
                        return
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Format invalide",
                        description="Format de channel invalide. Utilisez `#nom-du-channel` ou `dm`.",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    return
            else:
                # Si la destination n'est ni dm ni un channel, c'est probablement le début du message
                message = f"{destination} {message}" if message else destination
        
        # Si pas de message, utiliser un message par défaut
        if not message:
            message = "Rappel personnalisé"
        
        try:
            # Parser la durée
            total_seconds = self.parse_duration(duration)
            if total_seconds is None or total_seconds <= 0:
                embed = discord.Embed(
                    title="❌ Durée invalide",
                    description="Le format de durée n'est pas correct.",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="⏱️ Formats acceptés",
                    value="• `30s` (30 secondes)\n"
                          "• `5m` (5 minutes)\n"
                          "• `2h` (2 heures)\n"
                          "• `1d` (1 jour)\n"
                          "• `1h30m` (1 heure 30 minutes)\n"
                          "• `2d5h30m` (2 jours 5 heures 30 minutes)",
                    inline=False
                )
                embed.add_field(
                    name="✨ Exemples corrects",
                    value="• `.remindme 30s Dans 30 secondes`\n"
                          "• `.remindme 1h30m Réunion dans 1h30`",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
            
            # Calculer la date du rappel
            reminder_datetime = datetime.now() + timedelta(seconds=total_seconds)
            
            # Générer un ID unique
            reminder_id = f"{ctx.author.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Stocker le rappel
            self.reminders[reminder_id] = {
                'user_id': ctx.author.id,
                'channel_id': ctx.channel.id,  # Channel où la commande a été tapée (pour référence)
                'guild_id': ctx.guild.id if ctx.guild else None,
                'message': message,
                'datetime': reminder_datetime.isoformat(),
                'created_at': datetime.now().isoformat(),
                'dest_type': dest_type,  # "current", "dm", "channel"
                'dest_id': dest_id       # ID du channel de destination ou None pour DM
            }
            
            self.save_reminders()
            
            # Préparer le texte de destination pour la confirmation
            if dest_type == "dm":
                dest_text = "en message privé"
            elif dest_type == "channel":
                dest_channel = ctx.guild.get_channel(dest_id)
                dest_text = f"dans {dest_channel.mention}" if dest_channel else "dans un channel"
            else:
                dest_text = "dans ce channel"
            
            # Confirmation
            embed = discord.Embed(
                title="✅ Rappel créé",
                description=f"**Message:** {message}\n"
                           f"**Dans:** {self.format_duration(total_seconds)}\n"
                           f"**Date:** {reminder_datetime.strftime('%d/%m/%Y à %H:%M')}\n"
                           f"**Destination:** {dest_text}\n"
                           f"**ID:** `{reminder_id}`",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur",
                description=f"Une erreur s'est produite lors de la création du rappel.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="🔍 Détails de l'erreur",
                value=f"```{str(e)}```",
                inline=False
            )
            embed.add_field(
                name="💡 Aide",
                value="Tapez `.remindme` sans paramètres pour voir l'aide complète.",
                inline=False
            )
            await ctx.send(embed=embed)
            print(f"Erreur dans remind_me: {e}")
    
    def parse_duration(self, duration_str):
        """Parse une durée comme '1h30m' en secondes"""
        # Nettoyer la chaîne
        duration_str = duration_str.lower().strip()
        
        # Pattern pour capturer les nombres et unités
        pattern = r'(\d+)([smhd])'
        matches = re.findall(pattern, duration_str)
        
        if not matches:
            return None
        
        total_seconds = 0
        multipliers = {
            's': 1,          # secondes
            'm': 60,         # minutes
            'h': 3600,       # heures
            'd': 86400       # jours
        }
        
        for value, unit in matches:
            if unit in multipliers:
                total_seconds += int(value) * multipliers[unit]
            else:
                return None
        
        return total_seconds
    
    def format_duration(self, seconds):
        """Formate une durée en secondes en texte lisible"""
        if seconds < 60:
            return f"{seconds} seconde{'s' if seconds > 1 else ''}"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes == 0:
                return f"{hours} heure{'s' if hours > 1 else ''}"
            return f"{hours}h{minutes}m"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if hours == 0:
                return f"{days} jour{'s' if days > 1 else ''}"
            return f"{days}j{hours}h"
    
    @commands.command(name='myreminders', aliases=['reminders', 'listreminders'])
    async def list_reminders(self, ctx):
        """Affiche la liste de vos rappels actifs"""
        user_reminders = []
        
        for reminder_id, reminder in self.reminders.items():
            if reminder['user_id'] == ctx.author.id:
                try:
                    reminder_datetime = datetime.fromisoformat(reminder['datetime'])
                    if reminder_datetime > datetime.now():
                        user_reminders.append((reminder_id, reminder, reminder_datetime))
                except ValueError:
                    print(f"Erreur de format datetime pour le rappel {reminder_id}")
                    continue
        
        if not user_reminders:
            embed = discord.Embed(
                title="📋 Vos rappels",
                description="Vous n'avez aucun rappel actif.\n\n"
                           "**Créer un rappel:**\n"
                           "• `.remindme 30m Message` (dans 30 minutes)\n"
                           "• `.setreminder 25/12/2024 15:30 Message` (date fixe)",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        # Trier par date
        user_reminders.sort(key=lambda x: x[2])
        
        embed = discord.Embed(
            title="📋 Vos rappels actifs",
            color=discord.Color.blue()
        )
        
        for i, (reminder_id, reminder, reminder_datetime) in enumerate(user_reminders[:10]):  # Limite à 10
            time_left = reminder_datetime - datetime.now()
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes = remainder // 60
            
            time_str = []
            if days > 0:
                time_str.append(f"{days}j")
            if hours > 0:
                time_str.append(f"{hours}h")
            if minutes > 0:
                time_str.append(f"{minutes}m")
            
            time_remaining = " ".join(time_str) if time_str else "< 1m"
            
            embed.add_field(
                name=f"ID: {reminder_id}",
                value=f"**Message:** {reminder['message'][:50]}{'...' if len(reminder['message']) > 50 else ''}\n"
                      f"**Date:** {reminder_datetime.strftime('%d/%m/%Y à %H:%M')}\n"
                      f"**Dans:** {time_remaining}",
                inline=False
            )
        
        if len(user_reminders) > 10:
            embed.set_footer(text=f"Affichage de 10/{len(user_reminders)} rappels")
        else:
            embed.set_footer(text=f"Total: {len(user_reminders)} rappel{'s' if len(user_reminders) > 1 else ''}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='deletereminder', aliases=['delreminder', 'removereminder'])
    async def delete_reminder(self, ctx, reminder_id: str = None):
        """Supprime un rappel par son ID"""
        # Si aucun ID n'est fourni, afficher l'aide
        if not reminder_id:
            embed = discord.Embed(
                title="🗑️ Aide - Supprimer un rappel",
                description="Cette commande vous permet de supprimer un de vos rappels.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="💡 Syntaxe",
                value="`.deletereminder ID_du_rappel`\n"
                      "**Alias:** `.delreminder`, `.removereminder`",
                inline=False
            )
            embed.add_field(
                name="🔍 Comment trouver l'ID ?",
                value="Utilisez `.myreminders` pour voir tous vos rappels avec leurs IDs",
                inline=False
            )
            embed.add_field(
                name="✨ Exemple",
                value="`.deletereminder 123456789_20240315_143052`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        if reminder_id not in self.reminders:
            embed = discord.Embed(
                title="❌ Rappel introuvable",
                description=f"Aucun rappel trouvé avec l'ID `{reminder_id}`",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Conseil",
                value="Utilisez `.myreminders` pour voir tous vos rappels actifs avec leurs IDs",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        reminder = self.reminders[reminder_id]
        
        # Vérifier que l'utilisateur est le propriétaire du rappel
        if reminder['user_id'] != ctx.author.id:
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous ne pouvez supprimer que vos propres rappels.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Supprimer le rappel
        del self.reminders[reminder_id]
        self.save_reminders()
        
        embed = discord.Embed(
            title="✅ Rappel supprimé",
            description=f"Le rappel a été supprimé avec succès.\n\n"
                       f"**Message supprimé:** {reminder['message'][:100]}{'...' if len(reminder['message']) > 100 else ''}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @tasks.loop(seconds=30)  # Vérifie toutes les 30 secondes
    async def check_reminders(self):
        """Vérifie et envoie les rappels qui doivent être déclenchés"""
        current_time = datetime.now()
        reminders_to_remove = []
        
        for reminder_id, reminder in self.reminders.items():
            try:
                reminder_datetime = datetime.fromisoformat(reminder['datetime'])
                
                if current_time >= reminder_datetime:
                    # Envoyer le rappel
                    try:
                        user = self.bot.get_user(reminder['user_id'])
                        if user:
                            embed = discord.Embed(
                                title="🔔 Rappel",
                                description=reminder['message'],
                                color=discord.Color.gold()
                            )
                            embed.add_field(
                                name="Créé le",
                                value=datetime.fromisoformat(reminder['created_at']).strftime('%d/%m/%Y à %H:%M'),
                                inline=True
                            )
                            embed.set_footer(text=f"Rappel pour {user.display_name}")
                            
                            # Déterminer où envoyer le rappel
                            dest_type = reminder.get('dest_type', 'current')
                            dest_id = reminder.get('dest_id', reminder['channel_id'])
                            
                            if dest_type == "dm":
                                # Envoyer en DM
                                try:
                                    await user.send(embed=embed)
                                except discord.Forbidden:
                                    # Si impossible d'envoyer en DM, envoyer dans le channel original
                                    fallback_channel = self.bot.get_channel(reminder['channel_id'])
                                    if fallback_channel:
                                        embed.add_field(
                                            name="⚠️ Note",
                                            value="Impossible d'envoyer en DM, rappel envoyé ici.",
                                            inline=False
                                        )
                                        await fallback_channel.send(f"{user.mention}", embed=embed)
                            else:
                                # Envoyer dans un channel
                                channel = self.bot.get_channel(dest_id)
                                if channel:
                                    await channel.send(f"{user.mention}", embed=embed)
                                else:
                                    # Channel introuvable, envoyer dans le channel original
                                    fallback_channel = self.bot.get_channel(reminder['channel_id'])
                                    if fallback_channel:
                                        embed.add_field(
                                            name="⚠️ Note",
                                            value="Channel de destination introuvable, rappel envoyé ici.",
                                            inline=False
                                        )
                                        await fallback_channel.send(f"{user.mention}", embed=embed)
                    except Exception as e:
                        print(f"Erreur lors de l'envoi du rappel {reminder_id}: {e}")
                    
                    # Marquer pour suppression
                    reminders_to_remove.append(reminder_id)
            except ValueError as e:
                print(f"Erreur de format datetime pour le rappel {reminder_id}: {e}")
                # Marquer les rappels avec des erreurs pour suppression
                reminders_to_remove.append(reminder_id)
        
        # Supprimer les rappels traités
        for reminder_id in reminders_to_remove:
            if reminder_id in self.reminders:
                del self.reminders[reminder_id]
        
        if reminders_to_remove:
            self.save_reminders()
    
    @check_reminders.before_loop
    async def before_check_reminders(self):
        """Attend que le bot soit prêt avant de commencer la boucle"""
        await self.bot.wait_until_ready()
    
    # Gestion des erreurs pour les commandes
    @set_reminder.error
    async def set_reminder_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await self.set_reminder(ctx)  # Afficher l'aide
        else:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors de l'exécution de la commande.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            print(f"Erreur dans set_reminder: {error}")
    
    @remind_me.error
    async def remind_me_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await self.remind_me(ctx)  # Afficher l'aide
        else:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors de l'exécution de la commande.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            print(f"Erreur dans remind_me: {error}")
    
    @delete_reminder.error
    async def delete_reminder_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await self.delete_reminder(ctx)  # Afficher l'aide
        else:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Une erreur s'est produite lors de l'exécution de la commande.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            print(f"Erreur dans delete_reminder: {error}")
    
    def cog_unload(self):
        """Nettoie quand le cog est déchargé"""
        self.check_reminders.cancel()

async def setup(bot):
    await bot.add_cog(Reminder(bot))