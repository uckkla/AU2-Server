# Achievement Unlocked 2 - Multiplayer Server
 
A custom multiplayer server that restores online co-op functionality to [Achievement Unlocked 2](https://armorgames.com/play/6561/achievement-unlocked-2), a Flash game by John Cooney (jmtb02) originally hosted on Armor Games. The official servers were shut down years ago, this project brings them back.
 
 
## What is this?
 
Achievement Unlocked 2 has a co-op multiplayer mode where 2-4 players can work together to unlock achievements. This mode required a SmartFoxServer backend that Armor Games no longer runs. Rather than using the original SmartFoxServer software, this project reimplements the necessary parts of the SFS1 protocol in Python, along with an HTTP server to serve the modified SWF file.
 
 
## Requirements
 
- Python 3.10+
- A copy of the modified `achievement-unlocked-6561.swf` (included, for host only)
- [Adobe Flash Player Standalone Projector 32](https://fpdownload.macromedia.com/pub/flashplayer/updaters/32/flashplayer_32_sa.exe) — use version 32, the last version without the kill switch.
 
 
## Setup
> [!NOTE]
> Steps 1-3 are required by the host PC. If you are joining the host, skip to step 4.
 
### 1. Download the server

**Option A: Clone with git** 
```bash
git clone https://github.com/uckkla/Achievement-Unlocked-2-Server.git
cd Achievement-Unlocked-2-Server
```

**Option B: Download the zip**
If you don't have git installed, download the latest release from the [Releases](https://github.com/uckkla/AU2-Server/releases) page and extract it.
 
### 2. Configure the server IP
 
Open `public/config.xml` and set the `<ip>` to the IP address of the machine running the server:
 
- **Playing over a local network:** use the host machine's local IP (e.g. `192.168.1.x`)
- **Playing over the internet:** use the host machine's public IP (requires port forwarding)
 
The port should not be changed.
 
```xml
<SmartFoxConfig>
    <ip>192.168.1.x</ip>
    <port>9339</port>
    <zone>AU2</zone>
</SmartFoxConfig>
```
 
### 3. Start the server
 
```
python main.py 
```
 
You should see:
```
HTTP server listening on 0.0.0.0:8000
SFS server listening on 0.0.0.0:9339
```
 
If you are running the policy server, you will also see:
```
Policy server listening on 0.0.0.0:843
```
 
### 4. Load the game
 
Open the Flash Projector and load the following URL, replacing the IP with the host machine's IP:
```
http://192.168.1.x:8000/achievement-unlocked-6561.swf
```
 
If connecting from outside the local network, ask the host for their public IP and use that instead.
 
 
## Playing over the internet
 
To allow friends outside your local network to connect, you need to forward the following ports on your router to your machine's local IP:
 
| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | TCP | HTTP server (serves the SWF) |
| 9339 | TCP | SFS game server |
| 843  | TCP | Flash policy server (only needed if using `--policy-server` flag) |
 
## Command Line Options
 
| Flag | Description |
|------|-------------|
| `--policy-server` | Enables a dedicated Flash policy server on port 843 |
 
By default, Flash policy requests are handled on port 9339 alongside game traffic. Note that Flash checks port 843 first before falling back to 9339, which may cause a brief delay when connecting. If you experience connection issues or want to eliminate this delay, enable the dedicated policy server:
 
```
python main.py --policy-server
```
 
This adds port 843 as a requirement for port forwarding if playing over the internet.

## Troubleshooting

**Flash Projector shows a blank screen**
- Make sure the server is running and you can see the HTTP and SFS server listening messages.
- Check that the IP in `config.xml` matches the host machine's actual IP.
- If connecting over the internet, make sure ports 8000 and 9339 are forwarded. If using policy server, port 843 should also be forwarded.

**Game loads but multiplayer lobby is empty or won't connect**
- Check that the relevant ports are not being blocked.
- The IP in the Flash Projector URL and the IP in `config.xml` should both point to the host.
 
## How it works
 
### SFS1 Protocol Reimplementation
 
The game uses SmartFoxServer 1.x, which communicates over TCP using null-terminated XML messages. This server reimplements the parts of the SFS1 protocol that AU2 needs:
 
- **Version check** (`verChk` / `apiOK`) — handshake on connect
- **Login** (`login` / `logOK`) — player authentication with username
- **Room list** (`getRmList` / `rmList`) — dynamic list of all active rooms
- **Room creation** (`createRoom` / `roomAdd` + `joinOK`) — creates a temporary game room and auto-joins the creator
- **Room joining** (`joinRoom` / `joinOK`) — joins an existing room by ID, with checks for password, capacity, game in progress, and duplicate usernames
- **Public messages** (`pubMsg`) — relays game state (`>>` prefix) and chat (`!!` prefix) between players
- **Disconnection** — notifies remaining players via `userGone` and cleans up empty rooms
 
### Flash Policy Server
 
Flash requires a cross-domain policy file before allowing socket connections to a server. By default this is handled on port 9339 alongside game traffic. A dedicated policy server on port 843 can optionally be enabled via `--policy-server` for networks that require it.
 
### HTTP Server
 
The SWF file is served over HTTP so that Flash's security sandbox treats it as a web-hosted file rather than a local file, which is required for socket connections to work.
 
### SWF Modifications
 
The original SWF has been modified to:
- Connect to a configurable server address via `config.xml` instead of the hardcoded Armor Games server IP
- Remove the domain sitelock
- Fix in-game chat by correctly initialising the chat UI on multiplayer game start
- Update the main menu version text
 
 
## Credits
 
- **John Cooney (jmtb02)** — original game developer
- **Armor Games** — original publisher