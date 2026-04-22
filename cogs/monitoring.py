import asyncio
import json
import logging
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime

import aiohttp
import discord
import psutil
from discord.ext import commands
import config
from utils.permissions import require_admin


logger = logging.getLogger(__name__)


class Monitoring(commands.Cog):
    """Commandes de monitoring système pour PythonBot."""

    def __init__(self, bot):
        self.bot = bot

        # Configuration Beszel
        self.beszel_url = getattr(config, "BESZEL_URL", None) or os.getenv("BESZEL_URL")
        self.beszel_email = getattr(config, "BESZEL_EMAIL", None) or os.getenv("BESZEL_EMAIL")
        self.beszel_password = getattr(config, "BESZEL_PASSWORD", None) or os.getenv("BESZEL_PASSWORD")
        self._beszel_token = None

        self.services_to_watch = [
            "docker",
            "tailscaled",
            "qbittorrent-nox",
        ]
        self.disk_paths = [
            "/",
            "/home",
            "/mnt/SSD1Tb",
            "/mnt/wd4tb",
        ]
        self.health_hosts = {
            "Bell": "207.164.234.129",
            "OptiPlex": "192.168.2.113",
            "Raspberry Pi": "192.168.2.50",
        }

    def run_cmd(self, command: list[str], timeout: int = 10) -> str:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return result.stderr.strip() or "Commande échouée"
        except Exception as e:
            return f"Erreur: {e}"

    def format_bytes(self, num: float) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if num < 1024:
                return f"{num:.1f} {unit}"
            num /= 1024
        return f"{num:.1f} PB"

    def format_uptime(self, seconds):
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

    def shorten_text(self, text: str, max_length: int = 1024) -> str:
        if text is None:
            return "N/A"
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def get_cpu_temp(self):
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

    def get_temperature_readings(self):
        readings = []

        try:
            if hasattr(psutil, "sensors_temperatures"):
                sensors = psutil.sensors_temperatures() or {}
                for entries in sensors.values():
                    for entry in entries:
                        current = getattr(entry, "current", None)
                        if current is not None:
                            readings.append(round(float(current), 1))
        except Exception:
            pass

        if readings:
            return readings

        temp = self.get_cpu_temp()
        return [temp] if temp is not None else []

    def get_uptime_linux_style(self):
        uptime_output = self.run_cmd(["uptime"], timeout=5)
        if uptime_output and not uptime_output.startswith("Erreur"):
            return uptime_output
        return "Impossible de récupérer uptime"

    def get_local_uptime_info(self):
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
            result = subprocess.run(["who"], capture_output=True, text=True, timeout=5)
            lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
            user_count = len(lines)
        except Exception:
            user_count = 0

        return uptime_str, la_str, user_count

    def get_disk_usage(self):
        results = []
        for path in self.disk_paths:
            if os.path.exists(path):
                try:
                    usage = shutil.disk_usage(path)
                    percent = round((usage.used / usage.total) * 100, 1)
                    results.append(
                        (
                            path,
                            f"{percent}% used ({self.format_bytes(usage.used)} / {self.format_bytes(usage.total)})",
                        )
                    )
                except Exception:
                    continue
        return results

    def get_service_status(self, service_name: str) -> str:
        result = self.run_cmd(["systemctl", "is-active", service_name], timeout=5)
        if result == "active":
            return "🟢 Active"
        if result == "inactive":
            return "⚪ Inactive"
        if result == "failed":
            return "🔴 Failed"
        return f"🟡 {result}"

    def get_docker_containers(self):
        if not shutil.which("docker"):
            return "Docker non installé"
        output = self.run_cmd(
            ["docker", "ps", "--format", "{{.Names}} | {{.Status}}"],
            timeout=10,
        )
        return output or "Aucun conteneur actif"

    def get_running_docker_count(self):
        if not shutil.which("docker"):
            return 0, 0

        running = self.run_cmd(["docker", "ps", "-q"], timeout=5)
        all_containers = self.run_cmd(["docker", "ps", "-aq"], timeout=5)
        running_count = len([x for x in running.splitlines() if x.strip()]) if running else 0
        total_count = len([x for x in all_containers.splitlines() if x.strip()]) if all_containers else 0
        return running_count, total_count

    def get_updates_output(self):
        update_cmd = self.run_cmd(["apt", "list", "--upgradable"], timeout=20)
        if update_cmd.startswith("Erreur:"):
            return [], update_cmd

        packages = []
        for line in update_cmd.splitlines():
            if not line or line.startswith("Listing..."):
                continue
            packages.append(line.strip())

        return packages, update_cmd

    def get_journal_output(self, service_name: str, lines: int = 50):
        safe_service = service_name.strip()
        if not safe_service or not all(c.isalnum() or c in "_.@:-" for c in safe_service):
            raise RuntimeError("Nom de service invalide")

        lines = max(5, min(lines, 100))
        return self.run_cmd(
            ["journalctl", "-u", safe_service, "-n", str(lines), "--no-pager", "--output", "short-iso"],
            timeout=15,
        )

    def truncate_output(self, text: str, limit: int = 3800):
        text = text.strip() or "Aucune sortie."
        if len(text) <= limit:
            return text
        return text[: limit - 80].rstrip() + "\n\n... sortie tronquée ..."

    def format_code_output(self, text: str, language: str = ""):
        safe_text = self.truncate_output(text).replace("```", "'''")
        return f"```{language}\n{safe_text}\n```"

    def ping_host_quick(self, host: str):
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

    def get_local_ip_addresses(self):
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

    async def get_beszel_token(self):
        if self._beszel_token:
            return self._beszel_token

        url = f"{self.beszel_url}/api/collections/users/auth-with-password"
        payload = {"identity": self.beszel_email, "password": self.beszel_password}

        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        data = json.loads(body)
                        self._beszel_token = data["token"]
                        return self._beszel_token
                    logger.error(f"[beszel] Auth HTTP {resp.status}: {body[:300]}")
                    return None
            except Exception as e:
                logger.error(f"[beszel] EXCEPTION: {type(e).__name__}: {e}")
                return None

    async def get_beszel_systems(self):
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
                    if resp.status == 401:
                        self._beszel_token = None
                        return None
                    logger.error(f"[beszel] Erreur HTTP {resp.status}")
                    return None
            except Exception as e:
                logger.error(f"[beszel] Exception get_systems: {e}")
                return None

    def build_status_embed(self):
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
            title="📊 PythonBot Status",
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

        disk_lines = [f"**{path}**\n{info}" for path, info in self.get_disk_usage()]
        embed.add_field(
            name="💽 Disques",
            value="\n\n".join(disk_lines[:10]) if disk_lines else "Aucun disque trouvé",
            inline=False,
        )

        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_temp_embed(self):
        readings = self.get_temperature_readings()
        temp = readings[0] if readings else None

        if temp is None:
            color = discord.Color.light_grey()
            desc = "Impossible de lire la température."
        elif temp < 60:
            color = discord.Color.green()
        elif temp < 75:
            color = discord.Color.gold()
        else:
            color = discord.Color.red()

        embed = discord.Embed(
            title="🌡️ CPU Temperature",
            description=desc if temp is None else None,
            color=color,
            timestamp=datetime.now(),
        )

        if readings:
            max_temp = max(readings)
            avg_temp = sum(readings) / len(readings)
            embed.add_field(name="🌡️ Actuelle", value=f"**{temp}°C**", inline=True)
            embed.add_field(name="🔥 Max", value=f"**{max_temp}°C**", inline=True)
            embed.add_field(name="📊 Moyenne", value=f"**{avg_temp:.1f}°C**", inline=True)
            embed.add_field(name="📡 Capteurs", value=f"**{len(readings)}** détecté(s)", inline=False)

        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_disk_embed(self):
        lines = [f"**{path}**\n{info}" for path, info in self.get_disk_usage()]

        embed = discord.Embed(
            title="💽 Disk Usage",
            description="\n\n".join(lines) if lines else "Aucun disque trouvé",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_services_embed(self):
        lines = [f"**{svc}** → {self.get_service_status(svc)}" for svc in self.services_to_watch]

        embed = discord.Embed(
            title="🛠️ Services",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_docker_embed(self):
        containers = self.get_docker_containers()

        embed = discord.Embed(
            title="🐳 Docker Containers",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.description = f"```ansi\n{containers[:3500]}\n```"
        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_uptime_embed(self):
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
                value=f"**1m:** {load1}\n**5m:** {load5}\n**15m:** {load15}",
                inline=False,
            )
            embed.set_footer(text="PythonBot Monitoring")
            return embed
        except Exception:
            embed = discord.Embed(
                title="⏱️ System Uptime",
                description=f"```{raw}```",
                color=0x0099FF,
                timestamp=datetime.now(),
            )
            embed.set_footer(text="PythonBot Monitoring")
            return embed

    def build_health_embed(self):
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        temp = self.get_cpu_temp()
        uptime_str, la_str, user_count = self.get_local_uptime_info()
        running_docker, total_docker = self.get_running_docker_count()

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
        user_label = f"{user_count} {'user' if user_count == 1 else 'users'}"
        embed.add_field(name="👥 Users", value=f"**{user_label}**", inline=True)
        embed.add_field(name="📊 Load", value=f"`{la_str}`", inline=True)

        service_lines = [f"**{svc}** → {self.get_service_status(svc)}" for svc in self.services_to_watch]
        embed.add_field(name="🛠️ Services", value="\n".join(service_lines) if service_lines else "Aucun", inline=False)

        embed.add_field(
            name="🐳 Docker",
            value=f"**{running_docker}/{total_docker}** conteneurs actifs",
            inline=False,
        )

        host_lines = []
        for label, host in self.health_hosts.items():
            ok, info = self.ping_host_quick(host)
            status = "🟢 Online" if ok else "🔴 Offline"
            suffix = f" ({info})" if info else ""
            host_lines.append(f"**{label}** → {status}{suffix}")

        embed.add_field(
            name="🌐 Hosts",
            value="\n".join(host_lines) if host_lines else "Aucun host configuré",
            inline=False,
        )
        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_system_embed(self):
        hostname = socket.gethostname()
        os_name = f"{platform.system()} {platform.release()}".strip()
        cpu_name = platform.processor() or platform.machine() or "Inconnu"
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()

        ip_map = self.get_local_ip_addresses()
        ip_lines = [f"**{interface}**: {', '.join(ips[:2])}" for interface, ips in ip_map.items()]

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
            value=f"**{ram.percent}%**\n{self.format_bytes(ram.used)} / {self.format_bytes(ram.total)}",
            inline=True,
        )
        embed.add_field(
            name="🔁 Swap",
            value=(
                f"**{swap.percent}%**\n{self.format_bytes(swap.used)} / {self.format_bytes(swap.total)}"
                if swap.total
                else "**0%**\n0 B / 0 B"
            ),
            inline=True,
        )
        embed.add_field(
            name="🌐 IP locales",
            value=self.shorten_text("\n".join(ip_lines) if ip_lines else "Aucune IP locale détectée", 1000),
            inline=False,
        )
        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_network_embed(self):
        stats_map = psutil.net_if_stats()
        addr_map = psutil.net_if_addrs()
        io_map = psutil.net_io_counters(pernic=True)

        embed = discord.Embed(
            title="🌐 Network Interfaces",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )

        if not stats_map:
            embed.description = "Aucune interface réseau détectée."
            embed.set_footer(text="PythonBot Monitoring")
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
                io_text = f"RX {self.format_bytes(counters.bytes_recv)} • TX {self.format_bytes(counters.bytes_sent)}"

            value_lines = [
                f"**État:** {state}",
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
                name="➕ Interfaces supplémentaires",
                value=f"{hidden_interfaces} interface(s) non affichée(s) pour rester dans les limites Discord.",
                inline=False,
            )

        embed.set_footer(text="PythonBot Monitoring")
        return embed

    async def build_top_embed(self, limit: int = 5):
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

        process_stats.sort(key=lambda proc: (proc["cpu"], proc["mem_percent"]), reverse=True)
        top_processes = process_stats[:limit]

        embed = discord.Embed(
            title=f"🔥 Top Processus ({len(top_processes)})",
            color=discord.Color.orange(),
            timestamp=datetime.now(),
        )

        if not top_processes:
            embed.description = "Impossible de récupérer la liste des processus."
            embed.set_footer(text="PythonBot Monitoring")
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

        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_update_embed(self):
        packages, raw_output = self.get_updates_output()

        if raw_output.startswith("Erreur:"):
            raise RuntimeError(raw_output)

        color = 0x2ECC71 if not packages else 0xF1C40F
        embed = discord.Embed(
            title="📦 APT Updates",
            color=color,
            timestamp=datetime.now(),
        )

        if not packages:
            embed.description = "✅ Aucun paquet à mettre à jour."
        else:
            shown = packages[:20]
            extra = len(packages) - len(shown)
            description = "\n".join(f"• `{pkg.split('/')[0]}`" for pkg in shown)
            if extra > 0:
                description += f"\n\n... et **{extra}** autre(s) paquet(s)."

            embed.description = description
            embed.add_field(name="Paquets disponibles", value=f"**{len(packages)}**", inline=True)

        embed.set_footer(text="PythonBot Monitoring")
        return embed

    def build_journal_embed(self, service_name: str, lines: int = 50):
        output = self.get_journal_output(service_name, lines)

        embed = discord.Embed(
            title=f"🧾 Journal: {service_name}",
            description=self.format_code_output(output),
            color=0x0099FF,
            timestamp=datetime.now(),
        )
        embed.set_footer(text="PythonBot Monitoring")
        return embed

    @commands.command(name="beszel", aliases=["servers", "systemes"])
    async def beszel_status(self, ctx):
        await ctx.send("🖥️ Récupération des systèmes Beszel...")
        systems = await self.get_beszel_systems()

        if systems is None:
            embed = discord.Embed(
                title="❌ Erreur Beszel",
                description="Impossible de joindre l'API Beszel. Vérifiez l'URL, l'email et le mot de passe.",
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
            description=f"🟢 **{up_count}** en ligne • 🔴 **{down_count}** hors ligne",
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
            mem_str = "N/A"
            if mem_pct is not None and mem_total:
                mem_used = mem_total * mem_pct / 100
                mem_str = f"{mem_used:.1f} / {mem_total:.0f} GB ({mem_pct:.0f}%)"

            la = info.get("la", [])
            la_str = f"{la[0]} / {la[1]} / {la[2]}" if la and len(la) >= 3 else "N/A"
            disk_pct = info.get("dp")
            disk_str = f"{disk_pct:.1f}%" if disk_pct is not None else "N/A"

            value = (
                f"🔗 `{host}`\n"
                f"⏱️ Uptime: **{uptime}**\n"
                f"⚙️ CPU: **{cpu_str}** • Load: `{la_str}`\n"
                f"🧠 RAM: **{mem_str}**\n"
                f"💾 Disk: **{disk_str}**"
            )
            embed.add_field(name=f"{emoji} {name}", value=value, inline=True)

        embed.set_footer(text=f"Beszel • {self.beszel_url}")
        await ctx.send(embed=embed)

    @commands.command(name="beszel_debug")
    @commands.has_permissions(administrator=True)
    async def beszel_debug(self, ctx):
        url_auth = f"{self.beszel_url}/api/collections/users/auth-with-password"
        payload = {"identity": self.beszel_email, "password": self.beszel_password}
        await ctx.send(f"🔍 Test: `{url_auth}`")

        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(
                    url_auth,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    body = await resp.text()
                    icon = "✅" if resp.status == 200 else "❌"
                    await ctx.send(f"{icon} **Auth:** `{resp.status}`\n```json\n{body[:400]}\n```")
            except Exception as e:
                await ctx.send(f"❌ **Exception:** `{type(e).__name__}: {e}`")

    @commands.command(name="status")
    async def status_command(self, ctx):
        await ctx.send(embed=self.build_status_embed())

    @commands.command(name="temps")
    async def temps_command(self, ctx):
        await ctx.send(embed=self.build_temp_embed())

    @commands.command(name="disk")
    async def disk_command(self, ctx):
        await ctx.send(embed=self.build_disk_embed())

    @commands.command(name="services")
    async def services_command(self, ctx):
        await ctx.send(embed=self.build_services_embed())

    @commands.command(name="docker")
    async def docker_command(self, ctx):
        await ctx.send(embed=self.build_docker_embed())

    @commands.command(name="uptime")
    async def uptime_command(self, ctx):
        await ctx.send(embed=self.build_uptime_embed())

    @commands.command(name="health")
    async def health_command(self, ctx):
        await ctx.send(embed=self.build_health_embed())

    @commands.command(name="system")
    async def system_command(self, ctx):
        await ctx.send(embed=self.build_system_embed())

    @commands.command(name="network")
    async def network_command(self, ctx):
        await ctx.send(embed=self.build_network_embed())

    @commands.command(name="top")
    async def top_command(self, ctx, limit: int = 5):
        if limit < 1 or limit > 10:
            await ctx.send("❌ Le nombre doit être entre 1 et 10.")
            return
        await ctx.send(embed=await self.build_top_embed(limit))

    @commands.command(name="update")
    @require_admin()
    async def update_command(self, ctx):
        try:
            async with ctx.typing():
                embed = await asyncio.to_thread(self.build_update_embed)
            await ctx.send(embed=embed)
        except RuntimeError as e:
            await ctx.send(f"❌ {e}")

    @commands.command(name="journal")
    @require_admin()
    async def journal_command(self, ctx, service: str = None, lines: int = 50):
        if not service:
            await ctx.send("❌ Syntaxe : `.journal <service> [lignes]`")
            return

        try:
            lines = max(5, min(lines, 100))
            async with ctx.typing():
                embed = await asyncio.to_thread(self.build_journal_embed, service, lines)
            await ctx.send(embed=embed)
        except RuntimeError as e:
            await ctx.send(f"❌ {e}")

    @top_command.error
    async def top_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Utilisation: `.top [1-10]`")
            return
        await ctx.send(f"❌ Erreur top: {str(error)}")


async def setup(bot):
    await bot.add_cog(Monitoring(bot))
