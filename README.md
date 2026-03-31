# Personal Discord Bot

> Bot Discord multifonction — admin, réseau, monitoring…

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Status](https://img.shields.io/badge/status-online-success)
![Power](https://img.shields.io/badge/powered%20by-homelab-purple)

---

## Présentation

**PythonBot**, créé pour :

* automatiser un serveur
* monitorer un système
* jouer avec le réseau
* apprendre ptyhon,api etc :)

> Héberger sur mon optiplex et me permet d'avoir les stats sonarr,radarr,qbittorrent,temps etc!

---

## Commandes principales

### Mode Admin

```
.shutdown   → Éteint le bot (RIP)
.restart    → Redémarre le bot
.purge      → Supprime des messages
.setnick    → Change le pseudo du bot
.cogs       → Gère les modules
```

---

### Infos système

```
.sysinfo    → Stats complètes du serveur
.temp       → Température du système 
.botinfo    → Infos du bot
```

---

### NMap

```
.nmap       → Scan une cible réseau
.nmap_help  → Aide pour les scans
```

---

### Bonus fun

* Notifications de jeux gratuits 🎮
* Automatisation Discord
* Modules personnalisés

---

## Exemple

```
.nmap 192.168.2.1
```

## Résultat :

```
[+] Host is up
[+] Open ports detected
```

---

## Tech utilisée

* Python
* Discord.py
* Nmap
* Docker (optionnel)
* Linux

---

## Installation

```
git clone https://github.com/elfant0me/PersonalDiscordBot
cd PersonalDiscordBot
pip install -r requirements.txt
python bot.py
```

---

## Configuration

Créer un `.env` :

```
DISCORD_TOKEN=your_token_here
```

---

## 🧠 Lore (aka pourquoi ce projet existe)

Ce bot fait partie de mon **homelab** :

* Services auto-hébergés
* Accès sécurisé
* Monitoring
* Expérimentation réseau

C’est un terrain de jeu… mais version sysadmin.

---

## Auteur

**eLFantome**

> Geek by day ☕
> Sysadmin by night 🌙
> Gamer anytime 🎮

---

## Disclaimer

Ce bot est fait pour usage éducatif / personnel.
Utilise les commandes réseau de façon responsable 😅
