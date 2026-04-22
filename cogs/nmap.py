# cogs/nmap.py

import discord
from discord.ext import commands
from utils.permissions import require_admin
import subprocess
import asyncio
import re
import json
from typing import Optional

class nmap(commands.Cog):
    """Cog pour les fonctionnalités de scan réseau avec nmap"""
    
    def __init__(self, bot):
        self.bot = bot
        
    def is_valid_target(self, target: str) -> bool:
        """Valide si la cible est acceptable (bloque seulement localhost)"""
        # Bloquer localhost et 127.x.x.x pour éviter les scans locaux
        if target.lower() in ['localhost', '::1']:
            return False
            
        # Bloquer toute la plage 127.x.x.x
        if re.match(r'^127\.', target):
            return False
            
        # Tout le reste est autorisé
        return True
        
    async def run_command(self, command: list, timeout: int = 60) -> tuple:
        """Exécute une commande de manière asynchrone"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            return stdout.decode('utf-8'), stderr.decode('utf-8'), process.returncode
            
        except asyncio.TimeoutError:
            return None, "Timeout: La commande a pris trop de temps", 1
        except Exception as e:
            return None, f"Erreur: {str(e)}", 1

    @commands.command(name='nmap', hidden=True)
    @require_admin()
    async def nmap_scan(self, ctx, target: str, scan_type: str = "basic"):
        """
        Usage: .nmap <target> [scan_type]  
        Scan types disponibles:
        - basic: Scan basique des ports
        - stealth: Scan SYN stealth
        - version: Détection de version
        - os: Détection d'OS
        - vuln: Scan de vulnérabilités
        """
        
        # Validation de la cible
        if not self.is_valid_target(target):
            await ctx.send("❌ Cible non autorisée. Les scans localhost/127.x.x.x sont interdits.")
            return
            
        # Préparation de la commande selon le type de scan (sudo requis pour certains scans)
        base_cmd = ['sudo', 'nmap']
        
        if scan_type == "basic":
            cmd = base_cmd + ['-Pn', '-T4', '-F', target]
            description = "Scan basique des ports les plus courants"
        elif scan_type == "stealth":
            cmd = base_cmd + ['-Pn', '-sS', '-T4', '-F', target]
            description = "Scan SYN stealth"
        elif scan_type == "version":
            cmd = base_cmd + ['-Pn', '-sV', '-T4', '--top-ports', '100', target]
            description = "Détection de version des services"
        elif scan_type == "os":
            cmd = base_cmd + ['-Pn', '-O', '-T4', '--top-ports', '100', target]
            description = "Détection du système d'exploitation"
        elif scan_type == "vuln":
            cmd = base_cmd + ['-Pn', '--script', 'vuln', '-T4', '--top-ports', '100', target]
            description = "Scan de vulnérabilités"
        else:
            await ctx.send("❌ Type de scan non reconnu. Types disponibles: basic, stealth, version, os, vuln")
            return
            
        # Message d'attente
        embed = discord.Embed(
            title="🔍 Scan en cours...",
            description=f"**Cible:** {target}\n**Type:** {description}",
            color=discord.Color.orange()
        )
        msg = await ctx.send(embed=embed)
        
        # Exécution du scan
        stdout, stderr, returncode = await self.run_command(cmd, timeout=120)
        
        # Traitement des résultats
        if returncode != 0:
            embed = discord.Embed(
                title="❌ Erreur lors du scan",
                description=f"```\n{stderr}\n```",
                color=discord.Color.red()
            )
            await msg.edit(embed=embed)
            return
            
        # Formatage des résultats
        # Embed fields are limited to 1024 chars; account for code block markers + truncation suffix
        truncation_suffix = "\n... (résultat tronqué)"
        max_field_len = 1024 - 8 - len(truncation_suffix)  # 8 = len("```\n" + "\n```")
        if len(stdout) > max_field_len:
            stdout = stdout[:max_field_len] + truncation_suffix

        embed = discord.Embed(
            title="✅ Scan terminé",
            description=f"**Cible:** {target}\n**Type:** {description}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Résultats",
            value=f"```\n{stdout}\n```",
            inline=False
        )
        
        await msg.edit(embed=embed)

    @commands.command(name='nslookup')
    @require_admin()
    async def nslookup(self, ctx, domain: str, record_type: str = "A"):
        """
        Usage: .nslookup <domain> [record_type]
        Types d'enregistrements disponibles:
        - A: Adresse IPv4 (défaut)
        - AAAA: Adresse IPv6
        - MX: Serveurs mail
        - NS: Serveurs de noms
        - TXT: Enregistrements texte
        - CNAME: Alias
        - SOA: Start of Authority
        - ANY: Tous les enregistrements
        """

        # Détecter si c'est une IP pour faire un reverse lookup automatique (PTR)
        is_ip = bool(re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain) or re.match(r'^[0-9a-fA-F:]+:[0-9a-fA-F:]+$', domain))

        if is_ip:
            record_type = "PTR"
            embed = discord.Embed(
                title="🔎 Reverse DNS en cours...",
                description=f"**IP:** `{domain}`\n**Type:** PTR (reverse lookup automatique)",
                color=discord.Color.orange()
            )
            msg = await ctx.send(embed=embed)
            cmd = ['dig', '+noall', '+answer', '+authority', '-x', domain]
        else:
            record_type = record_type.upper()
            valid_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "ANY"]

            if record_type not in valid_types:
                await ctx.send(f"❌ Type d'enregistrement non reconnu. Types disponibles: {', '.join(valid_types)}")
                return

            # Message d'attente
            embed = discord.Embed(
                title="🔎 Résolution DNS en cours...",
                description=f"**Domaine:** {domain}\n**Type:** {record_type}",
                color=discord.Color.orange()
            )
            msg = await ctx.send(embed=embed)

            # On utilise `dig` qui est plus fiable et lisible que nslookup
            cmd = ['dig', '+noall', '+answer', '+authority', '-t', record_type, domain]
        stdout, stderr, returncode = await self.run_command(cmd, timeout=30)

        if returncode != 0 or (not stdout and stderr):
            embed = discord.Embed(
                title="❌ Erreur lors de la résolution",
                description=f"```\n{stderr or 'Aucune réponse reçue.'}\n```",
                color=discord.Color.red()
            )
            await msg.edit(embed=embed)
            return

        result = stdout.strip() if stdout.strip() else "Aucun enregistrement trouvé pour ce type."

        if len(result) > 1900:
            result = result[:1900] + "\n... (résultat tronqué)"

        embed = discord.Embed(
            title="✅ Résolution DNS terminée",
            description=f"**Domaine:** `{domain}`\n**Type:** `{record_type}`",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Résultats",
            value=f"```\n{result}\n```",
            inline=False
        )

        await msg.edit(embed=embed)

    def parse_ping_stats(self, output: str) -> dict:
        """Extrait les statistiques du ping"""
        stats = {}
        pkt_match = re.search(
            r'(\d+) packets transmitted, (\d+) received,.*?(\d+)% packet loss',
            output
        )
        if pkt_match:
            stats['sent'] = int(pkt_match.group(1))
            stats['received'] = int(pkt_match.group(2))
            stats['loss'] = int(pkt_match.group(3))

        rtt_match = re.search(
            r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)',
            output
        )
        if rtt_match:
            stats['min'] = float(rtt_match.group(1))
            stats['avg'] = float(rtt_match.group(2))
            stats['max'] = float(rtt_match.group(3))
            stats['mdev'] = float(rtt_match.group(4))

        time_match = re.search(r'time=([\d.]+)\s*ms', output)
        if time_match:
            stats['time'] = float(time_match.group(1))

        return stats

    @commands.command(name='ping')
    @require_admin()
    async def ping_host(self, ctx, target: Optional[str] = None):
        """
        Usage: .ping <ip/domaine>
        """

        if not target:
            embed = discord.Embed(
                title="📡 Syntaxe de la commande ping",
                description=(
                    "Utilisation: `.ping <ip/domaine>`\n\n"
                    "**Exemples:**\n"
                    "`.ping 8.8.8.8`\n"
                    "`.ping google.com`"
                ),
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        # Validation de la cible
        if not self.is_valid_target(target):
            await ctx.send("❌ Cible non autorisée. Les pings vers localhost/127.x.x.x sont interdits.")
            return

        # Message d'attente
        embed = discord.Embed(
            title="📡 Ping en cours...",
            description=f"**Host:** `{target}`\n**Requêtes:** 1",
            color=discord.Color.orange()
        )
        msg = await ctx.send(embed=embed)

        # Exécution du ping avec une seule requête
        cmd = ['ping', '-c', '1', '-W', '2', target]
        stdout, stderr, returncode = await self.run_command(cmd, timeout=8)

        # Hôte injoignable
        if returncode != 0 and not stdout:
            embed = discord.Embed(
                title="❌ Ping échoué",
                description=f"**Cible:** `{target}`\n```\n{stderr}\n```",
                color=discord.Color.red()
            )
            await msg.edit(embed=embed)
            return

        # Parse les stats
        stats = self.parse_ping_stats(stdout or "")
        loss = stats.get('loss', 100)

        response_time = stats.get('time', stats.get('avg'))

        if loss == 0:
            color = discord.Color.green()
            status_text = "🟢 Host reachable"
            result_text = f"{response_time:.2f} ms" if response_time is not None else "Réponse reçue"
        elif loss < 100:
            color = discord.Color.orange()
            status_text = "🟠 Packet loss detected"
            result_text = f"{response_time:.2f} ms" if response_time is not None else "Réponse partielle"
        else:
            color = discord.Color.red()
            status_text = "🔴 Host unreachable"
            result_text = stderr.strip() or "Timeout"

        embed = discord.Embed(
            title="🌐 Ping Host",
            color=color
        )
        embed.add_field(name="Host", value=f"`{target}`", inline=False)
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Result", value=result_text, inline=True)
        embed.set_footer(text=f"PythonBot Monitoring • Today at {discord.utils.utcnow().strftime('%H:%M')}")

        await msg.edit(embed=embed)

    @commands.command(name='nmap_help')
    async def nmap_help(self, ctx):
        """Affiche l'aide pour les commandes réseau"""
        
        embed = discord.Embed(
            title="🛠️ Aide — Outils Réseau",
            description="Commandes disponibles pour le scan et la reconnaissance réseau",
            color=discord.Color.blue()
        )

        # Commande nmap
        embed.add_field(
            name="🔍 .nmap <target> [type]",
            value=(
                "Effectue un scan nmap sur la cible (exécuté en `sudo`).\n"
                "**Types disponibles:**\n"
                "• `basic` — Scan rapide des ports courants *(défaut)*\n"
                "• `stealth` — Scan SYN stealth (discret)\n"
                "• `version` — Détection de version des services\n"
                "• `os` — Détection du système d'exploitation\n"
                "• `vuln` — Scan de vulnérabilités (scripts NSE)\n\n"
                "**Exemples:**\n"
                "```\n.nmap 192.168.1.1\n.nmap 10.0.0.1 stealth\n.nmap 10.0.0.1 vuln\n```"
            ),
            inline=False
        )

        # Commande nslookup
        embed.add_field(
            name="🔎 .nslookup <domain> [type]",
            value=(
                "Résout un nom de domaine via DNS (`dig`).\n"
                "**Types d'enregistrements:**\n"
                "• `A` — Adresse IPv4 *(défaut)*\n"
                "• `AAAA` — Adresse IPv6\n"
                "• `MX` — Serveurs mail\n"
                "• `NS` — Serveurs de noms\n"
                "• `TXT` — Enregistrements texte (SPF, DMARC…)\n"
                "• `CNAME` — Alias\n"
                "• `SOA` — Start of Authority\n"
                "• `ANY` — Tous les enregistrements\n\n"
                "**Exemples:**\n"
                "```\n.nslookup google.com\n.nslookup google.com MX\n.nslookup example.com TXT\n```"
            ),
            inline=False
        )

        # Commande ping
        embed.add_field(
            name="📡 .ping <ip/domaine>",
            value=(
                "Ping un hôte avec une seule requête et affiche un résultat compact.\n"
                "Si aucun host n'est fourni, la syntaxe de la commande est affichée.\n\n"
                "**Exemples:**\n"
                "```\n.ping 8.8.8.8\n.ping google.com\n```"
            ),
            inline=False
        )

        # Restrictions
        embed.add_field(
            name="⚠️ Restrictions",
            value=(
                "• Les cibles `localhost` / `127.x.x.x` sont interdites\n"
                "• Commandes réservées aux utilisateurs autorisés\n"
                "• Timeout: **2 min** pour nmap, **30 sec** pour nslookup, **~8 sec** pour ping"
            ),
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        """Événement appelé quand le cog est chargé"""
        print(f"Cog {self.__class__.__name__} chargé avec succès!")

# Fonction pour charger le cog
async def setup(bot):
    await bot.add_cog(nmap(bot))
