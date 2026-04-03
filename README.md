# Claude Sessions Dashboard

Centrally view and manage Claude Code conversations across multiple machines.

## Architecture

```
  Machine A (agent)     Machine B (agent)     Machine C (agent)
  ┌──────────┐         ┌──────────┐         ┌──────────┐
  │ agent.py │──POST──▶│ agent.py │──POST──▶│ agent.py │──POST──┐
  └──────────┘         └──────────┘         └──────────┘        │
                                                                 ▼
                                                    ┌────────────────────┐
                                                    │  Server (app.py)   │
                                                    │  Flask + SQLite    │
                                                    │  + JSONL backups   │
                                                    └────────────────────┘
                                                                 │
                                                        Cloudflare Tunnel
                                                      + Cloudflare Access
                                                                 │
                                                         Browser (anywhere)
```

- **Server** (`server/app.py`) — Flask + SQLite dashboard. Stores parsed sessions in SQLite and raw JSONL backups on disk.
- **Agent** (`agent/agent.py`) — lightweight sync script on each machine. Reads local `~/.claude/` session files and pushes to the server.

## Quick Start

### 1. Server Setup

```bash
cd server
pip install -r requirements.txt

# Edit config — set your API key
vim server-config.yaml

# Run directly
python app.py

# Or install as a service (see below)
```

Dashboard available at `http://localhost:5000`.

### 2. Agent Setup (each machine)

```bash
cd agent
pip install -r requirements.txt

# Edit config — set server URL, API key, and machine name
vim agent-config.yaml

# Sync once
python agent.py --once

# Or run as daemon
python agent.py --daemon
```

### 3. Cron Setup (optional)

Sync every 5 minutes:

```bash
crontab -e
# Add:
*/5 * * * * cd /path/to/claude-sessions/agent && python3 agent.py --once >> /tmp/claude-sync.log 2>&1
```

## Installing as a Service

The server can be installed as a persistent service that starts on boot.

### Linux (systemd)

```bash
cd server
chmod +x install-service.sh
./install-service.sh
```

Manage with:
```bash
sudo systemctl status claude-dashboard
sudo systemctl stop claude-dashboard
sudo systemctl restart claude-dashboard
sudo journalctl -u claude-dashboard -f   # view logs
```

Uninstall: `./uninstall-service.sh`

### macOS (launchd)

```bash
cd server
chmod +x install-service.sh
./install-service.sh
```

Manage with:
```bash
launchctl list | grep claude-dashboard
launchctl stop com.claude-dashboard
launchctl start com.claude-dashboard
tail -f /tmp/claude-dashboard.log
```

Uninstall: `./uninstall-service.sh`

### Windows (NSSM or Scheduled Task)

Run PowerShell as Administrator:

```powershell
cd server
.\install-service.ps1
```

If [NSSM](https://nssm.cc/) is installed, it creates a proper Windows service. Otherwise, it falls back to a scheduled task that runs at logon.

## Making the Server Reachable Across Machines

Your agents need to reach the server over the network. Options:

### Option A: Cloudflare Tunnel (recommended for internet access)

Exposes your server securely without opening ports or configuring firewalls.

```bash
# Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel login
cloudflared tunnel create claude-dashboard
cloudflared tunnel route dns claude-dashboard sessions.yourdomain.com
cloudflared tunnel --url http://localhost:5000 run claude-dashboard
```

Then configure **Cloudflare Access** in the Zero Trust dashboard to add authentication (Google, GitHub, email OTP) for browser access. Agents bypass Cloudflare Access by using the API key header directly — add a [Service Auth token](https://developers.cloudflare.com/cloudflare-one/identity/service-tokens/) or bypass policy for the `/api/sync` path.

### Option B: Tailscale / ZeroTier (private mesh VPN)

If all machines are on Tailscale, the server is reachable via its Tailscale IP (e.g., `http://100.x.y.z:5000`). No public exposure needed.

### Option C: Direct IP / LAN

If machines are on the same network, use the server's LAN IP directly. For machines on different networks, you'll need port forwarding on your router (port 5000).

Set the agent config accordingly:

```yaml
# agent-config.yaml
server_url: "https://sessions.yourdomain.com"  # Cloudflare Tunnel
# server_url: "http://100.64.0.1:5000"         # Tailscale
# server_url: "http://192.168.1.50:5000"        # LAN
```

## Raw JSONL Backups

In addition to the SQLite database, the server stores raw JSONL session files in `server/backups/<vm-name>/`. This preserves the original Claude Code session format including all metadata, tool calls, and thinking blocks.

## Configuration

### Server (`server/server-config.yaml`)

| Key | Description | Default |
|-----|-------------|---------|
| `api_key` | Shared secret for agent auth | (required) |
| `host` | Bind address | `0.0.0.0` |
| `port` | Port | `5000` |
| `db_path` | SQLite database path | `./sessions.db` |
| `backup_dir` | Raw JSONL backup directory | `./backups` |
| `debug` | Flask debug mode | `false` |

### Agent (`agent/agent-config.yaml`)

| Key | Description | Default |
|-----|-------------|---------|
| `server_url` | Dashboard server URL | (required) |
| `api_key` | Shared secret | (required) |
| `vm_name` | Label for this machine | hostname |
| `sync_interval` | Seconds between syncs (daemon mode) | `300` |
