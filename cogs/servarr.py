import os
import shutil
import subprocess
import socket
import json
import logging
import platform
import aiohttp
import asyncio
import psutil

import discord
from discord.ext import commands
from datetime import datetime, timedelta
import config
from utils.permissions import require_admin


logger = logging.getLogger(__name__)


class Servarr(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Configuration Jellyfin
        self.jellyfin_url = getattr(config, "JELLYFIN_URL", None) or os.getenv("JELLYFIN_URL")
        self.api_key = getattr(config, "JELLYFIN_API_KEY", None) or os.getenv("JELLYFIN_API_KEY")
        self.user_id = None

        # Configuration Sonarr
        self.sonarr_url = getattr(config, "SONARR_URL", None) or os.getenv("SONARR_URL")
        self.sonarr_api_key = getattr(config, "SONARR_API_KEY", None) or os.getenv("SONARR_API_KEY")

        # Configuration Radarr
        self.radarr_url = getattr(config, "RADARR_URL", None) or os.getenv("RADARR_URL")
        self.radarr_api_key = getattr(config, "RADARR_API_KEY", None) or os.getenv("RADARR_API_KEY")

        # Configuration Beszel
        self.beszel_url = getattr(config, "BESZEL_URL", None) or os.getenv("BESZEL_URL")
        self.beszel_email = getattr(config, "BESZEL_EMAIL", None) or os.getenv("BESZEL_EMAIL")
        self.beszel_password = getattr(config, "BESZEL_PASSWORD", None) or os.getenv("BESZEL_PASSWORD")
        self._beszel_token = None

    async def get_jellyfin_user_id(self):
        """Obtient l'ID utilisateur Jellyfin"""
        if self.user_id:
            return self.user_id

        url = f"{self.jellyfin_url}/Users"
        headers = {"X-Emby-Token": self.api_key}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        users = await response.json()
                        admin_user = next(
                            (
                                user
                                for user in users
                                if user.get("Policy", {}).get("IsAdministrator")
                            ),
                            None,
                        )
                        self.user_id = (
                            admin_user["Id"] if admin_user else users[0]["Id"]
                        )
                        return self.user_id
                    else:
                        return None
            except Exception as e:
                print(f"Erreur lors de la récupération de l'ID utilisateur: {e}")
                return None

    def get_image_url(self, item_id, image_type="Primary", width=300, height=450):
        """Génère l'URL pour l'image d'un élément avec authentification"""
        return f"{self.jellyfin_url}/Items/{item_id}/Images/{image_type}?width={width}&height={height}&X-Emby-Token={self.api_key}"

    async def get_latest_movies(self, limit=1):
        """Récupère les derniers films ajoutés"""
        user_id = await self.get_jellyfin_user_id()
        if not user_id:
            return None

        url = f"{self.jellyfin_url}/Users/{user_id}/Items"
        params = {
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "Fields": "DateCreated,Overview,Genres,ProductionYear,CommunityRating,ImageTags",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "Limit": limit,
        }
        headers = {"X-Emby-Token": self.api_key}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url, headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("Items", [])
                    else:
                        return None
            except Exception as e:
                print(f"Erreur lors de la récupération des films: {e}")
                return None

    async def get_latest_series(self, limit=1):
        """Récupère les dernières séries ajoutées"""
        user_id = await self.get_jellyfin_user_id()
        if not user_id:
            return None

        url = f"{self.jellyfin_url}/Users/{user_id}/Items"
        params = {
            "IncludeItemTypes": "Series",
            "Recursive": "true",
            "Fields": "DateCreated,Overview,Genres,ProductionYear,CommunityRating,ImageTags",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "Limit": limit,
        }
        headers = {"X-Emby-Token": self.api_key}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url, headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("Items", [])
                    else:
                        return None
            except Exception as e:
                print(f"Erreur lors de la récupération des séries: {e}")
                return None

    async def get_radarr_stats(self):
        """Récupère les statistiques Radarr"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Api-Key": self.radarr_api_key}

                wanted_url = f"{self.radarr_url}/api/v3/wanted/missing"
                params = {"pageSize": 1}
                async with session.get(
                    wanted_url, headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        wanted_data = await response.json()
                        wanted_count = wanted_data.get("totalRecords", 0)
                    else:
                        wanted_count = 0

                queue_url = f"{self.radarr_url}/api/v3/queue"
                async with session.get(queue_url, headers=headers) as response:
                    if response.status == 200:
                        queue_data = await response.json()
                        queued_count = queue_data.get("totalRecords", 0)
                    else:
                        queued_count = 0

                movies_url = f"{self.radarr_url}/api/v3/movie"
                async with session.get(movies_url, headers=headers) as response:
                    if response.status == 200:
                        movies_data = await response.json()
                        total_movies = len(movies_data)
                    else:
                        total_movies = 0

                return {
                    "wanted": wanted_count,
                    "queued": queued_count,
                    "total": total_movies,
                    "success": True,
                }
        except Exception as e:
            print(f"Erreur Radarr: {e}")
            return {"success": False, "error": str(e)}

    async def get_sonarr_stats(self):
        """Récupère les statistiques Sonarr"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Api-Key": self.sonarr_api_key}

                wanted_url = f"{self.sonarr_url}/api/v3/wanted/missing"
                params = {"pageSize": 1}
                async with session.get(
                    wanted_url, headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        wanted_data = await response.json()
                        wanted_count = wanted_data.get("totalRecords", 0)
                    else:
                        wanted_count = 0

                queue_url = f"{self.sonarr_url}/api/v3/queue"
                async with session.get(queue_url, headers=headers) as response:
                    if response.status == 200:
                        queue_data = await response.json()
                        queued_count = queue_data.get("totalRecords", 0)
                    else:
                        queued_count = 0

                series_url = f"{self.sonarr_url}/api/v3/series"
                async with session.get(series_url, headers=headers) as response:
                    if response.status == 200:
                        series_data = await response.json()
                        total_series = len(series_data)
                    else:
                        total_series = 0

                return {
                    "wanted": wanted_count,
                    "queued": queued_count,
                    "total": total_series,
                    "success": True,
                }
        except Exception as e:
            print(f"Erreur Sonarr: {e}")
            return {"success": False, "error": str(e)}

    async def get_active_streams(self):
        """Récupère les streams actifs sur Jellyfin"""
        url = f"{self.jellyfin_url}/Sessions"
        headers = {"X-Emby-Token": self.api_key}
        params = {"ActiveWithinSeconds": 60}

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        sessions = await response.json()
                        return [s for s in sessions if s.get("NowPlayingItem")], True
                    else:
                        print(f"[jellyfin view] Erreur HTTP {response.status}")
                        return [], False
            except Exception as e:
                print(f"[jellyfin view] Exception: {type(e).__name__}: {e}")
                return [], False

    def format_stream_info(self, session):
        """Formate les informations d'un stream actif"""
        item = session.get("NowPlayingItem", {})
        user = session.get("UserName", "Inconnu")
        client = session.get("Client", "Inconnu")
        device = session.get("DeviceName", "Inconnu")

        title = item.get("Name", "Titre inconnu")
        item_type = item.get("Type", "")
        series = item.get("SeriesName")
        season = item.get("ParentIndexNumber")
        episode = item.get("IndexNumber")

        if item_type == "Episode" and series:
            display_title = f"{series} — S{season:02d}E{episode:02d} · {title}"
        else:
            year = item.get("ProductionYear", "")
            display_title = f"{title} ({year})" if year else title

        position_ticks = session.get("PlayState", {}).get("PositionTicks", 0)
        runtime_ticks = item.get("RunTimeTicks", 0)
        if runtime_ticks:
            percent = int((position_ticks / runtime_ticks) * 100)
            pos_min = position_ticks // 600_000_000
            total_min = runtime_ticks // 600_000_000
            progress = f"{pos_min}min / {total_min}min ({percent}%)"
        else:
            progress = "N/A"

        is_paused = session.get("PlayState", {}).get("IsPaused", False)
        status = "⏸️ En pause" if is_paused else "▶️ En lecture"

        play_method = session.get("PlayState", {}).get("PlayMethod", "")
        if play_method == "DirectPlay":
            quality = "🟢 Direct Play"
        elif play_method == "DirectStream":
            quality = "🟡 Direct Stream"
        else:
            quality = "🔴 Transcodage"

        return {
            "display_title": display_title,
            "user": user,
            "client": client,
            "device": device,
            "progress": progress,
            "status": status,
            "quality": quality,
            "item_id": item.get("Id"),
            "item_type": item_type,
        }

    def format_movie_info(self, movie):
        """Formate les informations d'un film"""
        title = movie.get("Name", "Titre inconnu")
        year = movie.get("ProductionYear", "Année inconnue")
        rating = movie.get("CommunityRating")
        genres = movie.get("Genres", [])
        overview = movie.get("Overview", "")
        date_added = movie.get("DateCreated", "")

        if date_added:
            try:
                date_obj = datetime.fromisoformat(date_added.replace("Z", "+00:00"))
                formatted_date = date_obj.strftime("%d/%m/%Y à %H:%M")
            except Exception:
                formatted_date = "Date inconnue"
        else:
            formatted_date = "Date inconnue"

        rating_text = f" ⭐ {rating}/10" if rating else ""
        genres_text = ", ".join(genres[:3]) if genres else "Genres inconnus"

        if overview and len(overview) > 150:
            overview = overview[:150] + "..."

        return {
            "title": title,
            "year": year,
            "rating": rating_text,
            "genres": genres_text,
            "overview": overview or "Pas de description disponible",
            "date_added": formatted_date,
            "full_overview": movie.get("Overview", "Pas de description disponible"),
        }

    def format_series_info(self, series):
        """Formate les informations d'une série"""
        title = series.get("Name", "Titre inconnu")
        year = series.get("ProductionYear", "Année inconnue")
        rating = series.get("CommunityRating")
        genres = series.get("Genres", [])
        overview = series.get("Overview", "")
        date_added = series.get("DateCreated", "")

        if date_added:
            try:
                date_obj = datetime.fromisoformat(date_added.replace("Z", "+00:00"))
                formatted_date = date_obj.strftime("%d/%m/%Y à %H:%M")
            except Exception:
                formatted_date = "Date inconnue"
        else:
            formatted_date = "Date inconnue"

        rating_text = f" ⭐ {rating}/10" if rating else ""
        genres_text = ", ".join(genres[:3]) if genres else "Genres inconnus"

        if overview and len(overview) > 150:
            overview = overview[:150] + "..."

        return {
            "title": title,
            "year": year,
            "rating": rating_text,
            "genres": genres_text,
            "overview": overview or "Pas de description disponible",
            "date_added": formatted_date,
            "full_overview": series.get("Overview", "Pas de description disponible"),
        }

    async def get_beszel_token(self):
        """Authentification Beszel et récupération du token JWT"""
        if self._beszel_token:
            return self._beszel_token

        url = f"{self.beszel_url}/api/collections/users/auth-with-password"
        payload = {"identity": self.beszel_email, "password": self.beszel_password}

        logger.info(f"[beszel] URL: {url}")
        logger.info(f"[beszel] Email: {self.beszel_email}")

        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    body = await resp.text()
                    logger.info(f"[beszel] Status: {resp.status}")
                    logger.info(f"[beszel] Body: {body[:300]}")
                    if resp.status == 200:
                        data = json.loads(body)
                        self._beszel_token = data["token"]
                        return self._beszel_token
                    return None
            except Exception as e:
                logger.error(f"[beszel] EXCEPTION: {type(e).__name__}: {e}")
                return None

    async def get_beszel_systems(self):
        """Récupère tous les systèmes Beszel avec leurs stats"""
        token = await self.get_beszel_token()
        if not token:
            return None

        url = f"{self.beszel_url}/api/collections/systems/records"
        headers = {"Authorization": token}
        params = {"perPage": 100, "sort": "name"}

        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("items", [])
                    elif resp.status == 401:
                        self._beszel_token = None
                        logger.warning("[beszel] Token expiré, réinitialisation.")
                        return None
                    else:
                        logger.error(f"[beszel] Erreur HTTP {resp.status}")
                        return None
            except Exception as e:
                logger.error(f"[beszel] Exception get_systems: {e}")
                return None

    def format_uptime(self, seconds):
        """Convertit des secondes en format lisible j h m"""
        if not seconds:
            return "N/A"
        seconds = int(seconds)
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        parts = []
        if days:
            parts.append(f"{days}j")
        if hours:
            parts.append(f"{hours}h")
        if minutes or not parts:
            parts.append(f"{minutes}m")
        return " ".join(parts)

    # Commande déplacée dans cogs/monitoring.py
    async def beszel_status(self, ctx):
        """Affiche le statut, la charge et l'uptime de tous les systèmes Beszel"""
        await ctx.send("🖥️ Récupération des systèmes Beszel...")

        systems = await self.get_beszel_systems()

        if systems is None:
            embed = discord.Embed(
                title="❌ Erreur Beszel",
                description="Impossible de joindre l'API Beszel.\nVérifiez l'URL, l'email et le mot de passe dans la configuration.",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )
            await ctx.send(embed=embed)
            return

        if not systems:
            embed = discord.Embed(
                title="🖥️ Beszel — Aucun système",
                description="Aucun système n'est enregistré dans Beszel.",
                color=discord.Color.orange(),
                timestamp=datetime.now(),
            )
            await ctx.send(embed=embed)
            return

        status_emoji = {"up": "🟢", "down": "🔴", "paused": "⏸️"}

        up_count = sum(1 for s in systems if s.get("status") == "up")
        down_count = sum(1 for s in systems if s.get("status") == "down")

        embed = discord.Embed(
            title=f"🖥️ Beszel — {len(systems)} système(s)",
            description=f"🟢 **{up_count}** en ligne  •  🔴 **{down_count}** hors ligne",
            color=discord.Color.green() if down_count == 0 else discord.Color.orange(),
            timestamp=datetime.now(),
        )

        for system in systems:
            name = system.get("name", "Inconnu")
            host = system.get("host", "")
            status = system.get("status", "unknown")
            info = system.get("info", {})
            emoji = status_emoji.get(status, "❓")

            uptime = self.format_uptime(info.get("u", 0))

            cpu = info.get("cpu")
            cpu_str = f"{cpu:.1f}%" if cpu is not None else "N/A"

            mem_pct = info.get("mp")
            mem_total = info.get("t")
            if mem_pct is not None and mem_total:
                mem_used = mem_total * mem_pct / 100
                mem_str = f"{mem_used:.1f} / {mem_total:.0f} GB ({mem_pct:.0f}%)"
            else:
                mem_str = "N/A"

            la = info.get("la", [])
            if la and len(la) >= 3:
                la_str = f"{la[0]} / {la[1]} / {la[2]}"
            else:
                la_str = "N/A"

            disk_pct = info.get("dp")
            disk_str = f"{disk_pct:.1f}%" if disk_pct is not None else "N/A"

            value = (
                f"🔗 `{host}`\n"
                f"⏱️ Uptime: **{uptime}**\n"
                f"⚙️ CPU: **{cpu_str}**  •  Load: `{la_str}`\n"
                f"🧠 RAM: **{mem_str}**\n"
                f"💾 Disk: **{disk_str}**"
            )

            embed.add_field(name=f"{emoji} {name}", value=value, inline=True)

        embed.set_footer(text=f"Beszel • {self.beszel_url}")
        await ctx.send(embed=embed)

    # Commande déplacée dans cogs/monitoring.py
    @commands.has_permissions(administrator=True)
    async def beszel_debug(self, ctx):
        """Debug Beszel directement dans Discord"""
        url_auth = f"{self.beszel_url}/api/collections/users/auth-with-password"
        payload = {"identity": self.beszel_email, "password": self.beszel_password}

        await ctx.send(f"🔍 Test: `{url_auth}`")

        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(
                    url_auth, json=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    body = await resp.text()
                    icon = "✅" if resp.status == 200 else "❌"
                    await ctx.send(
                        f"{icon} **Auth:** `{resp.status}`\n```json\n{body[:400]}\n```"
                    )

                    if resp.status == 200:
                        token = json.loads(body).get("token", "")
                        url_sys = f"{self.beszel_url}/api/collections/systems/records"
                        async with session.get(
                            url_sys,
                            headers={"Authorization": token},
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as resp2:
                            body2 = await resp2.text()
                            icon2 = "✅" if resp2.status == 200 else "❌"
                            await ctx.send(
                                f"{icon2} **Systems:** `{resp2.status}`\n```json\n{body2[:400]}\n```"
                            )
            except Exception as e:
                await ctx.send(f"❌ **Exception:** `{type(e).__name__}: {e}`")

    # Gestion d'erreur déplacée dans cogs/monitoring.py
    async def beszel_status_error(self, ctx, error):
        await ctx.send(f"❌ Erreur Beszel: {str(error)}")

    def format_bytes(self, num: float) -> str:
        """Convertit des octets en format lisible."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if num < 1024:
                return f"{num:.1f} {unit}"
            num /= 1024
        return f"{num:.1f} PB"

    def get_disk_usage(self, paths: list[str]):
        """Retourne l'utilisation des disques pour une liste de chemins."""
        results = []
        for path in paths:
            if os.path.exists(path):
                try:
                    usage = shutil.disk_usage(path)
                    percent = round((usage.used / usage.total) * 100, 1)
                    results.append((
                        path,
                        f"{percent}% used ({self.format_bytes(usage.used)} / {self.format_bytes(usage.total)})",
                    ))
                except Exception:
                    continue
        return results

    def get_uptime_linux_style(self):
        """Retourne la sortie brute de uptime quand disponible."""
        try:
            result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
            output = (result.stdout or '').strip()
            if result.returncode == 0 and output:
                return output
        except Exception:
            pass
        return "Impossible de récupérer uptime"

    def build_status_embed(self):
        """Résumé complet du serveur."""
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        temp = self.get_cpu_temp()
        uptime_str = self.format_uptime(int(datetime.now().timestamp() - psutil.boot_time()))

        if cpu < 50:
            color = discord.Color.green()
        elif cpu < 80:
            color = discord.Color.gold()
        else:
            color = discord.Color.red()

        embed = discord.Embed(
            title="📊 Server Status",
            color=color,
            timestamp=datetime.now(),
        )

        embed.add_field(name="🧠 CPU", value=f"**{cpu}%**", inline=True)
        embed.add_field(
            name="💾 RAM",
            value=f"**{mem.percent}%**\n{self.format_bytes(mem.used)} / {self.format_bytes(mem.total)}",
            inline=True,
        )
        embed.add_field(
            name="🌡️ Temp",
            value=f"**{temp}°C**" if temp is not None else "**N/A**",
            inline=True,
        )

        embed.add_field(name="⏱️ Uptime", value=f"**{uptime_str}**", inline=False)

        disk_paths = ["/", "/home", "/mnt/SSD1Tb", "/mnt/wd4tb"]
        disk_lines = [f"**{path}**\n{info}" for path, info in self.get_disk_usage(disk_paths)]
        embed.add_field(
            name="💽 Disques",
            value="\n\n".join(disk_lines[:10]) if disk_lines else "Aucun disque trouvé",
            inline=False,
        )

        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    def build_temp_embed(self):
        """Affiche la température CPU."""
        temp = self.get_cpu_temp()

        if temp is None:
            color = discord.Color.light_grey()
            desc = "Impossible de lire la température."
        elif temp < 60:
            color = discord.Color.green()
            desc = f"Température actuelle: **{temp}°C**"
        elif temp < 75:
            color = discord.Color.gold()
            desc = f"Température actuelle: **{temp}°C**"
        else:
            color = discord.Color.red()
            desc = f"Température actuelle: **{temp}°C**"

        embed = discord.Embed(
            title="🌡️ CPU Temperature",
            description=desc,
            color=color,
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    def build_disk_embed(self):
        """Affiche l'utilisation des disques."""
        disk_paths = ["/", "/home", "/mnt/SSD1Tb", "/mnt/wd4tb"]
        lines = [f"**{path}**\n{info}" for path, info in self.get_disk_usage(disk_paths)]

        embed = discord.Embed(
            title="💽 Disk Usage",
            description="\n\n".join(lines) if lines else "Aucun disque trouvé",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    def build_services_embed(self):
        """Affiche l'état des services systemd suivis."""
        services_to_watch = ["docker", "tailscaled", "qbittorrent-nox"]
        lines = [f"**{svc}** → {self.get_service_status(svc)}" for svc in services_to_watch]

        embed = discord.Embed(
            title="🛠️ Services",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    def build_docker_embed(self):
        """Affiche la liste des conteneurs Docker actifs."""
        if not shutil.which("docker"):
            containers = "Docker non installé"
        else:
            try:
                result = subprocess.run(
                    ["docker", "ps", "--format", "{{.Names}} | {{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                containers = result.stdout.strip() if result.returncode == 0 else (result.stderr.strip() or "Commande échouée")
                if not containers:
                    containers = "Aucun conteneur actif"
            except Exception as e:
                containers = f"Erreur: {e}"

        embed = discord.Embed(
            title="🐳 Docker Containers",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.description = f"```ansi\n{containers[:3500]}\n```"
        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    def build_uptime_embed(self):
        """Affiche l'uptime style Linux/SSH."""
        raw = self.get_uptime_linux_style()

        try:
            parts = raw.split(" up ", 1)
            time_part = parts[0].strip()
            rest = parts[1].strip()

            if " load average: " in rest:
                before_load, load_part = rest.split(" load average: ", 1)
            else:
                before_load, load_part = rest, "N/A, N/A, N/A"

            segments = [seg.strip() for seg in before_load.split(",") if seg.strip()]

            users_part = "N/A"
            uptime_segments = []

            for seg in segments:
                if "user" in seg:
                    users_part = seg
                else:
                    uptime_segments.append(seg)

            uptime_part = ", ".join(uptime_segments) if uptime_segments else "N/A"

            load_values = [x.strip() for x in load_part.split(",")]
            while len(load_values) < 3:
                load_values.append("N/A")

            load1, load5, load15 = load_values[:3]

            try:
                load1_val = float(load1)
                if load1_val < 0.50:
                    color = 0x2ECC71
                    title = "🟢 System Uptime"
                elif load1_val < 1.50:
                    color = 0xF1C40F
                    title = "🟡 System Uptime"
                else:
                    color = 0xE74C3C
                    title = "🔴 System Uptime"
            except ValueError:
                color = 0x0099FF
                title = "⏱️ System Uptime"

            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=datetime.now(),
            )

            embed.add_field(name="🕒 Heure", value=f"**{time_part}**", inline=True)
            embed.add_field(name="⏱️ Uptime", value=f"**{uptime_part}**", inline=True)
            embed.add_field(name="👥 Users", value=f"**{users_part}**", inline=True)

            embed.add_field(
                name="📊 Load Average",
                value=(
                    f"**1m:** {load1}\n"
                    f"**5m:** {load5}\n"
                    f"**15m:** {load15}"
                ),
                inline=False,
            )

            embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
            return embed
        except Exception:
            embed = discord.Embed(
                title="⏱️ System Uptime",
                description=f"```{raw}```",
                color=0x0099FF,
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
            return embed

    def get_local_uptime_info(self):
        """Lit l'uptime, le load average et les users directement depuis la machine locale."""

        try:
            with open("/proc/uptime", "r") as f:
                total_seconds = int(float(f.read().split()[0]))
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            mins = (total_seconds % 3600) // 60
            if days:
                uptime_str = f"{days} {'day' if days == 1 else 'days'}, {hours:02d}:{mins:02d}"
            else:
                uptime_str = f"{hours:02d}:{mins:02d}"
        except Exception:
            uptime_str = "N/A"

        try:
            with open("/proc/loadavg", "r") as f:
                parts = f.read().split()
            la_str = f"{parts[0]}, {parts[1]}, {parts[2]}"
        except Exception:
            la_str = "N/A"

        try:
            result = subprocess.run(
                ["who"], capture_output=True, text=True, timeout=5
            )
            lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
            user_count = len(lines)
        except Exception:
            user_count = 0

        return uptime_str, la_str, user_count

    def get_cpu_temp(self):
        """Lit la température CPU locale."""
        thermal_paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/devices/virtual/thermal/thermal_zone0/temp",
        ]

        for path in thermal_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        raw = f.read().strip()
                    return round(int(raw) / 1000, 1)
                except Exception:
                    pass

        return None

    def get_service_status(self, service_name: str) -> str:
        """Retourne le statut systemd d'un service."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (result.stdout or result.stderr).strip()

            if output == "active":
                return "🟢 Active"
            if output == "inactive":
                return "⚪ Inactive"
            if output == "failed":
                return "🔴 Failed"
            return f"🟡 {output or 'Commande échouée'}"
        except Exception as e:
            return f"🟡 {type(e).__name__}: {e}"

    def get_running_docker_count(self):
        """Compte les conteneurs Docker actifs / total."""
        if not shutil.which("docker"):
            return 0, 0

        try:
            running = subprocess.run(
                ["docker", "ps", "-q"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()

            all_containers = subprocess.run(
                ["docker", "ps", "-aq"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()

            running_count = (
                len([x for x in running.splitlines() if x.strip()]) if running else 0
            )
            total_count = (
                len([x for x in all_containers.splitlines() if x.strip()])
                if all_containers
                else 0
            )
            return running_count, total_count
        except Exception:
            return 0, 0

    def get_local_ip_addresses(self):
        """Retourne les IP locales non loopback detectees sur les interfaces reseau."""
        ip_map = {}

        try:
            for interface_name, addresses in psutil.net_if_addrs().items():
                ips = []
                for address in addresses:
                    family = address.family
                    value = address.address

                    if family == socket.AF_INET and not value.startswith("127."):
                        ips.append(value)
                    elif family == socket.AF_INET6 and value not in ("::1",):
                        ips.append(value.split("%")[0])

                if ips:
                    ip_map[interface_name] = ips
        except Exception:
            return {}

        return ip_map

    def shorten_text(self, text: str, max_length: int = 1024) -> str:
        """Tronque un texte pour respecter les limites Discord."""
        if text is None:
            return "N/A"
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def build_system_embed(self):
        """Affiche les infos systeme rapides."""
        hostname = socket.gethostname()
        os_name = f"{platform.system()} {platform.release()}".strip()
        cpu_name = platform.processor() or platform.machine() or "Inconnu"

        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()

        ip_map = self.get_local_ip_addresses()
        ip_lines = []
        for interface_name, ips in ip_map.items():
            ip_lines.append(f"**{interface_name}**: {', '.join(ips[:2])}")

        embed = discord.Embed(
            title="🖥️ System Overview",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )

        embed.add_field(name="🏷️ Hostname", value=f"`{hostname}`", inline=False)
        embed.add_field(name="🐧 OS", value=self.shorten_text(os_name, 300), inline=False)
        embed.add_field(
            name="🧠 CPU",
            value=self.shorten_text(f"{cpu_name}\nCharge: **{cpu_percent}%**", 500),
            inline=False,
        )
        embed.add_field(
            name="💾 RAM",
            value=(
                f"**{ram.percent}%**\n"
                f"{self.format_bytes(ram.used)} / {self.format_bytes(ram.total)}"
            ),
            inline=True,
        )
        embed.add_field(
            name="🔁 Swap",
            value=(
                f"**{swap.percent}%**\n"
                f"{self.format_bytes(swap.used)} / {self.format_bytes(swap.total)}"
                if swap.total
                else "**0%**\n0 B / 0 B"
            ),
            inline=True,
        )
        embed.add_field(
            name="🌐 IP locales",
            value=self.shorten_text(
                "\n".join(ip_lines) if ip_lines else "Aucune IP locale detectee",
                1000,
            ),
            inline=False,
        )

        embed.set_footer(text=f"{hostname} • Monitoring")
        return embed

    def build_network_embed(self):
        """Affiche l'etat des interfaces reseau."""
        stats_map = psutil.net_if_stats()
        addr_map = psutil.net_if_addrs()
        io_map = psutil.net_io_counters(pernic=True)

        embed = discord.Embed(
            title="🌐 Network Interfaces",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )

        if not stats_map:
            embed.description = "Aucune interface reseau detectee."
            embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
            return embed

        field_count = 0
        hidden_interfaces = 0

        for interface_name in sorted(stats_map):
            if field_count >= 8:
                hidden_interfaces += 1
                continue

            stats = stats_map.get(interface_name)
            addresses = addr_map.get(interface_name, [])
            counters = io_map.get(interface_name)

            state = "🟢 Up" if stats and stats.isup else "🔴 Down"
            speed = f"{stats.speed} Mb/s" if stats and stats.speed > 0 else "N/A"
            mtu = stats.mtu if stats else "N/A"

            ipv4 = []
            ipv6 = []
            mac = None

            for address in addresses:
                family = address.family
                value = address.address

                if family == socket.AF_INET:
                    ipv4.append(value)
                elif family == socket.AF_INET6:
                    ipv6.append(value.split("%")[0])
                elif str(family) in ("AddressFamily.AF_LINK", "17", "18"):
                    mac = value

            io_text = "N/A"
            if counters:
                io_text = (
                    f"RX {self.format_bytes(counters.bytes_recv)} • "
                    f"TX {self.format_bytes(counters.bytes_sent)}"
                )

            value_lines = [
                f"**Etat:** {state}",
                f"**Vitesse:** {speed}",
                f"**MTU:** {mtu}",
                f"**IPv4:** {', '.join(ipv4[:2]) if ipv4 else 'Aucune'}",
                f"**IPv6:** {', '.join(ipv6[:2]) if ipv6 else 'Aucune'}",
                f"**MAC:** {mac or 'N/A'}",
                f"**Trafic:** {io_text}",
            ]

            embed.add_field(
                name=f"🔌 {interface_name}",
                value=self.shorten_text("\n".join(value_lines), 1000),
                inline=False,
            )
            field_count += 1

        if hidden_interfaces:
            embed.add_field(
                name="➕ Interfaces supplementaires",
                value=f"{hidden_interfaces} interface(s) non affichee(s) pour rester dans les limites Discord.",
                inline=False,
            )

        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    async def build_top_embed(self, limit: int = 5):
        """Affiche les processus les plus gourmands en CPU."""
        limit = max(1, min(limit, 10))

        processes = []
        for proc in psutil.process_iter(["pid", "name", "username", "memory_info"]):
            try:
                proc.cpu_percent(None)
                processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        await asyncio.sleep(1)

        process_stats = []
        total_ram = psutil.virtual_memory().total

        for proc in processes:
            try:
                cpu = proc.cpu_percent(None)
                info = proc.info
                mem_info = info.get("memory_info")
                mem_bytes = mem_info.rss if mem_info else 0
                mem_percent = (mem_bytes / total_ram * 100) if total_ram else 0

                process_stats.append(
                    {
                        "pid": info.get("pid", 0),
                        "name": info.get("name") or "Inconnu",
                        "user": info.get("username") or "Inconnu",
                        "cpu": cpu,
                        "mem_bytes": mem_bytes,
                        "mem_percent": mem_percent,
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        process_stats.sort(
            key=lambda proc: (proc["cpu"], proc["mem_percent"]),
            reverse=True,
        )

        top_processes = process_stats[:limit]

        embed = discord.Embed(
            title=f"🔥 Top Processus ({len(top_processes)})",
            color=discord.Color.orange(),
            timestamp=datetime.now(),
        )

        if not top_processes:
            embed.description = "Impossible de recuperer la liste des processus."
            embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
            return embed

        for index, proc in enumerate(top_processes, start=1):
            embed.add_field(
                name=f"{index}. {proc['name']} (PID {proc['pid']})",
                value=(
                    f"**CPU:** {proc['cpu']:.1f}%\n"
                    f"**RAM:** {self.format_bytes(proc['mem_bytes'])} ({proc['mem_percent']:.1f}%)\n"
                    f"**User:** {proc['user']}"
                ),
                inline=False,
            )

        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    def ping_host_quick(self, host: str):
        """Ping rapide d'un host."""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", host],
                capture_output=True,
                text=True,
                timeout=5,
            )

            output = (result.stdout or "") + (result.stderr or "")

            if result.returncode == 0:
                latency = "N/A"
                for line in output.splitlines():
                    if "time=" in line:
                        latency = line.split("time=")[1].split()[0] + " ms"
                        break
                return True, latency

            return False, "Offline"
        except Exception:
            return False, "Erreur"

    def build_health_embed(self):
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        temp = self.get_cpu_temp()
        uptime_str, la_str, user_count = self.get_local_uptime_info()
        running_docker, total_docker = self.get_running_docker_count()

        services_to_watch = [
            "docker",
            "tailscaled",
            "qbittorrent-nox",
        ]

        hosts_to_watch = {
            "Bell": "207.164.234.129",
            "OptiPlex": "192.168.2.113",
            "Raspberry Pi": "192.168.2.50",
        }

        if cpu < 50 and ram.percent < 75 and (temp is None or temp < 65):
            color = discord.Color.green()
            title = "🟢 Health Check"
        elif cpu < 80 and ram.percent < 90 and (temp is None or temp < 75):
            color = discord.Color.gold()
            title = "🟡 Health Check"
        else:
            color = discord.Color.red()
            title = "🔴 Health Check"

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now(),
        )

        embed.add_field(name="🧠 CPU", value=f"**{cpu}%**", inline=True)
        embed.add_field(name="💾 RAM", value=f"**{ram.percent}%**", inline=True)
        embed.add_field(
            name="🌡️ Temp",
            value=f"**{temp}°C**" if temp is not None else "**N/A**",
            inline=True,
        )

        embed.add_field(name="⏱️ Uptime", value=f"**{uptime_str}**", inline=True)
        embed.add_field(name="👤 Users", value=f"**{user_count}**", inline=True)
        embed.add_field(name="📊 Load", value=f"`{la_str}`", inline=True)

        service_lines = [
            f"**{svc}** → {self.get_service_status(svc)}"
            for svc in services_to_watch
        ]
        embed.add_field(
            name="🛠️ Services",
            value="\n".join(service_lines) if service_lines else "Aucun",
            inline=False,
        )

        embed.add_field(
            name="🐳 Docker",
            value=f"**{running_docker}/{total_docker}** conteneurs actifs",
            inline=False,
        )

        host_lines = []
        for label, host in hosts_to_watch.items():
            ok, info = self.ping_host_quick(host)
            status = "🟢 Online" if ok else "🔴 Offline"
            suffix = f" ({info})" if info else ""
            host_lines.append(f"**{label}** → {status}{suffix}")

        embed.add_field(
            name="🌐 Hosts",
            value="\n".join(host_lines) if host_lines else "Aucun host configuré",
            inline=False,
        )

        embed.set_footer(text=f"{socket.gethostname()} • Monitoring")
        return embed

    # Commande déplacée dans cogs/monitoring.py
    async def uptime_command(self, ctx):
        """Affiche l'uptime de la machine locale style SSH Linux."""
        await ctx.send(embed=self.build_uptime_embed())

    # Commande déplacée dans cogs/monitoring.py
    async def system_command(self, ctx):
        """Affiche les infos systeme rapides: hostname, OS, CPU, RAM, swap, IP locales."""
        await ctx.send(embed=self.build_system_embed())

    # Commande déplacée dans cogs/monitoring.py
    async def network_command(self, ctx):
        """Affiche l'etat des interfaces reseau."""
        await ctx.send(embed=self.build_network_embed())

    # Commande déplacée dans cogs/monitoring.py
    async def top_command(self, ctx, limit: int = 5):
        """Affiche les processus les plus gourmands. Usage: .top [1-10]"""
        if limit < 1 or limit > 10:
            await ctx.send("❌ Le nombre doit etre entre 1 et 10.")
            return

        await ctx.send(embed=await self.build_top_embed(limit))

    # Gestion d'erreur déplacée dans cogs/monitoring.py
    async def uptime_command_error(self, ctx, error):
        await ctx.send(f"❌ Erreur uptime: {str(error)}")

    # Gestion d'erreur déplacée dans cogs/monitoring.py
    async def system_command_error(self, ctx, error):
        await ctx.send(f"❌ Erreur system: {str(error)}")

    # Gestion d'erreur déplacée dans cogs/monitoring.py
    async def network_command_error(self, ctx, error):
        await ctx.send(f"❌ Erreur network: {str(error)}")

    # Gestion d'erreur déplacée dans cogs/monitoring.py
    async def top_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Utilisation: `.top [1-10]`")
            return
        await ctx.send(f"❌ Erreur top: {str(error)}")

    # Commande déplacée dans cogs/monitoring.py
    async def health_command(self, ctx):
        """Affiche un résumé santé du serveur."""
        await ctx.send(embed=self.build_health_embed())

    # Gestion d'erreur déplacée dans cogs/monitoring.py
    async def health_command_error(self, ctx, error):
        await ctx.send(f"❌ Erreur health: {str(error)}")

    # Commande déplacée dans cogs/monitoring.py
    async def status_command(self, ctx):
        """Résumé complet du serveur."""
        await ctx.send(embed=self.build_status_embed())

    # Commande déplacée dans cogs/monitoring.py
    async def temps_command(self, ctx):
        """Affiche la température CPU."""
        await ctx.send(embed=self.build_temp_embed())

    # Commande déplacée dans cogs/monitoring.py
    async def disk_command(self, ctx):
        """Affiche l'utilisation des disques."""
        await ctx.send(embed=self.build_disk_embed())

    # Commande déplacée dans cogs/monitoring.py
    async def services_command(self, ctx):
        """Affiche l'état des services systemd."""
        await ctx.send(embed=self.build_services_embed())

    # Commande déplacée dans cogs/monitoring.py
    async def docker_command(self, ctx):
        """Affiche les conteneurs Docker actifs."""
        await ctx.send(embed=self.build_docker_embed())

    @commands.command(name="radarr")
    async def radarr_stats(self, ctx):
        """Affiche les statistiques Radarr"""
        await ctx.send("🎬 Récupération des statistiques Radarr...")

        stats = await self.get_radarr_stats()

        if not stats["success"]:
            embed = discord.Embed(
                title="❌ Erreur Radarr",
                description=f"Impossible de se connecter à Radarr.\n```{stats.get('error', 'Erreur inconnue')}```",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🎬 Statistiques Radarr",
            description=f"**{stats['wanted']} Wanted • {stats['queued']} Queued • {stats['total']} Movies**",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )

        embed.add_field(
            name="🔥 Films manquants",
            value=f"**{stats['wanted']}** films recherchés",
            inline=True,
        )

        embed.add_field(
            name="⏳ En file d'attente",
            value=f"**{stats['queued']}** téléchargements",
            inline=True,
        )

        embed.add_field(
            name="🎞️ Bibliothèque totale",
            value=f"**{stats['total']}** films",
            inline=True,
        )

        embed.set_footer(
            text=f"Radarr • {self.radarr_url}",
            icon_url="https://radarr.video/img/logo.png",
        )
        await ctx.send(embed=embed)

    @commands.command(name="sonarr")
    async def sonarr_stats(self, ctx):
        """Affiche les statistiques Sonarr"""
        await ctx.send("📺 Récupération des statistiques Sonarr...")

        stats = await self.get_sonarr_stats()

        if not stats["success"]:
            embed = discord.Embed(
                title="❌ Erreur Sonarr",
                description=f"Impossible de se connecter à Sonarr.\n```{stats.get('error', 'Erreur inconnue')}```",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📺 Statistiques Sonarr",
            description=f"**{stats['wanted']} Wanted • {stats['queued']} Queued • {stats['total']} Series**",
            color=discord.Color.blue(),
            timestamp=datetime.now(),
        )

        embed.add_field(
            name="🔥 Épisodes manquants",
            value=f"**{stats['wanted']}** épisodes recherchés",
            inline=True,
        )

        embed.add_field(
            name="⏳ En file d'attente",
            value=f"**{stats['queued']}** téléchargements",
            inline=True,
        )

        embed.add_field(
            name="📺 Bibliothèque totale",
            value=f"**{stats['total']}** séries",
            inline=True,
        )

        embed.set_footer(
            text=f"Sonarr • {self.sonarr_url}",
            icon_url="https://sonarr.tv/img/logo.png",
        )
        await ctx.send(embed=embed)

    @commands.command(name="lastmovie", aliases=["latest_movies", "films"])
    async def latest_movies_command(self, ctx, nombre: int = 1):
        """Affiche le dernier film ajouté !lastmovie [nombre]"""
        if nombre < 1 or nombre > 10:
            await ctx.send("❌ Le nombre doit être entre 1 et 10.")
            return

        await ctx.send("🎬 Récupération des derniers films...")

        movies = await self.get_latest_movies(nombre)

        if movies is None:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Impossible de se connecter à Jellyfin. Vérifiez la configuration.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        if not movies:
            embed = discord.Embed(
                title="🎞️ Aucun film trouvé",
                description="Aucun film n'a été trouvé sur votre serveur Jellyfin.",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed)
            return

        if nombre == 1:
            movie = movies[0]
            movie_info = self.format_movie_info(movie)

            embed = discord.Embed(
                title=f"🎬 {movie_info['title']} ({movie_info['year']})",
                description=movie_info["full_overview"],
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            embed.add_field(name="🎭 Genres", value=movie_info["genres"], inline=True)
            if movie_info["rating"]:
                embed.add_field(name="📊 Note", value=movie_info["rating"], inline=True)
            embed.add_field(
                name="📅 Ajouté le", value=movie_info["date_added"], inline=True
            )

            if movie.get("ImageTags", {}).get("Primary"):
                poster_url = self.get_image_url(movie["Id"])
                embed.set_image(url=poster_url)

            embed.set_footer(
                text="Jellyfin Bot",
                icon_url="https://jellyfin.org/images/favicon.ico",
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"🎬 Les {len(movies)} derniers films ajoutés",
                description=f"Sur le serveur Jellyfin: `{self.jellyfin_url}`",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            for i, movie in enumerate(movies, 1):
                movie_info = self.format_movie_info(movie)

                field_name = (
                    f"{i}. {movie_info['title']} ({movie_info['year']})"
                    f"{movie_info['rating']}"
                )
                field_value = f"**Genres:** {movie_info['genres']}\n"
                field_value += f"**Ajouté le:** {movie_info['date_added']}\n"
                field_value += f"**Description:** {movie_info['overview']}"

                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False,
                )

            embed.set_footer(
                text="Jellyfin Bot",
                icon_url="https://jellyfin.org/images/favicon.ico",
            )
            await ctx.send(embed=embed)

    @commands.command(name="lastseries", aliases=["latest_series", "series"])
    async def latest_series_command(self, ctx, nombre: int = 1):
        """Affiche la dernière série ajoutée: !lastseries [nombre]"""
        if nombre < 1 or nombre > 10:
            await ctx.send("❌ Le nombre doit être entre 1 et 10.")
            return

        await ctx.send("📺 Récupération des dernières séries...")

        series = await self.get_latest_series(nombre)

        if series is None:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Impossible de se connecter à Jellyfin. Vérifiez la configuration.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        if not series:
            embed = discord.Embed(
                title="📺 Aucune série trouvée",
                description="Aucune série n'a été trouvée sur votre serveur Jellyfin.",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed)
            return

        if nombre == 1:
            show = series[0]
            series_info = self.format_series_info(show)

            embed = discord.Embed(
                title=f"📺 {series_info['title']} ({series_info['year']})",
                description=series_info["full_overview"],
                color=discord.Color.purple(),
                timestamp=datetime.now(),
            )

            embed.add_field(name="🎭 Genres", value=series_info["genres"], inline=True)
            if series_info["rating"]:
                embed.add_field(
                    name="📊 Note", value=series_info["rating"], inline=True
                )
            embed.add_field(
                name="📅 Ajouté le", value=series_info["date_added"], inline=True
            )

            if show.get("ImageTags", {}).get("Primary"):
                poster_url = self.get_image_url(show["Id"])
                embed.set_image(url=poster_url)

            embed.set_footer(
                text="Jellyfin Bot",
                icon_url="https://jellyfin.org/images/favicon.ico",
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"📺 Les {len(series)} dernières séries ajoutées",
                description=f"Sur le serveur Jellyfin: `{self.jellyfin_url}`",
                color=discord.Color.purple(),
                timestamp=datetime.now(),
            )

            for i, show in enumerate(series, 1):
                series_info = self.format_series_info(show)

                field_name = (
                    f"{i}. {series_info['title']} ({series_info['year']})"
                    f"{series_info['rating']}"
                )
                field_value = f"**Genres:** {series_info['genres']}\n"
                field_value += f"**Ajouté le:** {series_info['date_added']}\n"
                field_value += f"**Description:** {series_info['overview']}"

                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False,
                )

            embed.set_footer(
                text="Jellyfin Bot",
                icon_url="https://jellyfin.org/images/favicon.ico",
            )
            await ctx.send(embed=embed)

    async def get_watch_stats(self, days: int = 7):
        """Récupère les statistiques de visionnage des X derniers jours"""
        headers = {"X-Emby-Token": self.api_key}
        url = f"{self.jellyfin_url}/user_usage_stats/user_activity"
        params = {
            "days": days,
            "end_date": datetime.now().strftime("%Y-%m-%d"),
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url, headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data, True
                    else:
                        return None, False
            except Exception as e:
                print(f"Erreur stats: {e}")
                return None, False

    async def get_watch_stats_fallback(self, days: int = 7):
        """Récupère les stats depuis le log d'activité natif de Jellyfin"""
        headers = {"X-Emby-Token": self.api_key}
        url = f"{self.jellyfin_url}/System/ActivityLog/Entries"
        min_date = (datetime.now() - timedelta(days=days)).strftime(
            "%Y-%m-%dT00:00:00.000Z"
        )
        params = {
            "startIndex": 0,
            "limit": 1000,
            "hasUserId": "true",
            "minDate": min_date,
        }

        PLAY_KEYWORDS = ("playback", "play", "lecture", "stream", "watched")

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        entries = data.get("Items", [])
                        print(
                            f"[jellyfin stats] {len(entries)} entrées récupérées sur {days} jours"
                        )

                        play_events = [
                            e
                            for e in entries
                            if any(
                                kw in e.get("Type", "").lower()
                                for kw in PLAY_KEYWORDS
                            )
                            or any(
                                kw in e.get("Name", "").lower()
                                for kw in PLAY_KEYWORDS
                            )
                        ]

                        print(
                            f"[jellyfin stats] {len(play_events)} événements de lecture filtrés"
                        )

                        if play_events:
                            pe = play_events[0]
                            print(f"[jellyfin stats] Clés: {list(pe.keys())}")
                            print(
                                f"[jellyfin stats] Type={pe.get('Type')} | Name={pe.get('Name')} | UserName={pe.get('UserName')} | UserId={pe.get('UserId')} | ShortOverview={pe.get('ShortOverview')}"
                            )

                        user_counts = {}
                        for e in play_events:
                            user = e.get("UserName") or None
                            if not user:
                                short = e.get("ShortOverview", "")
                                if short:
                                    user = short.split(" ")[0]
                            user = user or "Inconnu"
                            user_counts[user] = user_counts.get(user, 0) + 1

                        return {
                            "total_plays": len(play_events),
                            "total_entries": len(entries),
                            "user_counts": user_counts,
                            "days": days,
                        }, True
                    else:
                        body = await response.text()
                        print(
                            f"[jellyfin stats] Erreur HTTP {response.status}: {body[:200]}"
                        )
                        return None, False
            except Exception as e:
                print(f"[jellyfin stats] Exception: {type(e).__name__}: {e}")
                return None, False

    async def get_jellyfin_library_stats(self, days: int | None = None):
        """Récupère le nombre de films, series et episodes dans Jellyfin."""
        user_id = await self.get_jellyfin_user_id()
        if not user_id:
            return None, False

        url = f"{self.jellyfin_url}/Users/{user_id}/Items"
        headers = {"X-Emby-Token": self.api_key}
        connector = aiohttp.TCPConnector(ssl=False)

        params = {
            "Recursive": "true",
            "Fields": "DateCreated",
            "Limit": 1,
        }

        if days is not None:
            min_date = (datetime.utcnow() - timedelta(days=days)).strftime(
                "%Y-%m-%dT00:00:00.0000000Z"
            )
            params["MinDateLastSavedForUser"] = min_date

        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                stats = {}
                for item_type in ("Movie", "Series", "Episode"):
                    current_params = {
                        **params,
                        "IncludeItemTypes": item_type,
                    }
                    async with session.get(
                        url,
                        headers=headers,
                        params=current_params,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as response:
                        if response.status != 200:
                            body = await response.text()
                            print(
                                f"[jellyfin library stats] Erreur HTTP {response.status} pour {item_type}: {body[:200]}"
                            )
                            return None, False

                        data = await response.json()
                        stats[item_type.lower()] = data.get("TotalRecordCount", 0)

                return stats, True
            except Exception as e:
                print(
                    f"[jellyfin library stats] Exception: {type(e).__name__}: {e}"
                )
                return None, False

    def resolve_stats_period(self, period: str):
        """Convertit une periode textuelle en nombre de jours."""
        if period is None:
            return 7, "week", "7 derniers jours"

        normalized = str(period).strip().lower()
        period_map = {
            "day": (1, "day", "dernier jour"),
            "jour": (1, "day", "dernier jour"),
            "1d": (1, "day", "dernier jour"),
            "week": (7, "week", "7 derniers jours"),
            "semaine": (7, "week", "7 derniers jours"),
            "7d": (7, "week", "7 derniers jours"),
            "month": (30, "month", "30 derniers jours"),
            "mois": (30, "month", "30 derniers jours"),
            "30d": (30, "month", "30 derniers jours"),
        }

        if normalized in period_map:
            return period_map[normalized]

        if normalized.isdigit():
            days = int(normalized)
            if 1 <= days <= 30:
                label = "dernier jour" if days == 1 else f"{days} derniers jours"
                return days, normalized, label

        return None, None, None

    @commands.group(name="jellyfin", invoke_without_command=True)
    async def jellyfin_group(self, ctx):
        """Commandes Jellyfin — sous-commandes: view, stats"""
        embed = discord.Embed(
            title="📡 Jellyfin — Aide",
            description=(
                "**Sous-commandes disponibles :**\n\n"
                "`.jellyfin view` — Streams actifs en ce moment\n"
                "`.jellyfin stats day` — Statistiques du dernier jour\n"
                "`.jellyfin stats week` — Statistiques des 7 derniers jours\n"
                "`.jellyfin stats month` — Statistiques des 30 derniers jours"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(
            text="Jellyfin Bot",
            icon_url="https://jellyfin.org/images/favicon.ico",
        )
        await ctx.send(embed=embed)

    @jellyfin_group.command(name="view")
    async def jellyfin_view(self, ctx):
        """Affiche les streams actifs sur Jellyfin: !jellyfin view"""
        await ctx.send("📡 Récupération des streams actifs...")

        streams, success = await self.get_active_streams()

        if not success:
            embed = discord.Embed(
                title="❌ Erreur Jellyfin",
                description="Impossible de récupérer les sessions. Vérifiez la configuration.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        if not streams:
            embed = discord.Embed(
                title="📡 Streams Jellyfin",
                description="Aucun stream actif en ce moment.",
                color=discord.Color.orange(),
                timestamp=datetime.now(),
            )
            embed.set_footer(
                text="Jellyfin Bot",
                icon_url="https://jellyfin.org/images/favicon.ico",
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title=f"📡 Streams actifs — {len(streams)} en cours",
            description=f"Serveur: `{self.jellyfin_url}`",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )

        for stream in streams:
            info = self.format_stream_info(stream)
            field_value = (
                f"{info['status']} • {info['quality']}\n"
                f"👤 **{info['user']}** sur {info['client']} ({info['device']})\n"
                f"⏱️ {info['progress']}"
            )
            embed.add_field(
                name=f"🎬 {info['display_title']}",
                value=field_value,
                inline=False,
            )

        embed.set_footer(
            text="Jellyfin Bot",
            icon_url="https://jellyfin.org/images/favicon.ico",
        )
        await ctx.send(embed=embed)

    @jellyfin_group.command(name="stats")
    async def jellyfin_stats(self, ctx, period: str = "week"):
        """Statistiques Jellyfin: .jellyfin stats <day|week|month>"""
        days, _, label = self.resolve_stats_period(period)
        if days is None:
            await ctx.send(
                "❌ Periode invalide. Utilisez `.jellyfin stats day`, `.jellyfin stats week` ou `.jellyfin stats month`."
            )
            return

        await ctx.send(f"📊 Récupération des statistiques des {label}...")

        stats, success = await self.get_watch_stats_fallback(days)
        library_stats, library_success = await self.get_jellyfin_library_stats()
        period_library_stats, period_library_success = await self.get_jellyfin_library_stats(
            days
        )

        if not success or stats is None:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Impossible de récupérer les statistiques depuis Jellyfin.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        total_plays = stats.get("total_plays", 0)
        user_counts = stats.get("user_counts", {})

        embed = discord.Embed(
            title=f"📊 Stats Jellyfin — {label}",
            description=f"Serveur: `{self.jellyfin_url}`",
            color=discord.Color.teal(),
            timestamp=datetime.now(),
        )

        embed.add_field(
            name="🎬 Total lectures",
            value=f"**{total_plays}** événements de lecture",
            inline=False,
        )

        if library_success and library_stats:
            embed.add_field(
                name="🎞️ Bibliothèque totale",
                value=(
                    f"**Films:** {library_stats.get('movie', 0)}\n"
                    f"**Series:** {library_stats.get('series', 0)}\n"
                    f"**Episodes:** {library_stats.get('episode', 0)}"
                ),
                inline=True,
            )

        if period_library_success and period_library_stats:
            embed.add_field(
                name=f"🆕 Ajouts sur {label}",
                value=(
                    f"**Films:** {period_library_stats.get('movie', 0)}\n"
                    f"**Series:** {period_library_stats.get('series', 0)}\n"
                    f"**Episodes:** {period_library_stats.get('episode', 0)}"
                ),
                inline=True,
            )

        if user_counts:
            sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
            user_lines = "\n".join(
                f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else '👤'} **{user}** — {count} lecture{'s' if count > 1 else ''}"
                for i, (user, count) in enumerate(sorted_users)
            )
            embed.add_field(
                name="👥 Activité par utilisateur",
                value=user_lines or "Aucune donnée",
                inline=False,
            )
        else:
            embed.add_field(
                name="👥 Activité par utilisateur",
                value="Aucune activité enregistrée sur cette période.",
                inline=False,
            )

        embed.set_footer(
            text=f"Jellyfin Bot • Période: {label}",
            icon_url="https://jellyfin.org/images/favicon.ico",
        )
        await ctx.send(embed=embed)

    @jellyfin_group.error
    async def jellyfin_group_error(self, ctx, error):
        await ctx.send(f"❌ Une erreur s'est produite: {str(error)}")

    @commands.command(name="config_jellyfin")
    @require_admin()
    async def config_jellyfin(self, ctx, url: str = None, api_key: str = None):
        """Configuration Jellyfin: !config_jellyfin <url> <api_key>"""
        if url:
            self.jellyfin_url = url.rstrip("/")
        if api_key:
            self.api_key = api_key
            self.user_id = None

        embed = discord.Embed(
            title="⚙️ Configuration mise à jour",
            description=f"**URL Jellyfin:** `{self.jellyfin_url}`\n**API Key:** `{'*' * len(self.api_key) if self.api_key else 'Non définie'}`",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="test_jellyfin")
    @require_admin()
    async def test_jellyfin(self, ctx):
        """Teste la connexion à Jellyfin"""
        await ctx.send("🔍 Test de connexion à Jellyfin...")

        user_id = await self.get_jellyfin_user_id()
        if user_id:
            embed = discord.Embed(
                title="✅ Connexion réussie",
                description=f"Connecté à Jellyfin sur `{self.jellyfin_url}`\nUtilisateur ID: `{user_id}`",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Échec de la connexion",
                description="Vérifiez l'URL du serveur et la clé API.",
                color=discord.Color.red(),
            )

        await ctx.send(embed=embed)

    @latest_movies_command.error
    async def latest_movies_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Veuillez fournir un nombre valide.")
        else:
            await ctx.send(f"❌ Une erreur s'est produite: {str(error)}")

    @latest_series_command.error
    async def latest_series_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Veuillez fournir un nombre valide.")
        else:
            await ctx.send(f"❌ Une erreur s'est produite: {str(error)}")

    @config_jellyfin.error
    async def config_jellyfin_error(self, ctx, error):
        if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
            await ctx.send(
                "❌ Vous devez être administrateur pour utiliser cette commande."
            )

    @test_jellyfin.error
    async def test_jellyfin_error(self, ctx, error):
        if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
            await ctx.send(
                "❌ Vous devez être administrateur pour utiliser cette commande."
            )


async def setup(bot):
    await bot.add_cog(Servarr(bot))
