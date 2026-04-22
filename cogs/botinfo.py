# cogs/botinfo.py

import discord
from discord.ext import commands
from config import BOT_PREFIX
import platform
import psutil
import datetime
import subprocess
import sys
import os
import glob

class Botinfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_cpu_name(self):
        """Récupère le nom du processeur selon l'OS"""
        try:
            if platform.system() == "Windows":
                # Windows - utilise wmic
                result = subprocess.run(
                    ["wmic", "cpu", "get", "name"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if line.strip() and "Name" not in line:
                            return line.strip()
                            
            elif platform.system() == "Linux":
                # Linux - lit /proc/cpuinfo
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
                            
            elif platform.system() == "Darwin":  # macOS
                # macOS - utilise sysctl
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
                    
        except Exception:
            pass
        
        # Fallback si les méthodes spécifiques échouent
        return platform.processor() or "Processeur inconnu"

    def get_disk_usage(self):
        """Récupère l'utilisation du disque"""
        try:
            disk = psutil.disk_usage('/')
            return {
                'total': disk.total / (1024 ** 3),
                'used': disk.used / (1024 ** 3),
                'free': disk.free / (1024 ** 3),
                'percent': (disk.used / disk.total) * 100
            }
        except Exception:
            return None

    def get_python_info(self):
        """Récupère les informations Python"""
        return {
            'version': sys.version.split()[0],
            'implementation': platform.python_implementation(),
            'compiler': platform.python_compiler()
        }

    def get_temperatures(self):
        """Récupère les températures du système"""
        temps = {}
        
        try:
            if platform.system() == "Linux":
                # Méthode 1: psutil (le plus fiable)
                try:
                    # Vérifier si psutil supporte les températures
                    if hasattr(psutil, 'sensors_temperatures'):
                        sensors = psutil.sensors_temperatures()
                        if sensors:
                            for name, entries in sensors.items():
                                for entry in entries:
                                    label = entry.label or f"{name}"
                                    if entry.current:
                                        temps[label] = {
                                            'current': round(entry.current, 1),
                                            'high': entry.high if entry.high else None,
                                            'critical': entry.critical if entry.critical else None
                                        }
                    else:
                        print("psutil.sensors_temperatures() non disponible")
                except AttributeError:
                    print("psutil version trop ancienne pour sensors_temperatures")
                except Exception as e:
                    print(f"Erreur psutil: {e}")
                except Exception:
                    pass
                
                # Méthode 2: Lecture directe des fichiers hwmon (fallback)
                if not temps:
                    try:
                        hwmon_paths = glob.glob('/sys/class/hwmon/hwmon*/temp*_input')
                        for path in hwmon_paths:
                            try:
                                with open(path, 'r') as f:
                                    temp_raw = int(f.read().strip())
                                    temp_celsius = temp_raw / 1000.0
                                    
                                    # Essayer de récupérer le nom du capteur
                                    name_path = path.replace('_input', '_label')
                                    sensor_name = "Capteur inconnu"
                                    
                                    if os.path.exists(name_path):
                                        try:
                                            with open(name_path, 'r') as nf:
                                                sensor_name = nf.read().strip()
                                        except:
                                            pass
                                    else:
                                        # Utiliser le nom du dossier hwmon
                                        hwmon_dir = os.path.dirname(path)
                                        name_file = os.path.join(hwmon_dir, 'name')
                                        if os.path.exists(name_file):
                                            try:
                                                with open(name_file, 'r') as nf:
                                                    sensor_name = nf.read().strip()
                                            except:
                                                pass
                                    
                                    temps[f"{sensor_name}_{os.path.basename(path)}"] = {
                                        'current': round(temp_celsius, 1),
                                        'high': None,
                                        'critical': None
                                    }
                            except Exception:
                                continue
                    except Exception:
                        pass
                
                # Méthode 3: sensors command (derniers recours)
                if not temps:
                    try:
                        # Vérifier si sensors est disponible
                        sensors_check = subprocess.run(['which', 'sensors'], 
                                                     capture_output=True, 
                                                     text=True)
                        
                        if sensors_check.returncode == 0:
                            result = subprocess.run(
                                ['sensors', '-A'], 
                                capture_output=True, 
                                text=True, 
                                timeout=5
                            )
                            if result.returncode == 0:
                                lines = result.stdout.split('\n')
                                current_chip = ""
                                for line in lines:
                                    line = line.strip()
                                    if line and not line.startswith(' ') and not line.startswith('+') and ':' in line:
                                        if not any(char in line for char in ['°C', '°F', 'RPM', 'V']):
                                            current_chip = line.split(':')[0]
                                        elif '°C' in line:
                                            try:
                                                parts = line.split(':')
                                                if len(parts) >= 2:
                                                    temp_part = parts[1].strip()
                                                    temp_val = float(temp_part.split('°C')[0].strip().replace('+', ''))
                                                    sensor_name = parts[0].strip()
                                                    temps[f"{current_chip}_{sensor_name}"] = {
                                                        'current': round(temp_val, 1),
                                                        'high': None,
                                                        'critical': None
                                                    }
                                            except ValueError:
                                                continue
                        else:
                            print("Commande 'sensors' non trouvée")
                    except FileNotFoundError:
                        print("Commande 'sensors' non disponible")
                    except Exception as e:
                        print(f"Erreur sensors: {e}")
            
            # Pour Windows (optionnel, nécessite des outils tiers)
            elif platform.system() == "Windows":
                # Pourrait utiliser wmi ou autres outils, mais plus complexe
                pass
                
        except Exception:
            pass
        
        return temps

    def get_bot_stats(self):
        """Récupère les statistiques du bot"""
        total_members = sum(guild.member_count for guild in self.bot.guilds)
        
        # Uptime du bot
        if hasattr(self.bot, 'start_time') and self.bot.start_time:
            bot_uptime = datetime.datetime.now() - self.bot.start_time
            uptime_str = f"{bot_uptime.days} jours, {bot_uptime.seconds // 3600}h {(bot_uptime.seconds % 3600) // 60}m"
        else:
            uptime_str = "Indisponible"
        
        return {
            'guilds': len(self.bot.guilds),
            'members': total_members,
            'uptime': uptime_str,
            'latency': round(self.bot.latency * 1000, 2)  # en ms
        }

    def format_temperature_display(self, temps, max_temps=8):
        """Formate l'affichage des températures pour l'embed"""
        if not temps:
            return "❌ Aucune température détectée"
        
        # Organiser les températures par priorité
        priority_order = ['Package', 'Core', 'GPU', 'radeon', 'temp1']
        sorted_temps = []
        
        # D'abord les températures importantes (CPU, GPU)
        for priority in priority_order:
            for name, data in temps.items():
                if any(p.lower() in name.lower() for p in [priority]):
                    sorted_temps.append((name, data))
        
        # Puis le reste par température décroissante
        remaining = [(name, data) for name, data in temps.items() 
                    if (name, data) not in sorted_temps]
        remaining.sort(key=lambda x: x[1]['current'], reverse=True)
        sorted_temps.extend(remaining)
        
        # Limiter l'affichage
        display_temps = sorted_temps[:max_temps]
        
        temp_lines = []
        for name, data in display_temps:
            current = data['current']
            
            # Emoji et couleur basés sur la température
            if current >= 80:
                emoji = "🔥"
            elif current >= 70:
                emoji = "🌡️"
            elif current >= 50:
                emoji = "🟡"
            else:
                emoji = "🟢"
            
            # Nettoyer et formater le nom du capteur
            clean_name = self.clean_sensor_name(name)
            
            temp_line = f"{emoji} **{clean_name}:** {current}°C"
            
            # Ajouter les seuils critiques/élevés
            thresholds = []
            if data['high'] and data['high'] != data['critical']:
                thresholds.append(f"Max: {data['high']}°C")
            if data['critical']:
                thresholds.append(f"Crit: {data['critical']}°C")
            
            if thresholds:
                temp_line += f" ({', '.join(thresholds)})"
            
            temp_lines.append(temp_line)
        
        result = "\n".join(temp_lines)
        
        if len(sorted_temps) > max_temps:
            result += f"\n*... et {len(sorted_temps) - max_temps} autres*"
        
        return result

    def clean_sensor_name(self, name):
        """Nettoie et améliore les noms de capteurs"""
        # Mapping des noms techniques vers des noms plus lisibles
        name_mapping = {
            'Package id 0': 'CPU Package',
            'Core 0': 'CPU Cœur 0',
            'Core 1': 'CPU Cœur 1', 
            'Core 2': 'CPU Cœur 2',
            'Core 3': 'CPU Cœur 3',
            'Core 4': 'CPU Cœur 4',
            'Core 5': 'CPU Cœur 5',
            'radeon_temp1': 'GPU Radeon',
            'pch_cannonlake_temp1': 'Chipset PCH',
            'acpitz_temp1': 'ACPI Thermal'
        }
        
        # Vérifier les mappings directs
        if name in name_mapping:
            return name_mapping[name]
        
        # Nettoyage générique
        clean = name.replace('_temp1_input', '').replace('_temp1', '')
        clean = clean.replace('_', ' ').title()
        
        # Raccourcir si trop long
        if len(clean) > 18:
            clean = clean[:15] + "..."
            
        return clean

    async def temperature(self, ctx):
        """Affiche les températures du système"""
        temps = self.get_temperatures()
        
        embed = discord.Embed(
            title="🌡️ Températures du système",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        
        if temps:
            # Calculer la température moyenne
            avg_temp = sum(t['current'] for t in temps.values()) / len(temps)
            max_temp = max(t['current'] for t in temps.values())
            
            embed.add_field(
                name="📊 Résumé",
                value=(
                    f"**Capteurs détectés:** {len(temps)}\n"
                    f"**Température max:** {max_temp}°C\n"
                    f"**Température moyenne:** {avg_temp:.1f}°C"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🌡️ Détail des températures",
                value=self.format_temperature_display(temps, max_temps=12),
                inline=False
            )
            
            # Alerte si température élevée
            if max_temp >= 80:
                embed.add_field(
                    name="⚠️ Alerte",
                    value="🔥 Températures élevées détectées ! Vérifiez le refroidissement.",
                    inline=False
                )
        else:
            embed.add_field(
                name="❌ Erreur",
                value=(
                    "Impossible de récupérer les températures.\n"
                    "**Vérifications nécessaires:**\n"
                    "• `sudo apt install lm-sensors`\n"
                    "• `sudo sensors-detect` (puis redémarrer)\n"
                    "• `pip install psutil` (dans le venv)\n"
                    "• Tester avec: `sensors`\n"
                    f"• OS détecté: {platform.system()}"
                ),
                inline=False
            )
        
        embed.set_footer(
            text=f"Demandé par {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )
        
        await ctx.send(embed=embed)

    @commands.command(name="sysinfo")
    async def sysinfo(self, ctx):
        """Affiche les informations système complètes"""
        
        # Informations système
        uname = platform.uname()
        cpu_freq = psutil.cpu_freq()
        cpu_percent = psutil.cpu_percent(interval=1)
        virtual_mem = psutil.virtual_memory()
        
        # Informations supplémentaires
        cpu_name = self.get_cpu_name()
        disk_info = self.get_disk_usage()
        python_info = self.get_python_info()
        bot_stats = self.get_bot_stats()
        temps = self.get_temperatures()
        
        # Uptime système réel (depuis boot)
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        system_uptime = datetime.datetime.now() - boot_time

        embed = discord.Embed(
            title="🖥️ Informations système du bot",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )

        # Informations du bot
        embed.add_field(
            name="🤖 Bot Discord",
            value=(
                f"**Serveurs :** {bot_stats['guilds']}\n"
                f"**Utilisateurs :** {bot_stats['members']}\n"
                f"**Uptime Bot :** {bot_stats['uptime']}\n"
                f"**Latence :** {bot_stats['latency']} ms"
            ),
            inline=True
        )

        # Informations OS
        embed.add_field(
            name="🧠 Système d'exploitation",
            value=(
                f"**OS :** {uname.system} {uname.release}\n"
                f"**Architecture :** {uname.machine}\n"
                f"**Nom d'hôte :** {uname.node}"
            ),
            inline=True
        )

        # Informations processeur
        embed.add_field(
            name="⚙️ Processeur",
            value=(
                f"**Modèle :** {cpu_name}\n"
                f"**Cœurs :** {psutil.cpu_count(logical=False)} physiques / {psutil.cpu_count(logical=True)} logiques\n"
                f"**Fréquence :** {cpu_freq.current:.0f} MHz (Max : {cpu_freq.max:.0f} MHz)\n"
                f"**Utilisation :** {cpu_percent}%"
            ),
            inline=False
        )

        # Informations mémoire
        embed.add_field(
            name="📈 Mémoire RAM",
            value=(
                f"**Utilisée :** {virtual_mem.used / (1024 ** 3):.2f} GB\n"
                f"**Totale :** {virtual_mem.total / (1024 ** 3):.2f} GB\n"
                f"**Pourcentage :** {virtual_mem.percent}%"
            ),
            inline=True
        )

        # Informations disque
        if disk_info:
            embed.add_field(
                name="💾 Stockage",
                value=(
                    f"**Utilisé :** {disk_info['used']:.2f} GB\n"
                    f"**Total :** {disk_info['total']:.2f} GB\n"
                    f"**Libre :** {disk_info['free']:.2f} GB\n"
                    f"**Pourcentage :** {disk_info['percent']:.1f}%"
                ),
                inline=True
            )

        # Informations température
        if temps:
            max_temp = max(t['current'] for t in temps.values())
            avg_temp = sum(t['current'] for t in temps.values()) / len(temps)
            
            embed.add_field(
                name="🌡️ Températures",
                value=(
                    f"**Max :** {max_temp}°C\n"
                    f"**Moyenne :** {avg_temp:.1f}°C\n"
                    f"**Capteurs :** {len(temps)}\n"
                ),
                inline=True
            )

        # Informations Python
        embed.add_field(
            name="🐍 Python",
            value=(
                f"**Version :** {python_info['version']}\n"
                f"**Implémentation :** {python_info['implementation']}\n"
                f"**Discord.py :** {discord.__version__}"
            ),
            inline=True
        )

        # Uptime système
        embed.add_field(
            name="⏱️ Uptime Système",
            value=f"{system_uptime.days} jours, {system_uptime.seconds // 3600}h {(system_uptime.seconds % 3600) // 60}m",
            inline=False
        )

        # Alerte température si nécessaire
        if temps:
            max_temp = max(t['current'] for t in temps.values())
            if max_temp >= 80:
                embed.add_field(
                    name="⚠️ Alerte Température",
                    value="🔥 Températures élevées détectées !",
                    inline=False
                )

        # Pied de page
        embed.set_footer(
            text=f"Demandé par {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )

        await ctx.send(embed=embed)

    @commands.command(name="botinfo")
    async def botinfo(self, ctx):
        """Affiche uniquement les informations du bot"""
        bot_stats = self.get_bot_stats()
        
        embed = discord.Embed(
            title="🤖 Informations du Bot",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="📊 Statistiques",
            value=(
                f"**Serveurs :** {bot_stats['guilds']}\n"
                f"**Utilisateurs :** {bot_stats['members']}\n"
                f"**Commandes :** {len(self.bot.commands)}\n"
                f"**Cogs :** {len(self.bot.cogs)}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="⚡ Performance",
            value=(
                f"**Latence :** {bot_stats['latency']} ms\n"
                f"**Uptime :** {bot_stats['uptime']}\n"
                f"**Discord.py :** {discord.__version__}\n"
                f"**Python :** {sys.version.split()[0]}"
            ),
            inline=True
        )
        
        embed.set_footer(
            text=f"Demandé par {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )
        
        await ctx.send(embed=embed)

    @commands.command(name="prefix")
    async def prefix(self, ctx):
        """Affiche le préfixe du bot"""
        await ctx.send(f"📌 Mon préfixe actuel est : `{BOT_PREFIX}`")

    @sysinfo.error
    @botinfo.error
    async def command_error(self, ctx, error):
        """Gère les erreurs des commandes"""
        embed = discord.Embed(
            title="❌ Erreur",
            description=f"Une erreur est survenue : {str(error)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        # Log l'erreur pour le debug
        print(f"Erreur dans {ctx.command}: {error}")

# Chargement du COG (asynchrone requis depuis discord.py 2.0+)
async def setup(bot):
    await bot.add_cog(Botinfo(bot))
