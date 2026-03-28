import discord
from discord.ext import commands
import asyncio
import aiohttp
import json
import os
import socket
import struct
from typing import Dict, Optional, List

class Assetto(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.servers_file = "monitored_servers.json"
        self.servers = self.load_servers()

    def load_servers(self) -> Dict[str, Dict]:
        if os.path.exists(self.servers_file):
            try:
                with open(self.servers_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}

    def save_servers(self):
        try:
            with open(self.servers_file, 'w', encoding='utf-8') as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")

    async def query_server_udp_multiple(self, ip: str, base_port: int) -> Optional[Dict]:
        """
        Essaie plusieurs ports UDP avec une meilleure gestion des protocoles AC
        """
        ports_to_try = [
            base_port,           # Port exact
            base_port + 1,       # Port +1
            base_port - 1,       # Port -1
            9600,               # Port par défaut AC
            9601,               # Port alternatif courant
            base_port + 96,     # Parfois décalé
            base_port + 100,    # Autre décalage
        ]
        
        for port in ports_to_try:
            try:
                result = await self._query_udp_single(ip, port)
                if result and result.get("name") != "Serveur AC":  # Éviter les réponses génériques
                    print(f"✅ Succès UDP sur {ip}:{port}")
                    return result
            except Exception as e:
                print(f"Échec UDP {ip}:{port}: {e}")
                continue
        
        return None

    async def _query_udp_single(self, ip: str, port: int) -> Optional[Dict]:
        """
        Requête UDP améliorée avec meilleurs paquets ACSP
        """
        try:
            loop = asyncio.get_event_loop()
            
            def _query():
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(4.0)  # Augmenté à 4 secondes
                
                try:
                    # Paquets ACSP dans l'ordre de priorité
                    packets = [
                        # ACSP_GET_INFO - Format correct
                        struct.pack('<HBB', 0x00C8, 0x00, 0x00),
                        # Version alternative avec padding
                        struct.pack('<HBBBB', 0x00C8, 0x00, 0x00, 0x00, 0x00),
                        # Format plus simple
                        struct.pack('<H', 0x00C8),
                        # Derniers recours
                        b'\xc8\x00\x00\x00',
                        b'INFO',
                    ]
                    
                    for i, packet in enumerate(packets):
                        try:
                            sock.sendto(packet, (ip, port))
                            sock.settimeout(3.0)  # Timeout plus court pour la réception
                            data, addr = sock.recvfrom(4096)  # Buffer plus large
                            
                            print(f"Réponse reçue de {ip}:{port}, taille: {len(data)}, paquet #{i}")
                            
                            if len(data) > 8:  # Au moins 8 bytes pour une réponse valide
                                server_info = self._parse_response(data)
                                
                                # Vérifier que nous avons des vraies données
                                if (server_info and server_info.get("online") and 
                                    server_info.get("name") != "Serveur AC" and
                                    server_info.get("track") not in ["Inconnu", "Détection TCP"]):
                                    
                                    # Essayer de récupérer la liste des joueurs
                                    try:
                                        # ACSP_GET_CAR_INFO
                                        car_packet = struct.pack('<HBB', 0x00CA, 0x00, 0xFF)
                                        sock.sendto(car_packet, (ip, port))
                                        sock.settimeout(2.0)
                                        car_data, _ = sock.recvfrom(8192)
                                        players = self._parse_car_info(car_data)
                                        server_info["player_list"] = players
                                        print(f"Joueurs trouvés: {len(players)}")
                                    except Exception as e:
                                        print(f"Échec récupération joueurs: {e}")
                                        server_info["player_list"] = []
                                
                                    return server_info
                                
                        except socket.timeout:
                            print(f"Timeout paquet #{i} sur {ip}:{port}")
                            continue
                        except Exception as e:
                            print(f"Erreur paquet #{i} sur {ip}:{port}: {e}")
                            continue
                    
                    return None
                    
                except Exception as e:
                    print(f"Erreur générale UDP {ip}:{port}: {e}")
                    return None
                finally:
                    sock.close()
            
            return await asyncio.wait_for(loop.run_in_executor(None, _query), timeout=8.0)
            
        except Exception as e:
            print(f"Erreur _query_udp_single {ip}:{port}: {e}")
            return None

    def _parse_response(self, data: bytes) -> Dict:
        """
        Parse amélioré des réponses AC
        """
        try:
            print(f"Parsing data, taille: {len(data)}, premiers bytes: {data[:20].hex()}")
            
            # Vérifier si c'est une réponse JSON
            if data.startswith(b'{'):
                try:
                    json_data = json.loads(data.decode('utf-8', errors='ignore'))
                    return {
                        "online": True,
                        "name": json_data.get("name", "Serveur AC"),
                        "track": json_data.get("track", json_data.get("map", "Inconnu")),
                        "players": f"{json_data.get('clients', 0)}/{json_data.get('maxclients', 0)}",
                        "player_list": json_data.get("players", []),
                        "session": json_data.get("session", "Inconnu"),
                        "time_left": json_data.get("timeleft", 0),
                        "weather": json_data.get("weather", "Inconnu"),
                        "temperature": json_data.get("ambient", 0)
                    }
                except:
                    pass
            
            # Parse binaire AC
            if len(data) >= 4:
                # Vérifier le packet ID
                packet_id = struct.unpack('<H', data[0:2])[0]
                print(f"Packet ID: 0x{packet_id:04X}")
                
                if packet_id == 0x00C9:  # ACSP_INFO response
                    return self._parse_ac_binary_improved(data[2:])
                elif packet_id == 0xC900:  # Endianness inversée
                    return self._parse_ac_binary_improved(data[2:])
                else:
                    # Essayer de parser quand même
                    print(f"ID inattendu, tentative de parsing...")
                    return self._parse_ac_binary_improved(data[2:])
            
            return None
            
        except Exception as e:
            print(f"Erreur parsing: {e}")
            return None

    def _parse_ac_binary_improved(self, data: bytes) -> Dict:
        """
        Parser binaire AC amélioré
        """
        try:
            print(f"Parsing binaire AC, taille: {len(data)}")
            offset = 0
            
            def read_string():
                nonlocal offset
                if offset >= len(data):
                    return ""
                # Chercher le null terminator
                end = data.find(b'\x00', offset)
                if end == -1:
                    # Pas de null terminator, prendre jusqu'à la fin
                    result = data[offset:].decode('utf-8', errors='replace')
                    offset = len(data)
                    return result.strip()
                
                result = data[offset:end].decode('utf-8', errors='replace')
                offset = end + 1
                return result.strip()
            
            def read_byte():
                nonlocal offset
                if offset >= len(data):
                    return 0
                result = data[offset]
                offset += 1
                return result
            
            def read_uint16():
                nonlocal offset
                if offset + 1 >= len(data):
                    return 0
                result = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
                return result
            
            # Lire les champs dans l'ordre ACSP
            server_name = read_string()
            print(f"Nom serveur: '{server_name}'")
            
            track = read_string()
            print(f"Track: '{track}'")
            
            track_config = read_string()
            print(f"Config: '{track_config}'")
            
            cars = read_string()
            print(f"Cars: '{cars}'")
            
            # Informations sur les joueurs
            current_players = read_byte()
            max_players = read_byte()
            print(f"Joueurs: {current_players}/{max_players}")
            
            # Sessions et temps (optionnels selon la version)
            session_type = read_byte() if offset < len(data) else 0
            session_time = read_uint16() if offset + 1 < len(data) else 0
            time_left = read_uint16() if offset + 1 < len(data) else 0
            
            # Construction du track complet
            full_track = track
            if track_config and track_config.strip() and track_config != track:
                full_track = f"{track} ({track_config})"
            
            # Session type mapping
            session_names = {
                0: "Practice",
                1: "Qualification", 
                2: "Race",
                3: "Hotlap",
                4: "Time Attack",
                5: "Drift",
                6: "Drag"
            }
            session_name = session_names.get(session_type, f"Type {session_type}")
            
            result = {
                "online": True,
                "name": server_name or "Serveur AC",
                "track": full_track or "Circuit inconnu",
                "players": f"{current_players}/{max_players}",
                "cars": cars or "Voitures inconnues",
                "player_list": [],  # Sera rempli par requête séparée
                "session": session_name,
                "time_left": time_left,
                "weather": "Inconnu",
                "temperature": 0
            }
            
            print(f"Résultat parsing: {result}")
            return result
            
        except Exception as e:
            print(f"Erreur parsing binaire: {e}")
            import traceback
            traceback.print_exc()
            return {
                "online": True,
                "name": "Serveur AC (erreur parsing)",
                "track": "Erreur lecture",
                "players": "?/?",
                "player_list": [],
                "session": "Inconnu",
                "time_left": 0,
                "weather": "Inconnu",
                "temperature": 0
            }

    def _parse_car_info(self, data: bytes) -> List[str]:
        """
        Parse amélioré des informations des voitures/joueurs
        """
        try:
            print(f"Parsing car info, taille: {len(data)}")
            if len(data) < 4:
                return []
                
            players = []
            offset = 0
            
            # Vérifier le packet ID
            if len(data) >= 2:
                packet_id = struct.unpack('<H', data[0:2])[0]
                print(f"Car info packet ID: 0x{packet_id:04X}")
                offset = 2
            
            # Lire le nombre de voitures
            if offset >= len(data):
                return []
            car_count = data[offset]
            offset += 1
            print(f"Nombre de voitures: {car_count}")
            
            for i in range(min(car_count, 32)):  # Limite sécurisée
                try:
                    if offset >= len(data):
                        break
                        
                    # Car ID
                    car_id = data[offset] if offset < len(data) else 0
                    offset += 1
                    
                    # Driver name (string null-terminated)
                    name_start = offset
                    name_end = data.find(b'\x00', offset)
                    if name_end == -1:
                        name_end = len(data)
                    
                    driver_name = data[name_start:name_end].decode('utf-8', errors='ignore').strip()
                    offset = name_end + 1 if name_end < len(data) else len(data)
                    
                    if driver_name:
                        players.append(driver_name)
                        print(f"Joueur {i}: {driver_name}")
                    
                    # Skip car model name
                    if offset < len(data):
                        car_end = data.find(b'\x00', offset)
                        if car_end != -1:
                            offset = car_end + 1
                        else:
                            offset = len(data)
                    
                    # Skip skin name
                    if offset < len(data):
                        skin_end = data.find(b'\x00', offset)
                        if skin_end != -1:
                            offset = skin_end + 1
                        else:
                            offset = len(data)
                    
                    # Skip binary data (position, etc.)
                    offset += min(50, len(data) - offset)  # Skip approximativement
                    
                except Exception as e:
                    print(f"Erreur parsing joueur {i}: {e}")
                    break
            
            print(f"Joueurs trouvés: {players}")
            return players
            
        except Exception as e:
            print(f"Erreur parsing car info: {e}")
            return []

    async def query_server_http(self, ip: str, http_port: int) -> Optional[Dict]:
        """
        Méthode HTTP améliorée
        """
        urls_to_try = [
            f"http://{ip}:{http_port}/INFO",
            f"http://{ip}:{http_port}/api/info",
            f"http://{ip}:{http_port}/status",
            f"http://{ip}:{http_port}/json",
            f"http://{ip}:{http_port}",
        ]
        
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for url in urls_to_try:
                    try:
                        print(f"Tentative HTTP: {url}")
                        async with session.get(url) as response:
                            if response.status == 200:
                                content_type = response.headers.get('content-type', '')
                                
                                if 'json' in content_type:
                                    data = await response.json()
                                else:
                                    text = await response.text()
                                    try:
                                        data = json.loads(text)
                                    except:
                                        # Pas JSON, essayer de parser comme texte
                                        if 'assetto' in text.lower() or 'server' in text.lower():
                                            return {
                                                "online": True,
                                                "name": f"Serveur HTTP {ip}",
                                                "track": "API Web détectée",
                                                "players": "?/?",
                                                "player_list": [],
                                                "session": "HTTP",
                                                "time_left": 0,
                                                "weather": "Inconnu",
                                                "temperature": 0
                                            }
                                        continue
                                
                                return {
                                    "online": True,
                                    "name": data.get("name", f"Serveur {ip}"),
                                    "track": data.get("track", data.get("map", "Inconnu")),
                                    "players": f"{data.get('clients', data.get('players', 0))}/{data.get('maxclients', data.get('maxplayers', 0))}",
                                    "player_list": data.get("players", data.get("clients_list", [])),
                                    "session": data.get("session", "Inconnu"),
                                    "time_left": data.get("timeleft", 0),
                                    "weather": data.get("weather", "Inconnu"),
                                    "temperature": data.get("ambient", data.get("temperature", 0))
                                }
                                
                    except Exception as e:
                        print(f"Erreur HTTP {url}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Erreur HTTP générale: {e}")
            
        return None

    async def query_server_tcp(self, ip: str, port: int) -> Optional[Dict]:
        """
        Test TCP basique - utilisé uniquement pour vérifier la connectivité
        """
        try:
            loop = asyncio.get_event_loop()
            
            def _tcp_connect():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                try:
                    result = sock.connect_ex((ip, port))
                    return result == 0
                except:
                    return False
                finally:
                    sock.close()
            
            is_open = await asyncio.wait_for(loop.run_in_executor(None, _tcp_connect), timeout=4.0)
            
            if is_open:
                # Ne retourner que si aucune autre méthode n'a fonctionné
                return {
                    "online": True,
                    "name": f"Serveur TCP {ip}:{port}",
                    "track": "Port ouvert (TCP)",
                    "players": "?/?",
                    "player_list": [],
                    "session": "Détecté",
                    "time_left": 0,
                    "weather": "Inconnu",
                    "temperature": 0
                }
            return None
            
        except Exception as e:
            print(f"Erreur TCP: {e}")
            return None

    async def query_server(self, ip: str, port: int = 9600, http_port: int = 8621) -> Optional[Dict]:
        """
        Méthode principale avec priorité aux vraies données
        """
        print(f"\n=== Interrogation {ip}:{port} ===")
        
        # 1. Essayer UDP en priorité (vraies données AC)
        print("1. Tentative UDP...")
        udp_result = await self.query_server_udp_multiple(ip, port)
        if udp_result and udp_result.get("name") != "Serveur AC":
            print(f"✅ UDP réussi: {udp_result.get('name')}")
            return udp_result
        
        # 2. Essayer HTTP
        print("2. Tentative HTTP...")
        http_result = await self.query_server_http(ip, http_port)
        if http_result and "API Web" not in http_result.get("track", ""):
            print(f"✅ HTTP réussi: {http_result.get('name')}")
            return http_result
        
        # 3. En dernier recours, TCP (juste pour savoir si c'est en ligne)
        print("3. Tentative TCP (fallback)...")
        tcp_result = await self.query_server_tcp(ip, port)
        if tcp_result:
            print(f"⚠️  TCP seulement: port ouvert mais pas de données détaillées")
            return tcp_result
        
        print("❌ Aucune méthode n'a fonctionné")
        return None

    async def ping_server(self, ip: str, port: int = 9600) -> bool:
        """
        Test simple de connectivité
        """
        result = await self.query_server(ip, port)
        return result is not None

    @commands.command(name='acaddserver')
    @commands.has_permissions(administrator=True)
    async def add_server(self, ctx, server_identifier: str, http_port: int = 8621, *, name: str = None):
        """Ajoute un serveur AC à la liste de monitoring"""
        try:
            # Parse l'identifiant du serveur
            if ':' in server_identifier:
                ip, port_str = server_identifier.split(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Erreur",
                        description=f"Port invalide: `{port_str}`. Le port doit être un nombre.",
                        color=discord.Color.red()))
                    return
            else:
                ip = server_identifier
                port = 9600  # Port par défaut
            
            server_key = f"{ip}:{port}"
            
            if not name:
                name = f"Serveur {server_key}"
            
            if server_key in self.servers:
                await ctx.send(embed=discord.Embed(
                    title="❌ Erreur",
                    description=f"Le serveur {server_key} est déjà dans la liste !",
                    color=discord.Color.red()))
                return

            msg = await ctx.send(embed=discord.Embed(
                title="🔄 Test de connexion...",
                description=f"Vérification de {server_key}\nCela peut prendre quelques secondes...",
                color=discord.Color.orange()))

            # Test de connexion
            server_info = await self.query_server(ip, port, http_port)
            is_online = server_info is not None

            # Sauvegarde
            self.servers[server_key] = {
                "name": name,
                "ip": ip,
                "port": port,
                "http_port": http_port,
                "added_by": ctx.author.id,
                "guild_id": ctx.guild.id if ctx.guild else 0
            }
            
            self.save_servers()

            # Réponse
            status_emoji = "🟢" if is_online else "🔴"
            status_text = "En ligne" if is_online else "Hors ligne"

            embed = discord.Embed(
                title="✅ Serveur ajouté",
                description=f"**{name}** (`{server_key}`) a été ajouté à la liste de monitoring",
                color=discord.Color.green())
            embed.add_field(name="Statut", value=f"{status_emoji} {status_text}", inline=True)
            embed.add_field(name="Ajouté par", value=ctx.author.mention, inline=True)
            
            if is_online and server_info:
                embed.add_field(name="Nom détecté", value=server_info['name'], inline=False)
                embed.add_field(name="Circuit", value=server_info['track'], inline=True)
                embed.add_field(name="Joueurs", value=server_info['players'], inline=True)
                if 'cars' in server_info:
                    embed.add_field(name="Voitures", value=server_info['cars'], inline=True)
                
            await msg.edit(embed=embed)
            
        except Exception as e:
            print(f"❌ ERREUR dans add_server: {e}")
            import traceback
            traceback.print_exc()
            try:
                await ctx.send(embed=discord.Embed(
                    title="❌ Erreur technique",
                    description=f"Une erreur s'est produite: {str(e)}",
                    color=discord.Color.red()))
            except Exception as e2:
                print(f"❌ Impossible d'envoyer le message d'erreur: {e2}")

    @commands.command(name='acserver')
    async def check_server(self, ctx, server_identifier: str = None):
        """Vérifie le statut d'un serveur AC"""
        if server_identifier is None:
            # Liste tous les serveurs
            if not self.servers:
                await ctx.send(embed=discord.Embed(
                    title="📋 Liste des serveurs",
                    description="Aucun serveur dans la liste de monitoring.",
                    color=discord.Color.blue()))
                return

            msg = await ctx.send(embed=discord.Embed(
                title="📋 Vérification en cours...",
                description="Vérification du statut de tous les serveurs...\nCela peut prendre un moment.",
                color=discord.Color.blue()))

            server_status = []
            for server_key, data in self.servers.items():
                info = await self.query_server(data["ip"], data["port"], data.get("http_port", 8621))
                status_emoji = "🟢" if info else "🔴"
                track = info['track'] if info else "Hors ligne"
                players = info['players'] if info else "0/0"
                
                # Ajouter la liste des joueurs si disponible
                player_info = ""
                if info and info.get('player_list'):
                    player_names = info['player_list'][:5]  # Limite à 5 joueurs pour l'affichage
                    if player_names:
                        player_info = f"\n   👥 {', '.join(player_names)}"
                        if len(info['player_list']) > 5:
                            player_info += f" (+{len(info['player_list'])-5} autres)"
                
                server_status.append(f"{status_emoji} **{data['name']}**\n   `{server_key}` • {track} • {players}{player_info}")

            embed = discord.Embed(
                title="🏁 Statut des serveurs AC",
                description="\n\n".join(server_status),
                color=discord.Color.blue())
            embed.set_footer(text=f"Dernière vérification: {discord.utils.format_dt(discord.utils.utcnow(), 'R')}")
            await msg.edit(embed=embed)
            
        else:
            # Parse l'identifiant du serveur
            if ':' in server_identifier:
                ip, port_str = server_identifier.split(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Erreur",
                        description=f"Port invalide: `{port_str}`. Le port doit être un nombre.",
                        color=discord.Color.red()))
                    return
            else:
                ip = server_identifier
                port = 9600  # Port par défaut
            
            server_key = f"{ip}:{port}"
            
            # Vérification d'un serveur spécifique
            msg = await ctx.send(embed=discord.Embed(
                title="🔄 Vérification...",
                description=f"Interrogation de `{server_key}`...",
                color=discord.Color.orange()))

            http_port = self.servers.get(server_key, {}).get("http_port", 8621)
            info = await self.query_server(ip, port, http_port)
            
            if info:
                embed = discord.Embed(
                    title="🟢 Serveur AC en ligne",
                    description=f"**{server_key}**",
                    color=discord.Color.green())
                embed.add_field(name="Nom du serveur", value=info['name'], inline=False)
                embed.add_field(name="Circuit", value=info['track'], inline=True)
                embed.add_field(name="Joueurs", value=info['players'], inline=True)
                if 'cars' in info and info['cars'] != "Inconnu":
                    embed.add_field(name="Voitures", value=info['cars'], inline=True)
                if 'session' in info:
                    embed.add_field(name="Session", value=info['session'], inline=True)

                # Afficher la liste des joueurs
                if info.get('player_list'):
                    players_text = "\n".join([f"• {player}" for player in info['player_list']])
                    if len(players_text) > 1000:  # Limite Discord
                        players_text = players_text[:950] + "\n• ..."
                    embed.add_field(name="🏃 Joueurs connectés", value=players_text or "Aucun", inline=False)
                else:
                    embed.add_field(name="🏃 Joueurs connectés", value="Information non disponible", inline=False)

                join_url = f"https://acstuff.ru/s/q:race/online/join?ip={ip}&httpPort={http_port}"
                embed.add_field(name="🔗 Connexion", value=f"[Rejoindre]({join_url})", inline=False)
            else:
                embed = discord.Embed(
                    title="🔴 Serveur AC hors ligne",
                    description=f"**{server_key}** ne répond pas ou est inaccessible",
                    color=discord.Color.red())

            embed.set_footer(text=f"Vérifié le {discord.utils.format_dt(discord.utils.utcnow(), 'F')}")
            await msg.edit(embed=embed)

    @commands.command(name='aclist')
    async def list_servers(self, ctx):
        """Liste tous les serveurs AC monitorés"""
        if not self.servers:
            await ctx.send(embed=discord.Embed(
                title="🏁 Liste des serveurs AC",
                description="Aucun serveur AC dans la liste.",
                color=discord.Color.blue()))
            return

        embed = discord.Embed(title="🏁 Serveurs AC monitorés", color=discord.Color.blue())
        for i, (key, data) in enumerate(self.servers.items(), 1):
            embed.add_field(
                name=f"{i}. {data['name']}",
                value=f"**IP:** `{key}`\n**HTTP:** `{data.get('http_port', 8621)}`\n**Par:** <@{data['added_by']}>",
                inline=True)
        embed.set_footer(text=f"Total: {len(self.servers)} serveur(s)")
        await ctx.send(embed=embed)

    @commands.command(name='acremove')
    @commands.has_permissions(administrator=True)
    async def remove_server(self, ctx, server_identifier: str):
        """Supprime un serveur de la liste (format: ip:port)"""
        try:
            # Si l'utilisateur donne déjà ip:port
            if ':' in server_identifier:
                server_key = server_identifier
            else:
                # Sinon on assume que c'est juste une IP avec port par défaut
                server_key = f"{server_identifier}:9600"
            
            if server_key not in self.servers:
                # Chercher si le serveur existe avec un port différent
                matching_servers = [key for key in self.servers.keys() if key.startswith(server_identifier.split(':')[0])]
                
                if matching_servers:
                    servers_list = '\n'.join([f"• `{key}` - {self.servers[key]['name']}" for key in matching_servers])
                    await ctx.send(embed=discord.Embed(
                        title="❌ Serveur non trouvé",
                        description=f"Le serveur `{server_key}` n'est pas dans la liste.\n\n**Serveurs disponibles pour cette IP :**\n{servers_list}\n\n**Utilisation :** `.acremove ip:port`",
                        color=discord.Color.red()))
                else:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Erreur",
                        description=f"Le serveur `{server_key}` n'est pas dans la liste !\n\nUtilisez `.aclist` pour voir tous les serveurs.",
                        color=discord.Color.red()))
                return
            
            server_name = self.servers[server_key]['name']
            del self.servers[server_key]
            self.save_servers()
            
            await ctx.send(embed=discord.Embed(
                title="✅ Serveur supprimé",
                description=f"**{server_name}** (`{server_key}`) a été retiré de la liste",
                color=discord.Color.green()))
                
        except Exception as e:
            print(f"❌ Erreur dans remove_server: {e}")
            await ctx.send(embed=discord.Embed(
                title="❌ Erreur technique",
                description=f"Erreur lors de la suppression: {str(e)}",
                color=discord.Color.red()))

    @commands.command(name='acdebug')
    @commands.has_permissions(administrator=True)
    async def debug_server(self, ctx, server_identifier: str):
        """Debug détaillé d'un serveur AC"""
        try:
            # Parse l'identifiant du serveur
            if ':' in server_identifier:
                ip, port_str = server_identifier.split(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    await ctx.send(embed=discord.Embed(
                        title="❌ Erreur",
                        description=f"Port invalide: `{port_str}`",
                        color=discord.Color.red()))
                    return
            else:
                ip = server_identifier
                port = 9600
            
            msg = await ctx.send(embed=discord.Embed(
                title="🔍 Debug en cours...",
                description=f"Analyse détaillée de `{ip}:{port}`",
                color=discord.Color.orange()))
            
            debug_info = []
            
            # Test UDP
            debug_info.append("**Test UDP:**")
            udp_result = await self.query_server_udp_multiple(ip, port)
            if udp_result:
                debug_info.append(f"✅ UDP réussi - {udp_result.get('name', 'N/A')}")
                debug_info.append(f"   Track: {udp_result.get('track', 'N/A')}")
                debug_info.append(f"   Joueurs: {udp_result.get('players', 'N/A')}")
            else:
                debug_info.append("❌ UDP échoué")
            
            # Test HTTP
            debug_info.append("\n**Test HTTP:**")
            http_result = await self.query_server_http(ip, 8621)
            if http_result:
                debug_info.append(f"✅ HTTP réussi - {http_result.get('name', 'N/A')}")
            else:
                debug_info.append("❌ HTTP échoué")
            
            # Test TCP
            debug_info.append("\n**Test TCP:**")
            tcp_result = await self.query_server_tcp(ip, port)
            if tcp_result:
                debug_info.append("✅ Port TCP ouvert")
            else:
                debug_info.append("❌ Port TCP fermé")
            
            embed = discord.Embed(
                title=f"🔍 Debug - {ip}:{port}",
                description="\n".join(debug_info),
                color=discord.Color.blue())
            
            await msg.edit(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                title="❌ Erreur debug",
                description=f"Erreur: {str(e)}",
                color=discord.Color.red()))

    @add_server.error
    async def add_server_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                title="❌ Permissions insuffisantes",
                description="Vous devez être administrateur pour utiliser cette commande.",
                color=discord.Color.red()))

    @remove_server.error
    async def remove_server_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                title="❌ Permissions insuffisantes",
                description="Vous devez être administrateur pour utiliser cette commande.",
                color=discord.Color.red()))

    @debug_server.error
    async def debug_server_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                title="❌ Permissions insuffisantes",
                description="Vous devez être administrateur pour utiliser cette commande.",
                color=discord.Color.red()))

async def setup(bot):
    await bot.add_cog(Assetto(bot))