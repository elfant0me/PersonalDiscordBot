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
        
    async def run_nmap_command(self, command: list, timeout: int = 60) -> tuple:
        """Exécute une commande nmap de manière asynchrone"""
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
            return None, "Timeout: Le scan a pris trop de temps", 1
        except Exception as e:
            return None, f"Erreur: {str(e)}", 1

    @commands.command(name='nmap')
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
            
        # Préparation de la commande selon le type de scan
        base_cmd = ['nmap']
        
        if scan_type == "basic":
            cmd = base_cmd + ['-T4', '-F', target]
            description = "Scan basique des ports les plus courants"
        elif scan_type == "stealth":
            cmd = base_cmd + ['-sS', '-T4', '-F', target]
            description = "Scan SYN stealth"
        elif scan_type == "version":
            cmd = base_cmd + ['-sV', '-T4', '--top-ports', '100', target]
            description = "Détection de version des services"
        elif scan_type == "os":
            cmd = base_cmd + ['-O', '-T4', '--top-ports', '100', target]
            description = "Détection du système d'exploitation"
        elif scan_type == "vuln":
            cmd = base_cmd + ['--script', 'vuln', '-T4', '--top-ports', '100', target]
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
        stdout, stderr, returncode = await self.run_nmap_command(cmd, timeout=120)
        
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
        if len(stdout) > 2000:
            # Si le résultat est trop long, on le tronque
            stdout = stdout[:1900] + "\n... (résultat tronqué)"
            
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

    @commands.command(name='nmap_help')
    async def nmap_help(self, ctx):
        """Affiche l'aide pour les commandes nmap"""
        
        embed = discord.Embed(
            title="🛠️ Aide Nmap",
            description="Commandes disponibles pour le scan réseau",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=".nmap <target> [type]",
            value="Effectue un scan nmap\n"
                  "**Types disponibles:**\n"
                  "• `basic` - Scan basique (défaut)\n"
                  "• `stealth` - Scan SYN stealth\n"
                  "• `version` - Détection de version\n"
                  "• `os` - Détection d'OS\n"
                  "• `vuln` - Scan de vulnérabilités",
            inline=False
        )
        
        embed.add_field(
            name="Exemples",
            value="```\n!nmap 192.168.1.1\n!nmap localhost stealth\n!nmap 10.0.0.1 version\n```",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Restrictions",
            value="• Les scans localhost/127.x.x.x sont interdits\n"
                  "• Commande réservée aux utilisateurs autorisés\n"
                  "• Timeout de 2 minutes par scan",
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